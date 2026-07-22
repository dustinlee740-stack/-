"""의미 비교 모듈 테스트

핵심 시나리오
-------------
1. A(FROM-join) vs B(WITH-CTE) → EQUIVALENT (구문 달라도 같은 결과)
2. WHERE 조건 다름 → DIVERGENT
3. 윈도우 함수 포함 → LIMITED
4. 테이블/조인/GROUP BY/집계 불일치 → DIVERGENT
5. API endpoint /semantic-diff 동작
6. execute 시 structure_diff 와 semantic_diff 병존
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from query_diff.api import app
from query_diff.models import Dialect, SemanticVerdict
from query_diff.semantic_diff import compare_semantic
from query_diff.store import store


@pytest.fixture(autouse=True)
def _clear_store():
    store.clear()
    yield
    store.clear()


client = TestClient(app)


# --- 단위 테스트: compare_semantic ---


class TestSemanticEquivalent:
    def test_from_join_vs_with_cte_same_result(self):
        """A는 FROM에서 직접 JOIN, B는 WITH으로 먼저 JOIN — 같은 결과가 나와야 함"""
        sql_a = """
            SELECT c.id, SUM(o.amount) AS total
            FROM customer c
            JOIN orders o ON o.customer_id = c.id
            WHERE c.region = 'KR'
            GROUP BY c.id
        """
        sql_b = """
            WITH joined AS (
              SELECT c.id AS id, o.amount AS amount
              FROM customer c
              JOIN orders o ON o.customer_id = c.id
              WHERE c.region = 'KR'
            )
            SELECT id, SUM(amount) AS total
            FROM joined
            GROUP BY id
        """
        r = compare_semantic(sql_a, Dialect.ORACLE, sql_b, Dialect.HIVE)
        assert r.verdict == SemanticVerdict.EQUIVALENT
        assert all(d.matched for d in r.dimensions if d.dimension.value in {
            "BASE_TABLES", "JOIN_GRAPH", "PREDICATES", "GROUP_KEYS", "AGGREGATES"
        })

    def test_identical_queries(self):
        sql = "SELECT id FROM t WHERE x = 1"
        r = compare_semantic(sql, Dialect.ORACLE, sql, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.EQUIVALENT

    def test_join_order_swap_still_equivalent(self):
        """JOIN의 왼쪽/오른쪽을 바꿔도 canonical_key가 정렬하므로 동치"""
        a = "SELECT * FROM a JOIN b ON a.id = b.aid"
        b = "SELECT * FROM b JOIN a ON a.id = b.aid"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        # join_graph는 동일해야 함
        join_dim = next(d for d in r.dimensions if d.dimension.value == "JOIN_GRAPH")
        assert join_dim.matched


class TestSemanticDivergent:
    def test_different_where_filter(self):
        a = "SELECT id FROM t WHERE status = 'A'"
        b = "SELECT id FROM t WHERE status = 'B'"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.DIVERGENT
        preds = next(d for d in r.dimensions if d.dimension.value == "PREDICATES")
        assert not preds.matched

    def test_different_base_tables(self):
        a = "SELECT id FROM customer"
        b = "SELECT id FROM orders"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.DIVERGENT

    def test_different_group_by(self):
        a = "SELECT region, SUM(amount) FROM sales GROUP BY region"
        b = "SELECT country, SUM(amount) FROM sales GROUP BY country"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.DIVERGENT

    def test_different_aggregate_function(self):
        a = "SELECT SUM(x) FROM t"
        b = "SELECT AVG(x) FROM t"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.DIVERGENT
        aggs = next(d for d in r.dimensions if d.dimension.value == "AGGREGATES")
        assert not aggs.matched

    def test_aggregate_qualifier_noise_absorbed(self):
        """집계식 매칭은 테이블 한정자를 무시(projections·group_keys 와 동일).

        같은 집계 컬럼(amt)이 서로 다른 테이블(t1↔t2)에서 오면 canonical 인자가
        `t1.amt`↔`t2.amt` 로 접두사만 달라진다. 테이블명은 번역하지 않는 설계이므로
        이 접두사 차이는 noise — 집계식 차원은 matched 여야 한다(오탐 방지).
        전체 판정은 base_tables 차이로 DIVERGENT 지만 집계식 자체는 일치.
        """
        a = "SELECT SUM(amt) FROM t1"
        b = "SELECT SUM(amt) FROM t2"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
        aggs = next(d for d in r.dimensions if d.dimension.value == "AGGREGATES")
        assert aggs.matched, (aggs.only_in_a, aggs.only_in_b)
        # 진짜 컬럼 차이는 여전히 상이(회귀 가드)
        a2 = "SELECT SUM(amt) FROM t1"
        b2 = "SELECT SUM(fee) FROM t2"
        r2 = compare_semantic(a2, Dialect.ORACLE, b2, Dialect.HIVE)
        aggs2 = next(d for d in r2.dimensions if d.dimension.value == "AGGREGATES")
        assert not aggs2.matched

    def test_aggregate_case_expr_qualifier_noise_absorbed(self):
        """집계 인자가 CASE 식이어도 테이블 한정자 noise 는 흡수(AST 기반 _strip_qualifiers).

        `_bare` 는 공백/괄호 있으면 원문 반환이라 CASE 안의 `t1.amt`↔`t2.amt` 를 못 뗐다.
        복합식 안 한정자까지 제거해 접두사만 다른 동일 집계는 matched 여야 한다.
        """
        a = "SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END), COUNT(CASE WHEN amt != 0 THEN 1 ELSE 0 END) FROM t1"
        b = "SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END), COUNT(CASE WHEN amt != 0 THEN 1 ELSE 0 END) FROM t2"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
        aggs = next(d for d in r.dimensions if d.dimension.value == "AGGREGATES")
        assert aggs.matched, (aggs.only_in_a, aggs.only_in_b)
        # CASE 식 안 진짜 컬럼 차이는 여전히 상이(회귀 가드)
        a2 = "SELECT SUM(CASE WHEN amt != 0 THEN amt ELSE 0 END) FROM t1"
        b2 = "SELECT SUM(CASE WHEN fee != 0 THEN fee ELSE 0 END) FROM t2"
        r2 = compare_semantic(a2, Dialect.ORACLE, b2, Dialect.HIVE)
        aggs2 = next(d for d in r2.dimensions if d.dimension.value == "AGGREGATES")
        assert not aggs2.matched

    def test_parameterized_filter_qualifier_noise_absorbed(self):
        """B 필터가 바인드(${p})→플레이스홀더면, 테이블 한정자 갭(t1↔t2)에도 파라미터로 흡수.

        `_absorb_parameterized` 의 shape 비교가 한정자를 포함해 못 흡수하던 것을 _strip_qualifiers 로 해소.
        1차는 구조 비교 — 파라미터 값은 2차(실데이터) 소관.
        """
        a = "SELECT SUM(x) FROM t1 WHERE k = 'V'"
        b = "SELECT SUM(x) FROM t2 WHERE k = '${p}'"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
        preds = next(d for d in r.dimensions if d.dimension.value == "PREDICATES")
        assert preds.matched, (preds.only_in_a, preds.only_in_b)
        # 가드: 플레이스홀더 아닌 진짜 다른 리터럴은 여전히 상이
        b2 = "SELECT SUM(x) FROM t2 WHERE k = 'W'"
        r2 = compare_semantic(a, Dialect.ORACLE, b2, Dialect.HIVE)
        preds2 = next(d for d in r2.dimensions if d.dimension.value == "PREDICATES")
        assert not preds2.matched

    def test_oracle_bind_vs_hue_bind_filter_absorbed(self):
        """A Oracle 바인드(:p) ↔ B Hue 바인드(${q}) 필터는 둘 다 파라미터로 인식·흡수.

        `_shape`·`_has_placeholder` 가 `:name` 을 파라미터로 정규화(라운드10 한정자 무시와 결합).
        """
        a = "SELECT SUM(x) FROM t1 WHERE k = :p"
        b = "SELECT SUM(x) FROM t2 WHERE k = '${q}'"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
        preds = next(d for d in r.dimensions if d.dimension.value == "PREDICATES")
        assert preds.matched, (preds.only_in_a, preds.only_in_b)

    def test_shape_bind_param_normalization(self):
        """_shape 가 Oracle 바인드 `:name` 을 `?` 로 정규화하되, 따옴표 시간·캐스트는 보존."""
        from query_diff.semantic_diff.plan_compare import _shape, _has_placeholder
        assert _shape(":nr_number = nr_no") == "? = nr_no"
        assert _has_placeholder(":nr_number = nr_no")
        assert _shape("a = '12:34:56'") == "a = ?"          # 따옴표 시간 → 리터럴
        assert _shape("x::text = y") == "x::text = y"        # Postgres 캐스트 보존
        assert not _has_placeholder("status = 'A'")           # 리터럴은 파라미터 아님

    def test_different_join_type(self):
        a = "SELECT * FROM a LEFT JOIN b ON a.id = b.aid"
        b = "SELECT * FROM a INNER JOIN b ON a.id = b.aid"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.DIVERGENT


class TestSemanticLimited:
    def test_window_function_flags_limited(self):
        sql = """
            SELECT id, ROW_NUMBER() OVER (PARTITION BY g ORDER BY id) AS rn
            FROM t WHERE x = 1
        """
        r = compare_semantic(sql, Dialect.ORACLE, sql, Dialect.ORACLE)
        # 핵심 차원은 일치하지만 윈도우 함수로 limitations 존재
        assert r.verdict == SemanticVerdict.LIMITED
        assert any("윈도우" in l or "OVER" in l for l in r.limitations)

    def test_union_flags_limited(self):
        sql = "SELECT id FROM a UNION SELECT id FROM b"
        r = compare_semantic(sql, Dialect.ORACLE, sql, Dialect.ORACLE)
        assert r.verdict == SemanticVerdict.LIMITED
        assert any("UNION" in l for l in r.limitations)


class TestSemanticDialectNormalization:
    def test_nvl_vs_coalesce_canonicalized(self):
        """Oracle NVL과 ANSI COALESCE는 canonical 단계에서 같은 함수로 정규화"""
        a = "SELECT NVL(x, 0) AS v FROM t"
        b = "SELECT COALESCE(x, 0) AS v FROM t"
        r = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
        # 비집계 projection 차원이 동일해야 함
        proj = next(d for d in r.dimensions if d.dimension.value == "PROJECTIONS")
        assert proj.matched


# --- 통합 테스트: API ---


def _setup_ready_comparison(sql_a: str, dialect_a: str, sql_b: str, dialect_b: str) -> str:
    r = client.post("/api/comparisons").json()
    cid = r["id"]
    client.put(f"/api/comparisons/{cid}/query-a", json={"sql_raw": sql_a, "dialect": dialect_a})
    client.put(f"/api/comparisons/{cid}/query-b", json={"sql_raw": sql_b, "dialect": dialect_b})
    v = client.post(f"/api/comparisons/{cid}/validate").json()
    assert v["query_a"]["is_valid"] and v["query_b"]["is_valid"]
    return cid


class TestSemanticAPI:
    def test_semantic_diff_endpoint_equivalent(self):
        cid = _setup_ready_comparison(
            "SELECT id FROM t WHERE x = 1", "oracle",
            "SELECT id FROM t WHERE x = 1", "oracle",
        )
        r = client.post(f"/api/comparisons/{cid}/semantic-diff")
        assert r.status_code == 200
        assert r.json()["verdict"] == "EQUIVALENT"

    def test_semantic_diff_endpoint_divergent(self):
        cid = _setup_ready_comparison(
            "SELECT id FROM t WHERE x = 1", "oracle",
            "SELECT id FROM t WHERE x = 2", "oracle",
        )
        r = client.post(f"/api/comparisons/{cid}/semantic-diff").json()
        assert r["verdict"] == "DIVERGENT"

    def test_get_before_run_returns_404(self):
        cid = _setup_ready_comparison(
            "SELECT 1 FROM t", "oracle",
            "SELECT 1 FROM t", "oracle",
        )
        r = client.get(f"/api/comparisons/{cid}/semantic-diff")
        assert r.status_code == 404

    def test_semantic_diff_requires_validation(self):
        r = client.post("/api/comparisons").json()
        cid = r["id"]
        r = client.post(f"/api/comparisons/{cid}/semantic-diff")
        assert r.status_code == 400

    def test_execute_populates_both_diffs(self):
        """execute는 structure_diff 와 semantic_diff 둘 다 채워야 함"""
        cid = _setup_ready_comparison(
            "SELECT id FROM t WHERE x = 1", "oracle",
            "SELECT id FROM t WHERE x = 1", "oracle",
        )
        client.put(
            f"/api/comparisons/{cid}/summary",
            json={"metrics": [{"metric_name": "합계", "value_a": 100, "value_b": 100}]},
        )
        r = client.post(f"/api/comparisons/{cid}/execute").json()
        assert r["structure_diff"] is not None
        assert r["semantic_diff"] is not None
        assert r["semantic_diff"]["verdict"] == "EQUIVALENT"

    def test_execute_divergent_semantic_with_no_structure_diff(self):
        """구문(SELECT 컬럼 수, WHERE AND 개수)은 같아 structure_diff 가 '동일'이어도
        필터 값이 다르면 semantic_diff 는 DIVERGENT 를 내야 함 — 두 뷰가 독립적으로 동작.
        """
        cid = _setup_ready_comparison(
            "SELECT id FROM t WHERE status = 'A'", "oracle",
            "SELECT id FROM t WHERE status = 'B'", "oracle",
        )
        client.put(
            f"/api/comparisons/{cid}/summary",
            json={"metrics": [{"metric_name": "합계", "value_a": 100, "value_b": 90}]},
        )
        r = client.post(f"/api/comparisons/{cid}/execute").json()
        assert r["semantic_diff"]["verdict"] == "DIVERGENT"
