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
    # 서버 지정 경로에 파일이 실제로 존재하면 그 경로를 노출
    (tmp_path / "b_sample.csv").write_text("bank_cd,tot\nBANK01,100\n", encoding="utf-8")
    stdout = json.dumps({"structured_output": _RECON}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout))
    result = asyncio.run(reconcile_via_cli(
        _SQL_B, Dialect.HIVE, _A_CSV, "a.csv", None, op_an=None, out_dir=str(tmp_path),
    ))
    assert result.b_csv_path == str(tmp_path / "b_sample.csv")


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
                   json={"csv": _A_CSV, "filename": "a.csv", "binds": {"start_dt": "20250501"}})
    assert r.status_code == 200
    body = r.json()
    assert body["sample_a_csv"] == _A_CSV
    assert body["sample_a_filename"] == "a.csv"
    assert body["sample_binds"] == {"start_dt": "20250501"}


def test_sample_a_clear_via_explicit_null():
    """파일 제거 → 프런트가 csv=null PUT → 서버가 이전 샘플을 비운다(재실행 시 stale 사용 금지)."""
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"csv": _A_CSV, "filename": "a.csv", "binds": {"start_dt": "20250501"}})
    assert client.get(f"/api/comparisons/{cid}").json()["sample_a_csv"] == _A_CSV
    # 명시적 null → clear
    client.put(f"/api/comparisons/{cid}/sample-a",
               json={"csv": None, "filename": None, "binds": {}})
    body = client.get(f"/api/comparisons/{cid}").json()
    assert body["sample_a_csv"] is None
    assert body["sample_a_filename"] is None
    assert body["sample_binds"] == {}


def test_sample_a_omitted_field_unchanged():
    """명시 안 한 필드는 불변(부분 업데이트 보존) — null 명시와 구분."""
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    client.put(f"/api/comparisons/{cid}/sample-a", json={"csv": _A_CSV, "filename": "a.csv"})
    client.put(f"/api/comparisons/{cid}/sample-a", json={"binds": {"x": "1"}})  # csv 생략
    body = client.get(f"/api/comparisons/{cid}").json()
    assert body["sample_a_csv"] == _A_CSV          # 생략 → 불변
    assert body["sample_binds"] == {"x": "1"}


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
    from query_diff.ai_diff.data_reconcile import _column_provenance_mismatch, _named_output_cols
    q = "SELECT bank_cd, SUM(org_amt) AS org_amt FROM t GROUP BY bank_cd"
    mm = _column_provenance_mismatch(q, "oracle", "bank_cd,org_amt,tr_amt\nBANK01,5000,1000\n")
    assert mm is not None
    _q, _h, missing, extra = mm
    assert missing == [] and extra == ["tr_amt"]
    # 정확히 일치 → None
    assert _column_provenance_mismatch(q, "oracle", "bank_cd,org_amt\nBANK01,5000\n") is None
    # 무별칭 집계 → complete=False → 여분 검사 생략(오탐 방지)
    assert _named_output_cols("SELECT bank_cd, SUM(org_amt) FROM t GROUP BY bank_cd", "oracle")[1] is False
    assert _column_provenance_mismatch("SELECT bank_cd, SUM(org_amt) FROM t GROUP BY bank_cd",
                                       "oracle", "bank_cd,org_amt,tr_amt\n1,2,3") is None


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
               json={"csv": "bank_cd,tr_amt\nBANK01,5000\n", "filename": "a.csv", "binds": {}})
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
