"""2차 판단(실데이터 대조, data_reconcile) 단위 테스트 — 구독·CLI·MCP·네트워크 없이 동작(모킹).

- reconcile_via_cli: mocked claude subprocess 의 structured_output → DataReconcileDiff
- MCP 켠 argv 검증: --strict-mcp-config 없음 · --permission-mode default · --allowedTools(Kona-hue) · effort
- 구독 인증 강제: 자식 env 에서 ANTHROPIC_API_KEY 제거
- claude 미설치/비정상종료/미구조화 → UNVERIFIABLE
- 바인드 해석(default 우선·override·bare 보존), 스키마 제약 준수, 매핑
- 엔드포인트: QD_RECON_ENABLED 킬스위치 / 활성 시 data_reconcile 채워짐
"""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from query_diff.ai_diff import data_reconcile
from query_diff.ai_diff.data_reconcile import _resolve_binds, _column_map_hints, reconcile_via_cli
from query_diff.ai_diff.schema import AI_DATA_RECONCILE_SCHEMA, AiDataReconcile
from query_diff.api import app
from query_diff.models import Attribution, Confidence, Dialect, FinalVerdict, ReconcileStatus

client = TestClient(app)

_SQL_B = "SELECT bank_cd, SUM(amt) AS tot FROM ods.stat WHERE dt BETWEEN ${start_dt=20250501} AND ${end_dt} GROUP BY bank_cd"
_A_CSV = "bank_cd,tot\nBANK01,100\nBANK02,200\n"


class _FakeProc:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout, self._stderr, self.returncode = stdout, stderr, returncode

    async def communicate(self, input=None):  # noqa: A002
        return self._stdout, self._stderr

    def kill(self):
        pass

    async def wait(self):
        return self.returncode


def _fake_exec(stdout_bytes=b"", returncode=0, captured=None):
    async def _exec(*argv, **kwargs):
        if captured is not None:
            captured["argv"] = argv
            captured["env"] = kwargs.get("env")
        return _FakeProc(stdout=stdout_bytes, returncode=returncode)

    return _exec


_RECON = {
    "status": "MISMATCH",
    "headline": "BANK02 합계 불일치",
    "row_count_a": 2,
    "row_count_b": 2,
    "matched_keys": 1,
    "mismatches": [
        {"key": "BANK02", "column": "tot", "value_a": "200", "value_b": "180",
         "likely_cause": "집계 그레인 차이"},
    ],
    "only_in_a": [],
    "only_in_b": [],
    "caveats": ["샘플 불일치는 실제 차이의 강한 근거"],
    "sample_bounded": False,
    "b_csv_path": "/hallucinated/path.csv",
}


def test_reconcile_maps_structured_output_and_mcp_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-stripped")
    captured: dict = {}
    stdout = json.dumps({"structured_output": _RECON, "total_cost_usd": 0}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout, captured=captured))

    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", {"end_dt": "20260601"},
        op_an=None, out_dir=str(tmp_path),
    ))

    assert result.status == ReconcileStatus.MISMATCH
    assert result.matched_keys == 1
    assert result.mismatches[0].key == "BANK02"
    assert result.mismatches[0].likely_cause == "집계 그레인 차이"
    # 바인드 해석: default(start_dt) + override(end_dt)
    assert result.binds_used == {"start_dt": "20250501", "end_dt": "20260601"}
    assert result.a_sample_name == "a.csv"
    # 파일이 실제로 생성되지 않았으므로 헛경로가 아니라 None
    assert result.b_csv_path is None

    argv = " ".join(captured["argv"])
    assert "--strict-mcp-config" not in argv               # MCP 켬
    assert "--permission-mode default" in argv             # plan 모드 방지(스파이크 함정)
    assert "mcp__Kona-hue-MCP__hue_run_query" in argv       # 툴 화이트리스트
    assert "--allowedTools" in argv
    # 구독 강제: 자식 env 에 ANTHROPIC_API_KEY 없어야
    assert "ANTHROPIC_API_KEY" not in (captured["env"] or {})


def test_reconcile_reports_b_csv_when_file_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: "/usr/bin/claude")
    stdout = json.dumps({"structured_output": _RECON}).encode("utf-8")

    # 실제 LLM 처럼 서브프로세스가 실행 중 b_sample.csv 를 쓴다(진입부 스테일 삭제 후 프레시 생성).
    # → 이번 실행이 실제로 쓴 파일만 경로로 노출됨을 검증.
    async def _exec_writes(*argv, **kwargs):
        (tmp_path / "b_sample.csv").write_text("bank_cd,tot\nBANK01,100\n", encoding="utf-8")
        return _FakeProc(stdout=stdout, returncode=0)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _exec_writes)
    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None, op_an=None, out_dir=str(tmp_path),
    ))
    assert result.b_csv_path == str(tmp_path / "b_sample.csv")


