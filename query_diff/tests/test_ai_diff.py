"""AI 비교 경로(ai_diff, claude -p 단일-샷 판정) 단위 테스트 — 구독·CLI·네트워크 없이 동작(모킹).

- compare_via_cli: 내부 compare_semantic(실제) 후 mocked claude subprocess 의 structured_output → SemanticDiff
- 구독 인증 강제: 자식 env 에서 ANTHROPIC_API_KEY 제거 확인
- claude 미설치/비정상종료/미구조화 → LIMITED
- 엔드포인트가 CLI 부재에도 500 아닌 LIMITED(200)
- _ods_context: QD_ODS_DIR 의 ODS_<T>.sql 을 참조 SQL 로부터 선로딩
- 구조화 출력 스키마 제약 준수
"""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from query_diff.ai_diff import cli_runner
from query_diff.ai_diff.cli_runner import _compact, _ods_context, compare_via_cli
from query_diff.ai_diff.schema import (
    AI_SEMANTIC_DIFF_SCHEMA,
    AiDimensionResult,
    AiSemanticDiff,
)
from query_diff.api import app
from query_diff.models import Dialect, DimensionName, SemanticVerdict

client = TestClient(app)

_A = "SELECT status, SUM(amt) AS total FROM tx WHERE status = 'Y' GROUP BY status"
_B = "SELECT status, SUM(amt) AS total FROM tx GROUP BY status"


class _FakeProc:
    def __init__(self, stdout=b"", stderr=b"", returncode=0):
        self._stdout, self._stderr, self.returncode = stdout, stderr, returncode

    async def communicate(self, input=None):  # noqa: A002 — subprocess API 시그니처
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
            captured["cwd"] = kwargs.get("cwd")
        return _FakeProc(stdout=stdout_bytes, returncode=returncode)

    return _exec


_SAMPLE = {
    "verdict": "DIVERGENT",
    "reason": "필터 조건이 다릅니다.",
    "issues": ["필터 조건 (WHERE/HAVING): A에만 STATUS='Y'"],
    "dimensions": [
        {
            "dimension": "PREDICATES",
            "matched": False,
            "limited": False,
            "only_in_a": ["STATUS = 'Y'"],
            "only_in_b": [],
            "shared": [],
            "explanation": "A에만 상태 필터",
            "caveat": "",
        }
    ],
    "limitations": [],
}


def test_compare_via_cli_maps_structured_output(monkeypatch):
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "should-be-stripped")
    captured: dict = {}
    stdout = json.dumps({"structured_output": _SAMPLE, "total_cost_usd": 0}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout, captured=captured))

    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _B, Dialect.HIVE))

    assert result.verdict == SemanticVerdict.DIVERGENT
    assert result.plan_a is None and result.plan_b is None
    dims = {d.dimension: d for d in result.dimensions}
    assert dims[DimensionName.PREDICATES].only_in_a == ["STATUS = 'Y'"]
    # 구독 인증 강제: 자식 env 에 ANTHROPIC_API_KEY 없어야
    assert "ANTHROPIC_API_KEY" not in (captured["env"] or {})


def test_compare_via_cli_result_fallback(monkeypatch):
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: "/usr/bin/claude")
    stdout = json.dumps({"result": json.dumps(_SAMPLE)}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout))
    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _B, Dialect.HIVE))
    assert result.verdict == SemanticVerdict.DIVERGENT


def test_compare_via_cli_result_fenced(monkeypatch):
    """result 가 ```json 펜스로 감싸여도(구조화 채널 누락) 복구."""
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: "/usr/bin/claude")
    fenced = "여기 결과입니다:\n```json\n" + json.dumps(_SAMPLE) + "\n```\n이상입니다."
    stdout = json.dumps({"result": fenced, "stop_reason": "end_turn"}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout))
    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _B, Dialect.HIVE))
    assert result.verdict == SemanticVerdict.DIVERGENT


def test_parse_json_loose():
    from query_diff.ai_diff.cli_runner import _parse_json_loose

    assert _parse_json_loose('{"a": 1}') == {"a": 1}
    assert _parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    assert _parse_json_loose('설명:\n{"a": {"b": 2}}\n끝') == {"a": {"b": 2}}
    assert _parse_json_loose('중괄호 문자열 {"s": "x } y"} 뒤') == {"s": "x } y"}
    assert _parse_json_loose("그냥 설명, JSON 없음") is None
    assert _parse_json_loose("") is None


def test_compare_via_cli_missing_claude_is_limited(monkeypatch):
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)
    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _A, Dialect.HIVE))
    assert result.verdict == SemanticVerdict.LIMITED
    assert "claude CLI" in (result.error or "")


