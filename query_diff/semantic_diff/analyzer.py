"""의미 비교 분석기

A/B 쿼리에서 LogicalPlan을 각각 추출한 뒤 6개 차원을 비교하여
EQUIVALENT / DIVERGENT / LIMITED 판정을 내리고 자연어 사유를 덧붙인다.

차원별 판정 규칙
----------------
- BASE_TABLES: 실제로 읽는 테이블 집합이 같은가
- JOIN_GRAPH: 조인 edge의 canonical key 집합이 같은가 (순서 무관)
- PREDICATES: WHERE+HAVING 통합 predicate 집합이 같은가
- GROUP_KEYS: GROUP BY 키 집합이 같은가
- AGGREGATES: (함수, 인자) 튜플 집합이 같은가
- PROJECTIONS: 비집계 출력 집합이 같은가 (참고용 — DIVERGENT 판정엔 약한 신호)

판정 규칙
----------
- 핵심 차원(BASE_TABLES, JOIN_GRAPH, PREDICATES, GROUP_KEYS, AGGREGATES)이 모두
  일치하고 제한사항이 없으면 EQUIVALENT
- 핵심 차원 중 하나라도 어긋나면 DIVERGENT
- 핵심 차원은 모두 일치하지만 제한사항이 있으면 LIMITED
"""

from __future__ import annotations

from query_diff.models import (
    Dialect,
    DimensionName,
    DimensionResult,
    JoinEdge,
    LogicalPlan,
    SemanticDiff,
    SemanticVerdict,
)
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.semantic_diff.planner import build_logical_plan

# sqlglot dialect 매핑 — validation_service와 중복되지만 의존 방향을 피하기 위해 국소 정의
_DIALECT_MAP: dict[Dialect, str] = {
    Dialect.ORACLE: "oracle",
    Dialect.HIVE: "hive",
    Dialect.MYSQL: "mysql",
    Dialect.POSTGRES: "postgres",
}

_CORE_DIMENSIONS = {
    DimensionName.BASE_TABLES,
    DimensionName.JOIN_GRAPH,
    DimensionName.PREDICATES,
    DimensionName.GROUP_KEYS,
    DimensionName.AGGREGATES,
}


def _diff_sets(
    a: list[str], b: list[str]
) -> tuple[bool, list[str], list[str], list[str]]:
    """두 문자열 집합을 비교하여 (matched, only_a, only_b, shared) 반환."""
    sa, sb = set(a), set(b)
    only_a = sorted(sa - sb)
    only_b = sorted(sb - sa)
    shared = sorted(sa & sb)
    matched = not only_a and not only_b
    return matched, only_a, only_b, shared