def test_reconcile_deletes_stale_b_csv_on_entry(monkeypatch, tmp_path):
    """직전 실행이 남긴 b_sample.csv 는 진입 시 삭제 → 이번 실행이 안 쓰면 노출되지 않는다(스테일 방지).

    재현: 20240101 실행이 남긴 옛 결과(2행)가 있는 상태에서 20240102 재실행(B 0건 → 미기록)이면,
    옛 파일이 표에 스테일로 뜨던 버그. 진입 삭제로 파일 부재 → b_csv_path=None → 표는 '결과 0건'.
    """
    stale = tmp_path / "b_sample.csv"
    stale.write_text("년월,은행코드,총건수\n202401,020,1\n202401,088,1\n", encoding="utf-8")
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)  # 서브프로세스 없이 단락(파일 미기록)
    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None, out_dir=str(tmp_path),
    ))
    assert not stale.exists()            # 진입부에서 스테일 파일 삭제됨
    assert result.b_csv_path is None     # 이번 실행이 쓰지 않았으므로 노출 안 함
    assert result.status == ReconcileStatus.UNVERIFIABLE


def test_where_date_literals_extracts_dates_excludes_masks():
    """WHERE 날짜 리터럴만 수집 — 포맷 마스크('yyyymmdd')·코드 상수('A0000')는 제외."""
    from query_diff.ai_diff.data_reconcile import _where_date_literals
    a = _where_date_literals(
        "SELECT x FROM t WHERE dt BETWEEN to_date('20240101','yyyymmdd') "
        "AND to_date('20240101','yyyymmdd') AND code = 'A0000'", "oracle")
    assert a == {"20240101"}
    b = _where_date_literals(
        "SELECT x FROM t WHERE dt BETWEEN to_timestamp('20240102','yyyyMMdd') "
        "AND to_timestamp('20240102','yyyyMMdd')", "hive")
    assert b == {"20240102"}
    assert _where_date_literals("!!! not sql", "hive") == set()      # 파싱 실패 → 빈 set


def test_where_date_ranges_extracts_between_and_bounds():
    """WHERE 날짜 술어를 컬럼별 범위 표시로(best-effort). to_date/to_timestamp 래퍼·포맷 마스크 무관."""
    from query_diff.ai_diff.data_reconcile import _where_date_ranges
    # BETWEEN — 하한==상한(단일일)
    assert _where_date_ranges(
        "SELECT x FROM t WHERE created_at BETWEEN to_date('20240101','yyyymmdd') "
        "AND to_date('20240101','yyyymmdd')", "oracle") == ["created_at: 20240101~20240101"]
    # BETWEEN — 범위(바인드 치환 후 형태)
    assert _where_date_ranges(
        "SELECT x FROM t WHERE sys_cre_dttm BETWEEN to_timestamp('20240101','yyyyMMdd') "
        "AND to_timestamp('20240102','yyyyMMdd')", "hive") == ["sys_cre_dttm: 20240101~20240102"]
    # >= / <= 경계쌍 → 하나의 범위로 묶임(한정자 제거)
    assert _where_date_ranges(
        "SELECT x FROM t a WHERE a.dt >= 20240101 AND a.dt <= 20240103", "hive") == \
        ["dt: 20240101~20240103"]
    # = (단일 날짜)
    assert _where_date_ranges("SELECT x FROM t WHERE dt = '20240101'", "hive") == ["dt: 20240101"]
    # 날짜 아닌 상수/파싱 실패 → 빈 리스트
    assert _where_date_ranges("SELECT x FROM t WHERE code = 'A0000'", "hive") == []
    assert _where_date_ranges("!!! not sql", "hive") == []


def test_build_prompt_condition_date_diff_block():
    """cond_diff(dict) 있으면 [조건 날짜 정합성] 블록 + QUERY(조건 차이) 지시 포함, 없으면 블록 미포함.

    cond_diff = {"a_dates","b_dates","a_ranges","b_ranges"} (집합차 아님 — 전체 값+범위 무손실 전달)."""
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", _A_CSV, "a.csv", {}, [], "/tmp/b.csv",
                      cond_diff={"a_dates": ["20240101"], "b_dates": ["20240102"],
                                 "a_ranges": [], "b_ranges": []})
    assert "A샘플과 B실행은 서로 다른 날짜" in p     # 조건 블록(조건차이 있을 때만)
    assert "20240101" in p and "20240102" in p
    assert "QUERY" in p and "조건 차이" in p
    assert "없음/불명/미상/전체" in p               # A를 '없음/미상'으로 서술하지 말라는 금지 지시 고정
    # cond_diff 없으면 조건 블록 미포함(단, 원인분류/예시에서 '[조건 날짜 정합성]' 명칭 언급은 상존).
    p2 = _build_prompt("SELECT 1", "hive", _A_CSV, "a.csv", {}, [], "/tmp/b.csv")
    assert "A샘플과 B실행은 서로 다른 날짜" not in p2


def test_build_prompt_condition_date_subset_states_a_positively():
    """부분집합(A ⊆ B) — 예전 결함 재현 방지: A를 '없음/미상'이 아니라 명시적 조건으로 양성 서술.

    A={20240101} ⊆ B={20240101,20240102} 일 때 프롬프트가 'A만:(없음)'을 렌더하면 LLM 이 'A 조건 없음/
    미상'으로 오서술하던 것을 회귀 단언으로 고정한다."""
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", _A_CSV, "a.csv", {}, [], "/tmp/b.csv",
                      cond_diff={"a_dates": ["20240101"], "b_dates": ["20240101", "20240102"],
                                 "a_ranges": ["created_at: 20240101~20240101"],
                                 "b_ranges": ["sys_cre_dttm: 20240101~20240102"]})
    assert "명시적 날짜 조건" in p
    assert "부분집합" in p
    assert "없음/불명/미상/전체" in p
    assert "created_at: 20240101~20240101" in p     # A 범위를 그대로 노출(양성 서술)
    assert "A만: (없음)" not in p                     # 회귀: A를 '(없음)'으로 렌더하지 않음