def test_compare_via_cli_nonzero_exit_is_limited(monkeypatch):
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: "/usr/bin/claude")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(b"", returncode=1))
    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _A, Dialect.HIVE))
    assert result.verdict == SemanticVerdict.LIMITED


def test_compare_via_cli_no_structured_is_limited(monkeypatch):
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: "/usr/bin/claude")
    stdout = json.dumps({"result": "그냥 텍스트, JSON 아님"}).encode("utf-8")
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_exec(stdout))
    result = asyncio.run(compare_via_cli(_A, Dialect.ORACLE, _A, Dialect.HIVE))
    assert result.verdict == SemanticVerdict.LIMITED


def test_ods_context_loads_def(monkeypatch, tmp_path):
    ods_dir = tmp_path / "ods"
    ods_dir.mkdir()
    (ods_dir / "ODS_FOO_AGG.sql").write_text(
        "insert into table ods.foo_agg\nSELECT x, SUM(y) FROM src.bar GROUP BY x",
        encoding="utf-8",
    )
    monkeypatch.setenv("QD_ODS_DIR", str(ods_dir))
    ctx, truncated = _ods_context("SELECT * FROM ods.foo_agg", "SELECT 1")
    assert "foo_agg" in ctx
    assert "src.bar" in ctx["foo_agg"]
    assert truncated is False


def test_ods_context_recurses_ods_to_ods(monkeypatch, tmp_path):
    """ODS→ODS 다단계: foo_agg 정의가 ods.bar_ods 참조 → bar_ods 도 로드."""
    ods_dir = tmp_path / "ods"
    ods_dir.mkdir()
    (ods_dir / "ODS_FOO_AGG.sql").write_text(
        "insert into table ods.foo_agg\nSELECT x FROM ods.bar_ods GROUP BY x", encoding="utf-8"
    )
    (ods_dir / "ODS_BAR_ODS.sql").write_text(
        "insert into table ods.bar_ods\nSELECT x FROM ias.raw WHERE mti != '0120'", encoding="utf-8"
    )
    monkeypatch.setenv("QD_ODS_DIR", str(ods_dir))
    ctx, truncated = _ods_context("SELECT * FROM ods.foo_agg", "")
    assert set(ctx) == {"foo_agg", "bar_ods"}  # 2단계 재귀
    assert "ias.raw" in ctx["bar_ods"]
    assert truncated is False


def test_ods_context_truncation_flag(monkeypatch, tmp_path):
    ods_dir = tmp_path / "ods"
    ods_dir.mkdir()
    (ods_dir / "ODS_FOO_AGG.sql").write_text("x" * 5000, encoding="utf-8")
    monkeypatch.setenv("QD_ODS_DIR", str(ods_dir))
    monkeypatch.setattr(cli_runner, "_ODS_MAX_CHARS", 100)
    ctx, truncated = _ods_context("SELECT * FROM ods.foo_agg", "")
    assert truncated is True
    assert len(ctx["foo_agg"]) <= 100


def test_ods_context_empty_without_dir(monkeypatch):
    monkeypatch.delenv("QD_ODS_DIR", raising=False)
    assert _ods_context("SELECT * FROM ods.foo", "SELECT 1") == ({}, False)


def test_compact_shape():
    base = compare_via_cli  # noqa: F841 — keep import used
    from query_diff.semantic_diff import compare_semantic

    sd = compare_semantic(_A, Dialect.ORACLE, _B, Dialect.HIVE)
    c = _compact(sd)
    assert set(c) == {"verdict", "reason", "issues", "dimensions", "limitations"}
    assert "plan_a" not in c and "structure" not in c
    assert all(set(d) == {"dimension", "matched", "limited", "only_in_a", "only_in_b",
                          "shared", "explanation", "caveat"} for d in c["dimensions"])


def test_ai_semantic_diff_to_semantic_diff():
    ai = AiSemanticDiff(
        verdict=SemanticVerdict.EQUIVALENT,
        reason="동일",
        dimensions=[AiDimensionResult(dimension=DimensionName.BASE_TABLES, matched=True)],
    )
    sd = ai.to_semantic_diff()
    assert sd.verdict == SemanticVerdict.EQUIVALENT
    assert sd.plan_a is None and sd.plan_b is None
    assert sd.dimensions[0].dimension == DimensionName.BASE_TABLES


def test_structured_output_schema_is_compliant():
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

    check(AI_SEMANTIC_DIFF_SCHEMA)