def _compare_base_tables(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.base_tables, b.base_tables)
    if matched:
        expl = f"양쪽 모두 같은 {len(sh)}개 테이블을 읽습니다: {', '.join(sh)}."
    else:
        parts = []
        if oa:
            parts.append(f"A에만 있는 테이블: {', '.join(oa)}")
        if ob:
            parts.append(f"B에만 있는 테이블: {', '.join(ob)}")
        expl = "읽는 기본 테이블이 다릅니다. " + " / ".join(parts)
    return DimensionResult(
        dimension=DimensionName.BASE_TABLES,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _edge_keys(edges: list[JoinEdge]) -> list[str]:
    return [e.canonical_key() for e in edges]


def _compare_join_graph(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    ka = _edge_keys(a.join_edges)
    kb = _edge_keys(b.join_edges)
    matched, oa, ob, sh = _diff_sets(ka, kb)
    if matched:
        if not sh:
            expl = "양쪽 모두 조인이 없습니다 (단일 테이블 또는 CTE 인라인 결과가 동일)."
        else:
            expl = (
                f"{len(sh)}개 조인이 모두 같은 테이블 쌍·조인 타입·조건으로 수행됩니다. "
                "A가 FROM에서 직접 조인하든 B가 WITH로 먼저 조인하든 옵티마이저 단계에서 "
                "동일한 조인 그래프로 수렴했습니다."
            )
    else:
        parts = []
        if oa:
            parts.append(f"A에만 있는 조인: {', '.join(oa)}")
        if ob:
            parts.append(f"B에만 있는 조인: {', '.join(ob)}")
        expl = "조인 그래프가 다릅니다. " + " / ".join(parts)
    return DimensionResult(
        dimension=DimensionName.JOIN_GRAPH,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_predicates(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.all_predicates, b.all_predicates)
    if matched:
        expl = (
            f"WHERE/HAVING 필터 {len(sh)}건이 동일합니다."
            if sh
            else "양쪽 모두 필터 조건이 없습니다."
        )
    else:
        parts = []
        if oa:
            parts.append(f"A에만 있는 조건: {', '.join(oa)}")
        if ob:
            parts.append(f"B에만 있는 조건: {', '.join(ob)}")
        expl = (
            "필터 조건이 달라 결과 행 집합이 달라질 수 있습니다. "
            + " / ".join(parts)
        )
    return DimensionResult(
        dimension=DimensionName.PREDICATES,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_group_keys(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.group_keys, b.group_keys)
    if matched:
        expl = (
            f"GROUP BY 키 {len(sh)}개가 동일합니다."
            if sh
            else "양쪽 모두 GROUP BY가 없습니다."
        )
    else:
        expl = (
            "GROUP BY 키가 달라 집계 단위(행 결합 기준)가 달라집니다. "
            f"A만: {oa or '없음'} / B만: {ob or '없음'}"
        )
    return DimensionResult(
        dimension=DimensionName.GROUP_KEYS,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_aggregates(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    # tuple(func, arg) → 문자열 표현으로 집합 비교
    def _fmt(pairs: list[tuple[str, str]]) -> list[str]:
        return [f"{f}({g})" for f, g in pairs]

    sa, sb = _fmt(a.aggregates), _fmt(b.aggregates)
    matched, oa, ob, sh = _diff_sets(sa, sb)
    if matched:
        expl = (
            f"집계식 {len(sh)}개가 동일합니다."
            if sh
            else "양쪽 모두 집계가 없습니다."
        )
    else:
        parts = []
        if oa:
            parts.append(f"A에만 있는 집계: {', '.join(oa)}")
        if ob:
            parts.append(f"B에만 있는 집계: {', '.join(ob)}")
        expl = "집계 결과가 달라집니다. " + " / ".join(parts)
    return DimensionResult(
        dimension=DimensionName.AGGREGATES,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_projections(a: LogicalPlan, b: LogicalPlan) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.projections, b.projections)
    if matched:
        expl = "비집계 출력 컬럼이 동일합니다."
    else:
        expl = (
            "비집계 출력 컬럼이 다릅니다 — 같은 데이터라도 노출 컬럼이 달라질 수 있습니다. "
            f"A만: {oa or '없음'} / B만: {ob or '없음'}"
        )
    return DimensionResult(
        dimension=DimensionName.PROJECTIONS,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _decide_verdict(
    dims: list[DimensionResult], limitations: list[str]
) -> tuple[SemanticVerdict, str]:
    unmatched_core = [
        d for d in dims if d.dimension in _CORE_DIMENSIONS and not d.matched
    ]

    if unmatched_core:
        reasons = [f"[{d.dimension.value}] {d.explanation}" for d in unmatched_core]
        return (
            SemanticVerdict.DIVERGENT,
            "두 쿼리는 서로 다른 결과를 낼 가능성이 높습니다. "
            + " | ".join(reasons),
        )

    if limitations:
        return (
            SemanticVerdict.LIMITED,
            "핵심 차원은 일치하지만 정규화할 수 없는 구문이 있어 완전한 동치 판정을 내리지 못했습니다: "
            + "; ".join(limitations),
        )

    return (
        SemanticVerdict.EQUIVALENT,
        "두 쿼리는 읽는 테이블·조인 그래프·필터·집계 단위·집계식이 모두 같아 "
        "동일한 결과 집합을 반환할 것으로 판정됩니다. "
        "표기(구문) 차이는 옵티마이저 단계에서 흡수되었습니다.",
    )


def compare_semantic(
    sql_a: str, dialect_a: Dialect, sql_b: str, dialect_b: Dialect
) -> SemanticDiff:
    """두 SQL의 의미적 동치 여부를 판정하여 SemanticDiff 반환."""
    da = _DIALECT_MAP[dialect_a]
    db = _DIALECT_MAP[dialect_b]

    try:
        tree_a, lim_a = normalize_query(sql_a, da)
    except ValueError as e:
        return SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="A 쿼리 정규화에 실패했습니다.",
            error=f"A: {e}",
        )

    try:
        tree_b, lim_b = normalize_query(sql_b, db)
    except ValueError as e:
        return SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="B 쿼리 정규화에 실패했습니다.",
            error=f"B: {e}",
        )

    plan_a = build_logical_plan(tree_a, lim_a)
    plan_b = build_logical_plan(tree_b, lim_b)

    dims = [
        _compare_base_tables(plan_a, plan_b),
        _compare_join_graph(plan_a, plan_b),
        _compare_predicates(plan_a, plan_b),
        _compare_group_keys(plan_a, plan_b),
        _compare_aggregates(plan_a, plan_b),
        _compare_projections(plan_a, plan_b),
    ]

    # 중복 제거된 통합 제한사항
    merged_limitations = sorted({*plan_a.limitations, *plan_b.limitations})
    verdict, reason = _decide_verdict(dims, merged_limitations)

    return SemanticDiff(
        verdict=verdict,
        reason=reason,
        plan_a=plan_a,
        plan_b=plan_b,
        dimensions=dims,
        limitations=merged_limitations,
    )