def test_build_prompt_condition_a_no_date_filter_branch():
    """A에 날짜 리터럴이 진짜 없고 B에만 있으면 'A: 날짜 미필터' 서술이 옳다(합법 무조건 케이스 보존)."""
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", _A_CSV, "a.csv", {}, [], "/tmp/b.csv",
                      cond_diff={"a_dates": [], "b_dates": ["20240102"],
                                 "a_ranges": [], "b_ranges": ["dt: 20240102~20240102"]})
    assert "날짜 리터럴 조건이 없고" in p
    assert "QUERY" in p and "조건 차이" in p


def test_reconcile_passes_condition_date_diff_to_prompt(monkeypatch, tmp_path):
    """reconcile 가 A(명시 날짜)와 B(바인드 치환) 날짜 차이를 탐지해 cond_diff(dict)로 프롬프트에 전달.

    cond_diff = {"a_dates","b_dates","a_ranges","b_ranges"} — 집합차가 아니라 전체 값+범위(무손실).
    같은 날짜 → None(DATA 귀속 허용). 부분집합(A ⊆ B)도 발화하며 a_dates 를 보존(예전 붕괴 결함 방지).
    """
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: "/usr/bin/claude")
    captured = {}
    real_build = data_reconcile._build_prompt

    def _spy(*a, **k):
        captured["cond_diff"] = k.get("cond_diff")
        return real_build(*a, **k)

    monkeypatch.setattr(data_reconcile, "_build_prompt", _spy)
    monkeypatch.setattr(asyncio, "create_subprocess_exec",
                        _fake_exec(json.dumps({"structured_output": _RECON}).encode("utf-8")))
    sql_a = ("SELECT bank_cd, SUM(amt) AS tot FROM t WHERE dt BETWEEN "
             "to_date('20240101','yyyymmdd') AND to_date('20240101','yyyymmdd') GROUP BY bank_cd")
    sql_b = ("SELECT bank_cd, SUM(amt) AS tot FROM t WHERE dt BETWEEN "
             "to_timestamp('${sd}','yyyyMMdd') AND to_timestamp('${ed}','yyyyMMdd') GROUP BY bank_cd")
    # 서로소: A=20240101, B=20240102
    asyncio.run(reconcile_via_cli(sql_b, Dialect.HIVE, _A_CSV, "a.csv",
                                  {"sd": "20240102", "ed": "20240102"},
                                  op_an=None, out_dir=str(tmp_path),
                                  sql_a=sql_a, dialect_a=Dialect.ORACLE))
    assert captured["cond_diff"]["a_dates"] == ["20240101"]
    assert captured["cond_diff"]["b_dates"] == ["20240102"]
    assert captured["cond_diff"]["a_ranges"] == ["dt: 20240101~20240101"]
    assert captured["cond_diff"]["b_ranges"] == ["dt: 20240102~20240102"]
    # 부분집합(버그 재현): A=20240101 ⊆ B={20240101,20240102} — a_dates 붕괴 없이 보존
    asyncio.run(reconcile_via_cli(sql_b, Dialect.HIVE, _A_CSV, "a.csv",
                                  {"sd": "20240101", "ed": "20240102"},
                                  op_an=None, out_dir=str(tmp_path),
                                  sql_a=sql_a, dialect_a=Dialect.ORACLE))
    assert captured["cond_diff"]["a_dates"] == ["20240101"]
    assert captured["cond_diff"]["b_dates"] == ["20240101", "20240102"]
    assert captured["cond_diff"]["a_ranges"] == ["dt: 20240101~20240101"]
    assert captured["cond_diff"]["b_ranges"] == ["dt: 20240101~20240102"]
    # 같은 날짜 → None(조건 차이 없음 → DATA 귀속 여지)
    asyncio.run(reconcile_via_cli(sql_b, Dialect.HIVE, _A_CSV, "a.csv",
                                  {"sd": "20240101", "ed": "20240101"},
                                  op_an=None, out_dir=str(tmp_path),
                                  sql_a=sql_a, dialect_a=Dialect.ORACLE))
    assert captured["cond_diff"] is None


def test_reconcile_missing_claude_unverifiable(monkeypatch):
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    result = asyncio.run(reconcile_via_cli(_SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None))
    assert result.status == ReconcileStatus.UNVERIFIABLE
    assert "claude CLI" in (result.error or "")


def test_reconcile_nonzero_exit_unverifiable(monkeypatch, tmp_path):
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(b"", returncode=1))
    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None, out_dir=str(tmp_path),
    ))
    assert result.status == ReconcileStatus.UNVERIFIABLE


def test_reconcile_no_structured_unverifiable(monkeypatch, tmp_path):
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: "/usr/bin/claude")
    stdout = json.dumps({"result": "그냥 텍스트, JSON 아님"}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout))
    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None, out_dir=str(tmp_path),
    ))
    assert result.status == ReconcileStatus.UNVERIFIABLE