def test_build_prompt_has_decision_rubric():
    """루브릭 회귀 가드: verdict 결정 규칙 문구가 프롬프트에 있어야(실행 간 변동 축소).

    데이터-의존 위험(INNER JOIN 행 누락·nvl NULL→0 등)은 항상 LIMITED 로, 확정 실차이만
    DIVERGENT 로 가는 상호배타 규칙 + 차원 귀속 규칙이 프롬프트에 명문화됐는지 확인한다.
    """
    from query_diff.ai_diff.cli_runner import _build_prompt

    compact = {
        "verdict": "DIVERGENT", "reason": "", "issues": [], "limitations": [], "dimensions": [],
    }
    prompt = _build_prompt("SELECT 1", "SELECT 1", "oracle", "hive", compact, {}, False)
    # 상호배타 결정 규칙의 핵심 문구
    assert "상호배타" in prompt
    assert "데이터-의존 위험" in prompt
    assert "확정 실차이" in prompt
    # 데이터-의존 위험은 LIMITED (DIVERGENT 아님)
    assert "DIVERGENT 아님" in prompt
    # 차원 귀속 규칙(⚠/✓ 셔플 제거) — 위험은 BASE_TABLES, JOIN_GRAPH 는 최상위 조인만
    assert "BASE_TABLES" in prompt
    assert "JOIN_GRAPH" in prompt
    # 2라운드: 차원 matched(✓) vs 제한(⚠) 플래그 값 자체를 규칙으로 고정
    assert "자기 차원" in prompt          # 자기 차원 위험이 있을 때만 limited=true
    assert "PROJECTIONS" in prompt        # nvl → PROJECTIONS 항상 ⚠
    assert "limited=true" in prompt
    # NULL/빈문자 처리 규칙: null-체크(A) vs '' 형(B) → 값 로직 동치이되 제한적(⚠)+caveat, 혼재 인코딩
    assert "NULL≡''" in prompt            # 운영 IS NULL ≡ 분석 = ''
    assert "빈 문자열" in prompt          # = '' null 표현
    assert "혼재" in prompt               # real null/'' 혼재 인코딩
    assert "동치로 간주" in prompt        # 값 로직 동치로 간주(하드 차이 아님)
    assert "재판정" in prompt             # base 매칭을 원본 SQL 로 재판정 금지


def test_build_prompt_gates_ods_rules_on_ods_defs():
    """ODS 전용 '고정 결과'(BASE_TABLES 조인 매칭률·증분 → ⚠)는 ods_defs 존재 시에만 프롬프트에 포함.

    비-ODS 직접조회 쿼리엔 '지어내지 마라' 게이팅 문구가 들어가 BASE_TABLES ODS 위험 오탐을 차단한다.
    """
    from query_diff.ai_diff.cli_runner import _build_prompt

    compact = {
        "verdict": "DIVERGENT", "reason": "", "issues": [], "limitations": [], "dimensions": [],
    }
    # 비-ODS(ods_defs 빈): 고정 결과 미포함 + '지어내지 마라' 포함
    p_no = _build_prompt("SELECT 1", "SELECT 1", "oracle", "hive", compact, {}, False)
    assert "지어내지 마라" in p_no
    assert "ODS 경유가 아니다" in p_no
    assert "고정 결과" not in p_no
    assert "조인 매칭률·증분 커버리지 위험 보유" not in p_no
    # ODS(ods_defs 있음): 고정 결과 포함
    p_ods = _build_prompt(
        "SELECT 1", "SELECT 1", "oracle", "hive", compact,
        {"foo_agg": "insert into ods.foo_agg select 1 from ias.x"}, False,
    )
    assert "고정 결과" in p_ods
    assert "ODS 집계본을 경유" in p_ods
    assert "조인 매칭률·증분 커버리지 위험 보유" in p_ods


def _setup_ready(sql_a, sql_b):
    cid = client.post("/api/comparisons").json()["id"]
    client.put(f"/api/comparisons/{cid}/query-a", json={"sql_raw": sql_a, "dialect": "oracle"})
    client.put(f"/api/comparisons/{cid}/query-b", json={"sql_raw": sql_b, "dialect": "hive"})
    client.post(f"/api/comparisons/{cid}/validate")
    return cid


def test_execute_ai_endpoint_limited_without_cli(monkeypatch):
    """claude CLI 부재에도 엔드포인트는 500이 아니라 LIMITED(200)."""
    monkeypatch.setattr(cli_runner, "_find_claude", lambda: None)
    cid = _setup_ready("SELECT a FROM t", "SELECT a FROM t")
    r = client.post(f"/api/comparisons/{cid}/execute-ai")
    assert r.status_code == 200
    body = r.json()
    assert body["semantic_diff"]["verdict"] == "LIMITED"
    assert body["structure_diff"] is not None  # 구문 비교는 결정적 파이썬 엔진으로 채워짐
