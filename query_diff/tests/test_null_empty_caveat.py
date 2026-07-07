"""NULL↔빈문자('') 처리 차이를 엔진이 결정적으로 제한적 판정(limited+caveat)으로 표기하는지 검증.

운영(A, real `IS NULL`)↔분석(B, `= ''`/`!= ''`)은 `_canonical_expr` 흡수로 매칭(값 로직 동치)되나,
분석계 NULL/빈문자 혼재 가능성 때문에 해당 차원을 limited=True + _NULL_EMPTY_CAVEAT 로 결정적으로
표기해야 한다(날짜범위 caveat 과 동일 패턴). 양쪽 다 real IS NULL 이면 위험 아님(limited=False).
"""
from __future__ import annotations

from query_diff.models import Dialect, DimensionName
from query_diff.semantic_diff import compare_semantic

O, H = Dialect.ORACLE, Dialect.HIVE


def _dim(diff, name):
    return next(d for d in diff.dimensions if d.dimension == name)


def test_where_null_vs_empty_flagged_limited():
    """WHERE: A `x IS NOT NULL` vs B `x != ''` → matched + limited + null/empty caveat."""
    a = "SELECT id FROM t WHERE flag_col IS NOT NULL"
    b = "SELECT id FROM t WHERE flag_col != ''"
    pred = _dim(compare_semantic(a, O, b, H), DimensionName.PREDICATES)
    assert pred.matched is True                    # 값 로직 동치 — 하드 차이 아님
    assert pred.limited is True                    # 혼재 위험 — 제한적
    assert "빈 문자열" in pred.caveat or "혼재" in pred.caveat, pred.caveat


def test_join_on_null_vs_empty_flagged_limited():
    """JOIN ON: A `c IS NOT NULL` vs B `c != ''` (부가조건) → JOIN_GRAPH matched + limited + caveat."""
    a = "SELECT x.id FROM x LEFT JOIN y ON y.k = x.k AND x.c IS NOT NULL"
    b = "SELECT x.id FROM x LEFT JOIN y ON y.k = x.k AND x.c != ''"
    jg = _dim(compare_semantic(a, O, b, H), DimensionName.JOIN_GRAPH)
    assert jg.matched is True
    assert jg.limited is True
    assert "빈 문자열" in jg.caveat or "혼재" in jg.caveat, jg.caveat


def test_null_empty_flagged_under_fallback_qualifier_mismatch():
    """원형 AST 폴백(뷰 컬럼 미해석)으로 A(한정)↔B(비한정) canonical 이 달라 `sh` 에 없고 한정자-노이즈
    로 흡수되는 케이스에도 null/empty 위험이 잡히는지(갭 회귀 방지). WHERE·JOIN 둘 다 limited=True.

    카드 재발급 실쿼리 재현: cdm.old_par(A 한정) vs OLD_PAR(B 비한정), card_apply_no 조인 부가조건."""
    a = ("select v from cdm.view_x cdm "
         "left join c.card_issue ci on cdm.card_apply_no is not null and ci.no = cdm.card_apply_no "
         "where cdm.old_par is not null")
    b = ("select v from cdm.view_x cdm "
         "left join c.card_issue ci on cdm.card_apply_no != '' and ci.no = cdm.card_apply_no "
         "where OLD_PAR != ''")
    diff = compare_semantic(a, O, b, H)
    pred = _dim(diff, DimensionName.PREDICATES)
    jg = _dim(diff, DimensionName.JOIN_GRAPH)
    assert pred.matched is True and pred.limited is True, (pred.matched, pred.limited)
    assert jg.matched is True and jg.limited is True, (jg.matched, jg.limited)


def test_both_real_null_not_flagged():
    """양쪽 모두 real `IS NOT NULL` → '' 형 아님 → 위험 없음(limited=False)."""
    a = "SELECT id FROM t WHERE flag_col IS NOT NULL"
    b = "SELECT id FROM t WHERE flag_col IS NOT NULL"
    pred = _dim(compare_semantic(a, O, b, H), DimensionName.PREDICATES)
    assert pred.matched is True
    assert pred.limited is False
    assert pred.caveat == ""