def test_resolve_binds_prefers_nonempty_default_over_bare():
    # default 있는 형이 뒤의 bare 형에 덮이지 않음
    b = _resolve_binds("a=${p} b=${q=9} c=${p=7}", None)
    assert b == {"p": "7", "q": "9"}
    # provided 가 최우선
    b2 = _resolve_binds("dt BETWEEN ${start_dt=20250501} AND ${end_dt}", {"end_dt": "20260601"})
    assert b2 == {"start_dt": "20250501", "end_dt": "20260601"}
    # SQL 에 없던 provided 도 보존
    assert _resolve_binds("no vars", {"x": "z"}) == {"x": "z"}


def test_reconcile_ignores_commented_bind_filter(monkeypatch):
    """주석 처리된 `${nr_no}` 필터는 2차 실행/바인드에서 제외(R14).

    주석 코드는 실행되지 않으므로, 그 안의 바인드값이 되살아나 B를 필터링하면 안 된다.
    """
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)  # 서브프로세스 없이 단락
    b_commented = "select count(1) c from ods.stlm_ods where 1=1\n--and nr_no = '${nr_no}'"
    r = asyncio.run(reconcile_via_cli(
        b_commented, Dialect.HIVE, "c\n1\n", "a.csv", {"nr_no": "KMN0000424460824"},
    ))
    assert r.binds_used == {}                                    # 주석 leftover 제외
    # 대비(회귀): 활성 필터면 바인드 그대로 적용
    b_active = "select count(1) c from ods.stlm_ods where 1=1 and nr_no = '${nr_no}'"
    r2 = asyncio.run(reconcile_via_cli(
        b_active, Dialect.HIVE, "c\n1\n", "a.csv", {"nr_no": "KMN0000424460824"},
    ))
    assert r2.binds_used == {"nr_no": "KMN0000424460824"}


def test_column_map_hints_filters_by_sql_and_renames_only():
    class _M:
        columns = {
            "IAS_MC.PAR": {"an_table": "IAS_MC", "an_col": "PAR_NO"},   # 이름 다름 + SQL 등장
            "IAS_MC.AMT": {"an_table": "IAS_MC", "an_col": "AMT"},       # 동일명 → 제외
            "OTHER.ZZZ": {"an_table": "OTHER", "an_col": "ZZZ_NO"},      # SQL 미등장 → 제외
        }
    hints = _column_map_hints(_M(), "SELECT PAR_NO FROM ias_mc")
    assert any("PAR" in h and "PAR_NO" in h for h in hints)
    assert all("AMT" not in h for h in hints)
    assert all("ZZZ" not in h for h in hints)
    assert _column_map_hints(None, "SELECT 1") == []


def test_data_reconcile_schema_is_compliant():
    def check(node):
        t = node.get("type")
        if t == "object":
            assert node.get("additionalProperties") is False
            props = set(node["properties"])
            assert set(node["required"]) == props, node
            for v in node["properties"].values():
                check(v)
        elif t == "array":
            check(node["items"])

    check(AI_DATA_RECONCILE_SCHEMA)


def test_ai_data_reconcile_to_data_reconcile():
    ai = AiDataReconcile.model_validate(_RECON)
    dr = ai.to_data_reconcile(binds={"start_dt": "20250501"}, a_sample_name="a.csv")
    assert dr.status == ReconcileStatus.MISMATCH
    assert dr.binds_used == {"start_dt": "20250501"}
    assert dr.a_sample_name == "a.csv"
    assert dr.mismatches[0].value_b == "180"


# --- 엔드포인트 배선 ---

def _setup_ready(sql_a, sql_b):
    cid = client.post("/api/comparisons").json()["id"]
    client.put(f"/api/comparisons/{cid}/query-a", json={"sql_raw": sql_a, "dialect": "oracle"})
    client.put(f"/api/comparisons/{cid}/query-b", json={"sql_raw": sql_b, "dialect": "hive"})
    client.post(f"/api/comparisons/{cid}/validate")
    return cid


def test_sample_a_upload_endpoint():
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    r = client.put(f"/api/comparisons/{cid}/sample-a",
                   json={"csv": _A_CSV, "filename": "a.csv",
                         "binds_a": {"nr_number": "K"}, "binds_b": {"start_dt": "20250501"}})
    assert r.status_code == 200
    body = r.json()
    assert body["sample_a_csv"] == _A_CSV
    assert body["sample_a_filename"] == "a.csv"
    assert body["sample_binds_a"] == {"nr_number": "K"}
    assert body["sample_binds_b"] == {"start_dt": "20250501"}


def test_sample_a_csv_download_endpoint():
    """GET /sample-a.csv — 저장된 A 샘플 원문 서빙(2차 대조 화면 A|B 표 렌더용). 없으면 404."""
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    # 업로드 전 → 404
    assert client.get(f"/api/comparisons/{cid}/sample-a.csv").status_code == 404
    client.put(f"/api/comparisons/{cid}/sample-a", json={"csv": _A_CSV, "filename": "a.csv"})
    r = client.get(f"/api/comparisons/{cid}/sample-a.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text == _A_CSV
    # 제거 후 → 404
    client.put(f"/api/comparisons/{cid}/sample-a", json={"csv": None})
    assert client.get(f"/api/comparisons/{cid}/sample-a.csv").status_code == 404


def test_sample_a_clear_via_explicit_null():
    """파일 제거 → 프런트가 csv=null PUT → 서버가 이전 샘플을 비운다(재실행 시 stale 사용 금지)."""
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"csv": _A_CSV, "filename": "a.csv", "binds_b": {"start_dt": "20250501"}})
    assert client.get(f"/api/comparisons/{cid}").json()["sample_a_csv"] == _A_CSV
    # 명시적 null → clear
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"csv": None, "filename": None, "binds_b": {}})
    body = client.get(f"/api/comparisons/{cid}").json()
    assert body["sample_a_csv"] is None
    assert body["sample_a_filename"] is None
    assert body["sample_binds_b"] == {}


