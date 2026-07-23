"""구조 비교 엔진(No.2) 테스트"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from query_diff.api import app
from query_diff.models import Dialect, QueryInput, Severity, ClauseType
from query_diff.store import store
from query_diff.structure_diff import compare_structures
from query_diff.validation_service import validate_query_input


client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    store.clear()
    yield
    store.clear()


def _qi(sql: str, dialect: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=dialect)
    validate_query_input(q)
    assert q.is_valid, f"검증 실패: {q.validation_error}"
    return q


# --- 동일 쿼리 ---

class TestIdentical:
    def test_identical_simple(self):
        sql = "SELECT id, SUM(amount) FROM sales WHERE status = 'A' GROUP BY id"
        a = _qi(sql, Dialect.ORACLE)
        b = _qi(sql, Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.has_difference is False
        assert d.fast_path_terminate is False
        assert d.findings == []

    def test_nvl_coalesce_equivalent(self):
        """NVL ↔ COALESCE 함수 동의어는 동일로 간주"""
        a = _qi("SELECT NVL(x, 0) FROM t", Dialect.ORACLE)
        b = _qi("SELECT COALESCE(x, 0) FROM t", Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.has_difference is False

    def test_where_order_insensitive(self):
        """WHERE AND 순서가 달라도 동일로 간주"""
        a = _qi("SELECT 1 FROM t WHERE a = 1 AND b = 2", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE b = 2 AND a = 1", Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.has_difference is False

    def test_equal_operator_symmetric(self):
        """a = b 와 b = a 는 동일"""
        a = _qi("SELECT 1 FROM t1 JOIN t2 ON t1.id = t2.id", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t1 JOIN t2 ON t2.id = t1.id", Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.has_difference is False


# --- 개별 규칙 ---

class TestFromRules:
    def test_table_count_mismatch(self):
        # 공유 엔진 통합 후 base_tables 는 집합 비교 → 테이블 수 차이는 정체성 불일치로 표면화
        a = _qi("SELECT 1 FROM t1, t2", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t1", Dialect.HIVE)
        d = compare_structures(a, b)
        from_critical = [
            f for f in d.findings
            if f.clause == ClauseType.FROM and f.severity == Severity.CRITICAL
        ]
        assert from_critical
        assert d.fast_path_terminate

    def test_table_identity_mismatch(self):
        a = _qi("SELECT 1 FROM sales", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM revenue", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "TABLE_IDENTITY_MISMATCH" for f in d.findings)


class TestJoinRules:
    def test_join_type_mismatch(self):
        a = _qi("SELECT a.id FROM t a JOIN u b ON a.id = b.id", Dialect.ORACLE)
        b = _qi("SELECT a.id FROM t a LEFT JOIN u b ON a.id = b.id", Dialect.HIVE)
        d = compare_structures(a, b)
        findings = [f for f in d.findings if f.rule_id == "JOIN_TYPE_MISMATCH"]
        assert len(findings) == 1
        assert findings[0].severity == Severity.CRITICAL

    def test_join_condition_mismatch(self):
        a = _qi("SELECT 1 FROM t a JOIN u b ON a.id = b.id", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t a JOIN u b ON a.id = b.other_id", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "JOIN_CONDITION_MISMATCH" for f in d.findings)


class TestWhereRules:
    def test_predicate_only_in_a(self):
        a = _qi("SELECT 1 FROM t WHERE x = 1 AND y = 2", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE x = 1", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "WHERE_PREDICATE_ONLY_IN_A" for f in d.findings)

    def test_predicate_only_in_b(self):
        a = _qi("SELECT 1 FROM t WHERE x = 1", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE x = 1 AND y = 2", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "WHERE_PREDICATE_ONLY_IN_B" for f in d.findings)

    def test_literal_mismatch(self):
        a = _qi("SELECT 1 FROM t WHERE status = 'A'", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE status = 'B'", Dialect.HIVE)
        d = compare_structures(a, b)
        lit = [f for f in d.findings if f.rule_id == "WHERE_LITERAL_MISMATCH"]
        assert len(lit) == 1
        assert lit[0].severity == Severity.CRITICAL

    def test_commented_predicate_ignored(self):
        """`--` 주석 처리된 술어는 구조 비교에서 무시 — WHERE 오탐 finding 없음."""
        a = _qi("SELECT 1 FROM t WHERE x = 1\n--and nr_number = 'V'\nAND y = 2", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE x = 1 AND y = 2", Dialect.HIVE)
        d = compare_structures(a, b)
        assert not any(f.rule_id.startswith("WHERE_") for f in d.findings), [
            f.rule_id for f in d.findings
        ]


class TestGroupByHavingRules:
    def test_group_by_mismatch(self):
        a = _qi("SELECT dept, SUM(x) FROM t GROUP BY dept", Dialect.ORACLE)
        b = _qi("SELECT dept, SUM(x) FROM t GROUP BY dept, region", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "GROUP_BY_COLUMN_MISMATCH" for f in d.findings)

    def test_having_mismatch(self):
        a = _qi("SELECT d, SUM(x) FROM t GROUP BY d HAVING SUM(x) > 100", Dialect.ORACLE)
        b = _qi("SELECT d, SUM(x) FROM t GROUP BY d HAVING SUM(x) > 200", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "HAVING_MISMATCH" for f in d.findings)


class TestSelectRules:
    def test_agg_function_mismatch(self):
        a = _qi("SELECT d, SUM(x) FROM t GROUP BY d", Dialect.ORACLE)
        b = _qi("SELECT d, COUNT(x) FROM t GROUP BY d", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "AGG_FUNCTION_MISMATCH" for f in d.findings)

    def test_agg_argument_mismatch(self):
        a = _qi("SELECT d, SUM(amount) FROM t GROUP BY d", Dialect.ORACLE)
        b = _qi("SELECT d, SUM(quantity) FROM t GROUP BY d", Dialect.HIVE)
        d = compare_structures(a, b)
        assert any(f.rule_id == "AGG_ARGUMENT_MISMATCH" for f in d.findings)

    def test_agg_qualifier_noise_no_finding(self):
        """같은 집계 컬럼이 다른 테이블에서 와 접두사만 다르면(t1.amt↔t2.amt)
        집계 오탐(AGG_ARGUMENT_MISMATCH/AGG_FUNCTION_MISMATCH)을 내지 않는다.
        테이블명 비번역 설계의 한정자 noise 흡수 — semantic 엔진과 동일."""
        a = _qi("SELECT SUM(amt) FROM t1", Dialect.ORACLE)
        b = _qi("SELECT SUM(amt) FROM t2", Dialect.HIVE)
        d = compare_structures(a, b)
        assert not [f for f in d.findings if f.rule_id.startswith("AGG_")]

    def test_agg_case_expr_qualifier_noise_no_finding(self):
        """집계 인자가 CASE 식(t1.amt↔t2.amt)이어도 접두사 noise 는 흡수 — AGG_* 미발화.
        복합식 안 한정자까지 제거(_strip_qualifiers). 진짜 컬럼 차이는 여전히 발화."""
        a = _qi("SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END) FROM t1", Dialect.ORACLE)
        b = _qi("SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END) FROM t2", Dialect.HIVE)
        d = compare_structures(a, b)
        assert not [f for f in d.findings if f.rule_id.startswith("AGG_")]
        # CASE 안 컬럼이 실제로 다르면 여전히 인자 불일치
        a2 = _qi("SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END) FROM t1", Dialect.ORACLE)
        b2 = _qi("SELECT SUM(CASE WHEN fee != 0 THEN fee ELSE 0 END) FROM t2", Dialect.HIVE)
        d2 = compare_structures(a2, b2)
        assert any(f.rule_id.startswith("AGG_") for f in d2.findings)

    def test_projection_diff_info(self):
        a = _qi("SELECT a, b, SUM(x) FROM t GROUP BY a, b", Dialect.ORACLE)
        b = _qi("SELECT a, c, SUM(x) FROM t GROUP BY a, c", Dialect.HIVE)
        d = compare_structures(a, b)
        # projection diff는 INFO
        info_findings = [f for f in d.findings if f.rule_id == "SELECT_PROJECTION_DIFF"]
        assert len(info_findings) >= 1
        assert info_findings[0].severity == Severity.INFO


# --- Fast-path 종결 ---

class TestFastPath:
    def test_fast_path_on_critical(self):
        a = _qi("SELECT 1 FROM sales WHERE status = 'A'", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM sales WHERE status = 'B'", Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.fast_path_terminate is True
        assert d.dominant_clause is not None

    def test_no_fast_path_on_warning_only(self):
        """WARNING만 있으면 fast-path 안 탐"""
        a = _qi("SELECT 1 FROM t WHERE x = 1", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM t WHERE x = 1 AND y IS NOT NULL", Dialect.HIVE)
        d = compare_structures(a, b)
        assert d.has_difference is True
        assert d.fast_path_terminate is False

    def test_dominant_clause_priority(self):
        """FROM > JOIN > WHERE 순으로 dominant 선정"""
        a = _qi("SELECT 1 FROM sales WHERE status = 'A'", Dialect.ORACLE)
        b = _qi("SELECT 1 FROM revenue WHERE status = 'B'", Dialect.HIVE)
        d = compare_structures(a, b)
        # FROM critical이 있으므로 FROM이 dominant
        assert d.dominant_clause == ClauseType.FROM


# --- API 엔드포인트 ---

def _setup_req(sql_a: str, sql_b: str) -> str:
    req = client.post("/api/comparisons").json()
    rid = req["id"]
    client.put(f"/api/comparisons/{rid}/query-a", json={"sql_raw": sql_a, "dialect": "oracle"})
    client.put(f"/api/comparisons/{rid}/query-b", json={"sql_raw": sql_b, "dialect": "hive"})
    client.post(f"/api/comparisons/{rid}/validate")
    return rid


class TestStructureDiffEndpoint:
    def test_run_structure_diff(self):
        rid = _setup_req(
            "SELECT id, SUM(x) FROM t WHERE s = 'A' GROUP BY id",
            "SELECT id, SUM(x) FROM t WHERE s = 'B' GROUP BY id",
        )
        resp = client.post(f"/api/comparisons/{rid}/structure-diff")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_difference"] is True
        assert data["fast_path_terminate"] is True
        assert any(f["rule_id"] == "WHERE_LITERAL_MISMATCH" for f in data["findings"])

    def test_get_structure_diff_before_run(self):
        rid = _setup_req("SELECT 1 FROM t", "SELECT 1 FROM t")
        resp = client.get(f"/api/comparisons/{rid}/structure-diff")
        assert resp.status_code == 404

    def test_get_structure_diff_after_run(self):
        rid = _setup_req("SELECT 1 FROM t", "SELECT 1 FROM t")
        client.post(f"/api/comparisons/{rid}/structure-diff")
        resp = client.get(f"/api/comparisons/{rid}/structure-diff")
        assert resp.status_code == 200
        assert resp.json()["has_difference"] is False

    def test_structure_diff_requires_valid(self):
        req = client.post("/api/comparisons").json()
        rid = req["id"]
        resp = client.post(f"/api/comparisons/{rid}/structure-diff")
        assert resp.status_code == 400


class TestAcknowledge:
    def _setup_critical(self) -> tuple[str, dict]:
        rid = _setup_req(
            "SELECT 1 FROM t WHERE s = 'A'",
            "SELECT 1 FROM t WHERE s = 'B'",
        )
        diff = client.post(f"/api/comparisons/{rid}/structure-diff").json()
        assert diff["fast_path_terminate"] is True
        assert diff["unresolved_critical_count"] >= 1
        return rid, diff

    def test_acknowledge_single_clears_fast_path_when_only_critical(self):
        rid, diff = self._setup_critical()
        critical_idx = next(
            i for i, f in enumerate(diff["findings"]) if f["severity"] == "CRITICAL"
        )
        resp = client.patch(
            f"/api/comparisons/{rid}/structure-diff/findings/{critical_idx}",
            json={"acknowledged": True},
        )
        assert resp.status_code == 200
        updated = resp.json()
        assert updated["findings"][critical_idx]["user_acknowledged"] is True
        assert updated["unresolved_critical_count"] == 0
        assert updated["fast_path_terminate"] is False

    def test_acknowledge_toggle(self):
        rid, diff = self._setup_critical()
        idx = next(
            i for i, f in enumerate(diff["findings"]) if f["severity"] == "CRITICAL"
        )
        client.patch(
            f"/api/comparisons/{rid}/structure-diff/findings/{idx}",
            json={"acknowledged": True},
        )
        resp = client.patch(
            f"/api/comparisons/{rid}/structure-diff/findings/{idx}",
            json={"acknowledged": False},
        )
        updated = resp.json()
        assert updated["findings"][idx]["user_acknowledged"] is False
        assert updated["fast_path_terminate"] is True

    def test_acknowledge_invalid_index(self):
        rid, _ = self._setup_critical()
        resp = client.patch(
            f"/api/comparisons/{rid}/structure-diff/findings/99",
            json={"acknowledged": True},
        )
        assert resp.status_code == 404