def test_sample_a_omitted_field_unchanged():
    """명시 안 한 필드는 불변(부분 업데이트 보존) — null 명시와 구분."""
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    client.put(f"/api/comparisons/{cid}/sample-a", json={"csv": _A_CSV, "filename": "a.csv"})
    client.put(f"/api/comparisons/{cid}/sample-a", json={"binds_b": {"x": "1"}})  # csv 생략
    body = client.get(f"/api/comparisons/{cid}").json()
    assert body["sample_a_csv"] == _A_CSV          # 생략 → 불변
    assert body["sample_binds_b"] == {"x": "1"}


def test_execute_ai_kill_switch_skips_reconcile(monkeypatch):
    """QD_RECON_ENABLED=0 이면 2차 미수행 → data_reconcile is None (현행 1차만)."""
    from query_diff.ai_diff import cli_runner
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)   # 1차도 CLI 없음(빠름)
    monkeypatch.setenv("QD_RECON_ENABLED", "0")
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    r = client.post(f"/api/comparisons/{cid}/execute-ai")
    assert r.status_code == 200
    assert r.json()["data_reconcile"] is None


def test_execute_ai_runs_reconcile_when_enabled(monkeypatch):
    """활성(기본) 시 모든 경우 2차 동작. CLI 부재면 data_reconcile=UNVERIFIABLE(500 아님)."""
    from query_diff.ai_diff import cli_runner
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    monkeypatch.delenv("QD_RECON_ENABLED", raising=False)
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    r = client.post(f"/api/comparisons/{cid}/execute-ai")
    assert r.status_code == 200
    body = r.json()
    assert body["data_reconcile"] is not None
    assert body["data_reconcile"]["status"] == "UNVERIFIABLE"


# --- 종합 판정(final_*) ---

def test_data_reconcile_schema_includes_final_fields():
    props = set(AI_DATA_RECONCILE_SCHEMA["properties"])
    for k in ("final_verdict", "final_confidence", "final_reason", "attribution"):
        assert k in props and k in AI_DATA_RECONCILE_SCHEMA["required"]


def test_to_data_reconcile_maps_final():
    ai = AiDataReconcile.model_validate({
        **_RECON,
        "final_verdict": "DIFFERENT", "final_confidence": "HIGH",
        "final_reason": "구조는 동치인데 값 상이 → 데이터 차이", "attribution": "DATA",
    })
    dr = ai.to_data_reconcile()
    assert dr.final_verdict == FinalVerdict.DIFFERENT
    assert dr.final_confidence == Confidence.HIGH
    assert dr.attribution == Attribution.DATA
    assert "데이터 차이" in dr.final_reason


def test_final_from_base_mapping():
    from query_diff.ai_diff.data_reconcile import _final_from_base
    assert _final_from_base({"verdict": "EQUIVALENT"})["final_verdict"] == FinalVerdict.SAME
    assert _final_from_base({"verdict": "DIVERGENT"})["final_verdict"] == FinalVerdict.DIFFERENT
    assert _final_from_base({"verdict": "LIMITED"})["final_verdict"] == FinalVerdict.INCONCLUSIVE
    assert _final_from_base(None)["final_verdict"] == FinalVerdict.INCONCLUSIVE
    assert _final_from_base({"verdict": "EQUIVALENT"})["final_confidence"] == Confidence.LOW


def test_reconcile_unverifiable_inherits_final_from_base(monkeypatch):
    """AI 대조 불가(claude 부재)라도 종합 판정은 1차를 결정적으로 승계(배너 비지 않게)."""
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    dr = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None,
        base_semantic={"verdict": "EQUIVALENT", "dimensions": []},
    ))
    assert dr.status == ReconcileStatus.UNVERIFIABLE
    assert dr.final_verdict == FinalVerdict.SAME
    assert dr.final_confidence == Confidence.LOW


def test_build_prompt_has_synthesis_rubric_and_base():
    from query_diff.ai_diff.data_reconcile import _build_prompt, _format_base
    base = _format_base({"verdict": "DIVERGENT",
                         "dimensions": [{"dimension": "PREDICATES", "matched": False}]})
    p = _build_prompt("SELECT 1", "hive", "c,v\n1,2", "a.csv",
                      {"start_dt": "20250501"}, [], "/tmp/b.csv", base)
    assert "종합 판정" in p
    assert "1차 정적 판정 요약" in p
    assert "DIVERGENT" in p                     # base 요약 주입
    assert "INCONCLUSIVE" in p                  # 비대칭 루브릭(DIVERGENT+MATCH→INCONCLUSIVE)
    assert "attribution" in p


def test_format_base_surfaces_diverging_filters():
    """불일치 차원은 A만/B만 구체 필터를 노출 — LLM 이 '동일 조건 대조' 오서술 안 하도록(R15)."""
    from query_diff.ai_diff.data_reconcile import _format_base
    base = _format_base({
        "verdict": "DIVERGENT",
        "dimensions": [
            {"dimension": "PREDICATES", "matched": False,
             "only_in_a": ["IAS_TRANSACTION.MTI != '0120'"],
             "only_in_b": ["STLM_ODS.NR_NO = 'KMN0000424460824'"]},
            {"dimension": "AGGREGATES", "matched": True,
             "only_in_a": [], "only_in_b": [], "shared": ["x"]},
        ],
    })
    assert "A만: IAS_TRANSACTION.MTI != '0120'" in base
    assert "B만: STLM_ODS.NR_NO = 'KMN0000424460824'" in base
    # 일치 차원엔 A만/B만 안 붙음
    assert base.count("A만:") == 1


def test_build_prompt_condition_asymmetry_instruction():
    """프롬프트에 활성 필터 비대칭 → '동일 조건 대조' 서술 금지 지시가 포함(R15)."""
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", "c,v\n1,2", "a.csv", {"nr_no": "KMN"}, [], "/tmp/b.csv")
    assert "조건 정합성" in p
    assert "동일 조건으로 대조" in p          # 금지 문구
    assert "동치 근거가 아님" in p


def test_build_prompt_trusts_a_sample():
    """업로드 A샘플을 A쿼리 결과로 신뢰하도록 지시 — provenance 의심 프레이밍 금지(R16)."""
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", "c,v\n1,2", "a.csv", {"nr_no": "KMN"}, [], "/tmp/b.csv")
    assert "A샘플 신뢰 전제" in p
    assert "의심하지 마라" in p
    # 불확정 사유는 '쿼리 조건이 다르다'로 서술(샘플 불신 아님)
    assert "쿼리 조건이 다르다" in p
    # 바인드블록이 'A샘플을 뽑은 조건과 동일해야'라는 의심 전제를 더는 심지 않음
    assert "A샘플을 뽑은 조건과 동일해야" not in p


# --- 컬럼 정합 검증(업로드 파일이 쿼리 결과인지) ---

def test_output_columns_and_csv_header():
    from query_diff.ai_diff.data_reconcile import _output_columns, _csv_header
    assert _output_columns("SELECT bank_cd, SUM(org_amt) AS org_amt FROM t GROUP BY bank_cd",
                           "oracle") == ["bank_cd", "org_amt"]
    assert _output_columns("SELECT * FROM t", "oracle") is None       # * → 확정 불가
    assert _output_columns("!!! not sql", "oracle") is None            # 파싱 실패
    assert _csv_header("BANK_CD,ORG_AMT\nBANK01,5000") == ["bank_cd", "org_amt"]  # 대소문자 정규화
    assert _csv_header("﻿a;b\n1;2") == ["a", "b"]                       # BOM + 세미콜론
    assert _csv_header("") is None


def test_reconcile_column_mismatch_short_circuits(monkeypatch):
    """A쿼리는 org_amt 산출, 업로드 CSV는 tr_amt → 결정적 단락: UNVERIFIABLE + INCONCLUSIVE(SAME 아님)."""
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)  # 게이트가 먼저 단락돼야
    q_a = "SELECT bank_cd, SUM(org_amt) AS org_amt FROM ias.tx GROUP BY bank_cd"
    dr = asyncio.run(reconcile_via_cli(
        "SELECT bank_cd, SUM(org_amt) AS org_amt FROM b GROUP BY bank_cd", Dialect.HIVE,
        "bank_cd,tr_amt\nBANK01,5000\n", "a.csv", None,
        sql_a=q_a, dialect_a=Dialect.ORACLE,
    ))
    assert dr.status == ReconcileStatus.UNVERIFIABLE
    assert dr.final_verdict == FinalVerdict.INCONCLUSIVE     # 절대 SAME 아님
    assert dr.error == "sample columns do not match query output columns"
    assert "org_amt" in dr.final_reason and "tr_amt" in dr.final_reason


def test_reconcile_column_match_proceeds_past_gate(monkeypatch):
    """컬럼이 일치하면 게이트를 통과해 CLI 경로로 진행(여기선 claude 부재 → 다른 사유의 UNVERIFIABLE)."""
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    q_a = "SELECT bank_cd, SUM(org_amt) AS org_amt FROM ias.tx GROUP BY bank_cd"
    dr = asyncio.run(reconcile_via_cli(
        "SELECT bank_cd, SUM(org_amt) AS org_amt FROM b GROUP BY bank_cd", Dialect.HIVE,
        "bank_cd,org_amt\nBANK01,5000\n", "a.csv", None,
        sql_a=q_a, dialect_a=Dialect.ORACLE,
    ))
    assert dr.status == ReconcileStatus.UNVERIFIABLE
    assert "claude CLI" in (dr.error or "")                  # 컬럼 단락 아님(게이트 통과)


def test_column_mismatch_detects_extra_column():
    """엄격 집합 동일: 쿼리는 org_amt만 내는데 파일에 여분 tr_amt → 미스매치(extra)."""
    from query_diff.ai_diff.data_reconcile import _column_provenance_mismatch
    q = "SELECT bank_cd, SUM(org_amt) AS org_amt FROM t GROUP BY bank_cd"
    mm = _column_provenance_mismatch(q, "oracle", "bank_cd,org_amt,tr_amt\nBANK01,5000,1000\n")
    assert mm is not None
    _q, _h, missing, extra = mm
    assert missing == [] and extra == ["tr_amt"]
    # 정확히 일치 → None
    assert _column_provenance_mismatch(q, "oracle", "bank_cd,org_amt\nBANK01,5000\n") is None
    # 이름 못 정하는 집계 식(SUM(a+b)) 섞임 → unreliable → complete=False → 여분 검사 생략(오탐 방지)
    assert _column_provenance_mismatch("SELECT bank_cd, SUM(org_amt + tr_amt) FROM t GROUP BY bank_cd",
                                       "oracle", "bank_cd,org_amt,tr_amt\n1,2,3") is None


def test_unaliased_aggregate_accept_tokens():
    """라운드7: 무별칭 집계 CSV 헤더는 export 규약마다 다르므로 표현식 원문(`count(org_amt)`)과
    인자 컬럼(`org_amt`) 을 **둘 다 허용**한다(accept-token). 함수 식별은 유지(avg≠count)."""
    from query_diff.ai_diff.data_reconcile import _column_provenance_mismatch, _output_columns

    # 표시명 = 표현식 원문/별칭/컬럼
    assert _output_columns("SELECT sum(org_amt) FROM ias.tx", "oracle") == ["sum(org_amt)"]
    assert _output_columns("SELECT max(a.org_amt) FROM ias.tx a", "oracle") == ["max(org_amt)"]
    assert _output_columns("SELECT count(*) FROM t", "oracle") == ["count(*)"]
    assert _output_columns("SELECT count(org_amt), sum(org_amt) FROM t", "oracle") == \
        ["count(org_amt)", "sum(org_amt)"]
    assert _output_columns("SELECT bank_cd, SUM(org_amt) AS org_amt FROM t GROUP BY bank_cd",
                           "oracle") == ["bank_cd", "org_amt"]
    assert _output_columns("SELECT * FROM t", "oracle") is None

    # 사용자 실제 케이스: Impala export 표현식 헤더(탭 구분) → 정합(None)
    q2 = "SELECT count(org_amt), sum(org_amt) FROM ias.tx"
    assert _column_provenance_mismatch(q2, "oracle", "count(org_amt)\tsum(org_amt)\n1\t5000\n") is None

    # 단일 집계: 표현식 헤더·인자 헤더 둘 다 정합
    q = "SELECT sum(org_amt) FROM ias.tx"
    assert _column_provenance_mismatch(q, "oracle", "sum(org_amt)\n5000\n") is None   # 표현식 원문
    assert _column_provenance_mismatch(q, "oracle", "org_amt\n5000\n") is None        # 인자 컬럼

    # 틀린 파일 차단 유지(라운드3/4)
    mm_missing = _column_provenance_mismatch(q, "oracle", "tr_amt\n5000\n")
    assert mm_missing is not None and mm_missing[2] == ["sum(org_amt)"]               # missing(표시명)
    mm_extra = _column_provenance_mismatch(q, "oracle", "org_amt,tr_amt\n5000,1000\n")
    assert mm_extra is not None and mm_extra[3] == ["tr_amt"]                         # extra

    # 함수 식별 유지: 파일이 avg 인데 쿼리는 count → 차단(단순 인자환원이면 놓침)
    mm_fn = _column_provenance_mismatch(q2, "oracle", "avg(org_amt),sum(org_amt)\n1,2\n")
    assert mm_fn is not None and "avg(org_amt)" in mm_fn[3]


def test_reconcile_unaliased_aggregate_proceeds_past_gate(monkeypatch):
    """무별칭 집계 + 다양한 export 헤더 → 컬럼 단락 아님(게이트 통과).

    (라운드6) 단일 sum(org_amt) + CSV org_amt(인자 헤더).
    (라운드7) count(org_amt),sum(org_amt) + Impala 탭 구분 표현식 헤더.
    """
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)

    def _gate_passed(sql_a, csv):
        dr = asyncio.run(reconcile_via_cli(
            "SELECT sum(gm_tr_amt) FROM ods.stlm_ods WHERE nr_no = 'K'", Dialect.HIVE,
            csv, "a.csv", None, sql_a=sql_a, dialect_a=Dialect.ORACLE,
        ))
        assert dr.status == ReconcileStatus.UNVERIFIABLE
        assert dr.error != "sample columns do not match query output columns"  # 컬럼 단락 아님
        assert "claude CLI" in (dr.error or "")                                 # 게이트 통과 후 CLI 부재

    _gate_passed("SELECT sum(org_amt) FROM ias.ias_transaction WHERE nr_number = 'K'",
                 "org_amt\n5000\n")
    _gate_passed("SELECT count(org_amt), sum(org_amt) FROM ias.ias_transaction WHERE nr_number = 'K'",
                 "count(org_amt)\tsum(org_amt)\n1\t5000\n")


def test_reconcile_extra_column_short_circuits(monkeypatch):
    """A쿼리 org_amt + 파일에 여분 tr_amt → 결정적 단락: UNVERIFIABLE + INCONCLUSIVE, 여분 컬럼 명시."""
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    q_a = "SELECT bank_cd, SUM(org_amt) AS org_amt FROM ias.tx GROUP BY bank_cd"
    dr = asyncio.run(reconcile_via_cli(
        "SELECT bank_cd, SUM(org_amt) AS org_amt FROM b GROUP BY bank_cd", Dialect.HIVE,
        "bank_cd,org_amt,tr_amt\nBANK01,5000,1000\n", "a.csv", None,
        sql_a=q_a, dialect_a=Dialect.ORACLE,
    ))
    assert dr.status == ReconcileStatus.UNVERIFIABLE
    assert dr.final_verdict == FinalVerdict.INCONCLUSIVE
    assert dr.error == "sample columns do not match query output columns"
    assert "tr_amt" in dr.headline                           # 여분 컬럼 명시


def test_build_prompt_has_column_consistency():
    from query_diff.ai_diff.data_reconcile import _build_prompt
    p = _build_prompt("SELECT 1", "hive", "bank_cd,tr_amt\n1,2", "a.csv", {}, [], "/tmp/b.csv",
                      "", ["bank_cd", "org_amt"], ["bank_cd", "tr_amt"])
    assert "[컬럼 정합성]" in p
    assert "org_amt" in p and "tr_amt" in p
    assert "동치(SAME)로 판정하지 말고" in p


def test_execute_ai_column_mismatch_not_same(monkeypatch):
    """엔드포인트: A쿼리 org_amt + 업로드 tr_amt → data_reconcile 이 INCONCLUSIVE(동치 아님)."""
    from query_diff.ai_diff import cli_runner
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)      # 1차 빠름
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)
    monkeypatch.delenv("QD_RECON_ENABLED", raising=False)
    cid = _setup_ready("SELECT bank_cd, SUM(org_amt) AS org_amt FROM ias.tx GROUP BY bank_cd",
                       "SELECT bank_cd, SUM(org_amt) AS org_amt FROM b GROUP BY bank_cd")
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"csv": "bank_cd,tr_amt\nBANK01,5000\n", "filename": "a.csv", "binds_b": {}})
    dr = client.post(f"/api/comparisons/{cid}/execute-ai").json()["data_reconcile"]
    assert dr["status"] == "UNVERIFIABLE"
    assert dr["final_verdict"] == "INCONCLUSIVE"             # false 동치 차단
    assert dr["error"] == "sample columns do not match query output columns"


def test_execute_ai_data_reconcile_has_final(monkeypatch):
    """엔드포인트: 2차가 UNVERIFIABLE 이어도 final_verdict 는 1차 승계로 채워짐."""
    from query_diff.ai_diff import cli_runner
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)      # 1차 → LIMITED
    monkeypatch.setattr(data_reconcile, "_find_claude", lambda: None)  # 2차 → UNVERIFIABLE
    monkeypatch.delenv("QD_RECON_ENABLED", raising=False)
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    dr = client.post(f"/api/comparisons/{cid}/execute-ai").json()["data_reconcile"]
    assert dr["status"] == "UNVERIFIABLE"
    assert dr["final_verdict"] == "INCONCLUSIVE"   # 1차 LIMITED 승계


# --- 바인드값 A/B 분리 + 1차 값 치환(라운드12) ---

def test_apply_binds_substitution():
    """_apply_binds: Oracle `:name`·Hue `${name}` 를 제공값으로 치환(따옴표/숫자/미제공 처리)."""
    from query_diff.validation_service import _apply_binds
    assert _apply_binds("x = :p", {"p": "'K'"}) == "x = 'K'"          # :name, 따옴표값
    assert _apply_binds("x = :p", {"p": "K"}) == "x = 'K'"            # :name, 무따옴표 → 인용
    assert _apply_binds("x = '${p}'", {"p": "'K'"}) == "x = 'K'"      # ${} 따옴표 안, 값따옴표 제거
    assert _apply_binds("x = '${p}'", {"p": "K"}) == "x = 'K'"        # ${} 따옴표 안
    assert _apply_binds("dt >= :d", {"d": "20250101"}) == "dt >= 20250101"   # 숫자 bare
    assert _apply_binds("x = :p and y = '${q}'", {}) == "x = :p and y = '${q}'"  # 미제공 → 원문
    assert _apply_binds("x::text = :p", {"p": "5"}) == "x::text = 5"  # 캐스트 보존


def test_execute_binds_substituted_in_first_pass():
    """/execute 1차: A `:p`·B `${q}` 를 각 바인드값으로 치환 후 비교.
    동일값 → PREDICATES matched, 다른값 → 상이(사용자 목적)."""
    def _pred(cid):
        sem = client.post(f"/api/comparisons/{cid}/execute").json()["semantic_diff"]
        return next(d for d in sem["dimensions"] if d["dimension"] == "PREDICATES")["matched"]

    # 같은 베이스 테이블 t — 한정자/ODS 개입 없이 값 치환 자체를 검증
    cid = _setup_ready("SELECT c FROM t WHERE k = :p", "SELECT c FROM t WHERE k = '${q}'")
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"binds_a": {"p": "'X'"}, "binds_b": {"q": "'X'"}})
    assert _pred(cid) is True          # 동일 값 → 일치

    cid2 = _setup_ready("SELECT c FROM t WHERE k = :p", "SELECT c FROM t WHERE k = '${q}'")
    client.put(f"/api/comparisons/{cid2}/sample-a",
               json={"binds_a": {"p": "'X'"}, "binds_b": {"q": "'Y'"}})
    assert _pred(cid2) is False         # 다른 값 → 상이
