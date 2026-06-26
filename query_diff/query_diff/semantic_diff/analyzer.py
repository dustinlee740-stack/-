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
    LogicalPlan,
    SemanticDiff,
    SemanticVerdict,
)
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.semantic_diff.planner import build_logical_plan, resolve_cte_passthrough
from query_diff.semantic_diff.plan_compare import (
    _absorb_parameterized,
    _bare_cols,
    _da,
    _diff_sets,
    _diff_sets_by_column,
    _group_edges,
    _lookup_raw_on,
    _raw_on_map,
    _ref_cols,
)
from query_diff.structure_diff.schema_mapping import OpAnMap, translate_op_to_an

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


def _compare_base_tables(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.base_tables, b.base_tables)
    oa = _da(oa, rename)
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


def _compare_join_graph(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str] | None = None,
    raw_on_a: dict[str, str] | None = None,
    raw_on_b: dict[str, str] | None = None,
) -> DimensionResult:
    """조인을 (ON 참조 테이블집합, 조인타입) 으로 페어링하고 ON 술어 단위로 비교.

    차이는 **원본 쿼리에서 찾을 수 있는 앵커**(테이블·컬럼 영문 + 해당 조인 ON 절 원문)로 표기.
    """
    ga, gb = _group_edges(a.join_edges), _group_edges(b.join_edges)
    raw_on_a = raw_on_a or {}
    raw_on_b = raw_on_b or {}

    only_a: list[str] = []
    only_b: list[str] = []
    shared_cnt = 0
    param_cnt = 0

    for key in sorted(set(ga) | set(gb), key=lambda k: (sorted(k[0]), k[1])):
        tables, jtype = key
        label = "↔".join(sorted(tables))
        pa = ga.get(key)
        pb = gb.get(key)
        if pa is None:
            raw = _lookup_raw_on(raw_on_b, tables)
            only_b.append(
                f"`{label}` 조인이 B 쿼리에만 있습니다"
                + (f" (B 원본 ON: {raw})" if raw else "")
            )
            continue
        if pb is None:
            raw = _lookup_raw_on(raw_on_a, tables)
            only_a.append(
                f"`{label}` 조인이 A 쿼리에만 있습니다"
                + (f" (A 원본 ON: {raw})" if raw else "")
            )
            continue
        # 같은 테이블쌍·타입 — ON 술어 차이만 비교
        dpa = sorted(pa - pb)
        dpb = sorted(pb - pa)
        dpa, dpb, param = _absorb_parameterized(dpa, dpb)
        param_cnt += len(param)
        dpa = _da(dpa, rename)
        if not dpa and not dpb:
            shared_cnt += 1
            continue
        if dpa:
            raw = _lookup_raw_on(raw_on_a, tables)
            only_a.append(
                f"`{label}` 조인 — A 쿼리에만 추가 조인 조건. 확인할 컬럼: "
                f"{', '.join(_ref_cols(dpa)) or '(상수 조건)'}"
                + (f" (A 원본 ON: {raw})" if raw else "")
            )
        if dpb:
            raw = _lookup_raw_on(raw_on_b, tables)
            only_b.append(
                f"`{label}` 조인 — B 쿼리에만 추가 조인 조건. 확인할 컬럼: "
                f"{', '.join(_ref_cols(dpb)) or '(상수 조건)'}"
                + (f" (B 원본 ON: {raw})" if raw else "")
            )

    matched = not only_a and not only_b
    param_note = (
        f" · 값만 다른 항목(날짜·코드 등) {param_cnt}개는 비교 제외" if param_cnt else ""
    )
    if matched:
        expl = (
            f"테이블 연결 방식(JOIN)이 양쪽 동일합니다{param_note}."
            if (shared_cnt or param_cnt)
            else "양쪽 모두 조인이 없습니다."
        )
    else:
        expl = (
            "테이블 연결 방식(JOIN)이 다릅니다 — "
            + " / ".join(only_a + only_b)
            + param_note
        )
    return DimensionResult(
        dimension=DimensionName.JOIN_GRAPH,
        matched=matched,
        only_in_a=only_a,
        only_in_b=only_b,
        shared=[],
        explanation=expl,
    )


def _compare_predicates(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.all_predicates, b.all_predicates)
    oa, ob, param = _absorb_parameterized(oa, ob)
    oa = _da(oa, rename)
    matched = not oa and not ob
    param_note = (
        f" · 값만 다른 항목(날짜·코드 등) {len(param)}개는 비교 제외" if param else ""
    )
    if matched:
        expl = (
            f"조회 조건(WHERE/HAVING) {len(sh)}건이 양쪽 동일합니다{param_note}."
            if sh or param
            else "양쪽 모두 조회 조건이 없습니다."
        )
    else:
        parts = []
        if oa:
            parts.append(f"A 쿼리에만: {', '.join(_ref_cols(oa)) or ', '.join(oa)}")
        if ob:
            parts.append(f"B 쿼리에만: {', '.join(_ref_cols(ob)) or ', '.join(ob)}")
        expl = (
            "조회 조건(WHERE/HAVING)이 다릅니다 — "
            + " / ".join(parts)
            + ". (해당 쿼리 WHERE 절에서 위 컬럼을 확인하세요)"
            + param_note
        )
    return DimensionResult(
        dimension=DimensionName.PREDICATES,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_group_keys(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets_by_column(a.group_keys, b.group_keys)
    oa = _da(oa, rename)
    if matched:
        expl = (
            f"GROUP BY 키 {len(sh)}개가 동일합니다."
            if sh
            else "양쪽 모두 GROUP BY가 없습니다."
        )
    else:
        parts = []
        if oa:
            parts.append(f"A 쿼리에만: {', '.join(_bare_cols(oa))}")
        if ob:
            parts.append(f"B 쿼리에만: {', '.join(_bare_cols(ob))}")
        expl = (
            "묶음 기준(GROUP BY)이 다릅니다 — "
            + " / ".join(parts)
            + ". (해당 쿼리 GROUP BY 절에서 위 컬럼을 확인하세요. 한쪽만 묶으면 합계 단위가 달라집니다)"
        )
    return DimensionResult(
        dimension=DimensionName.GROUP_KEYS,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_aggregates(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    # tuple(func, arg) → 문자열 표현으로 집합 비교
    def _fmt(pairs: list[tuple[str, str]]) -> list[str]:
        return [f"{f}({g})" for f, g in pairs]

    sa, sb = _fmt(a.aggregates), _fmt(b.aggregates)
    matched, oa, ob, sh = _diff_sets(sa, sb)
    oa = _da(oa, rename)
    if matched:
        expl = (
            f"집계식 {len(sh)}개가 동일합니다."
            if sh
            else "양쪽 모두 집계가 없습니다."
        )
    else:
        parts = []
        if oa:
            parts.append(f"A 쿼리: {', '.join(oa)}")
        if ob:
            parts.append(f"B 쿼리: {', '.join(ob)}")
        expl = (
            "계산식(SELECT 집계)이 다릅니다 — "
            + " / ".join(parts)
            + ". (각 쿼리 SELECT 절에서 위 컬럼을 확인하세요)"
        )
    return DimensionResult(
        dimension=DimensionName.AGGREGATES,
        matched=matched,
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
    )


def _compare_projections(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets_by_column(a.projections, b.projections)
    oa = _da(oa, rename)
    if matched:
        expl = "출력 컬럼(SELECT)이 양쪽 동일합니다."
    else:
        parts = []
        if oa:
            parts.append(f"A 쿼리에만: {', '.join(_bare_cols(oa))}")
        if ob:
            parts.append(f"B 쿼리에만: {', '.join(_bare_cols(ob))}")
        expl = (
            "출력(SELECT) 컬럼이 다릅니다 — "
            + " / ".join(parts)
            + ". (해당 쿼리 SELECT 절에서 위 컬럼을 확인하세요)"
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
    sql_a: str,
    dialect_a: Dialect,
    sql_b: str,
    dialect_b: Dialect,
    op_an: OpAnMap | None = None,
) -> SemanticDiff:
    """두 SQL의 의미적 동치 여부를 판정하여 SemanticDiff 반환.

    op_an 가 주어지면 A(운영) 쿼리를 정규화 후 분석 네임스페이스로 번역해 비교한다.
    """
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

    # 번역/해소 전 원본 ON 절 텍스트 확보(사용자가 원본 쿼리에서 찾을 수 있게)
    raw_on_a = _raw_on_map(tree_a)
    rename_a: dict[str, str] = {}
    if op_an is not None:
        tree_a, rename_a = translate_op_to_an(tree_a, op_an)

    try:
        tree_b, lim_b = normalize_query(sql_b, db)
    except ValueError as e:
        return SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="B 쿼리 정규화에 실패했습니다.",
            error=f"B: {e}",
        )
    raw_on_b = _raw_on_map(tree_b)

    # 집계 CTE(WITH)로 만든 main spine 을 원천으로 해소 — WITH-spine 과 JOIN-spine 정렬
    tree_a = resolve_cte_passthrough(tree_a)
    tree_b = resolve_cte_passthrough(tree_b)

    plan_a = build_logical_plan(tree_a, lim_a)
    plan_b = build_logical_plan(tree_b, lim_b)

    # 비교는 분석명 기준, A측 표시(only_in_a·explanation의 A부분)만 원본 운영명으로 역변환.
    dims = [
        _compare_base_tables(plan_a, plan_b, rename_a),
        _compare_join_graph(plan_a, plan_b, rename_a, raw_on_a, raw_on_b),
        _compare_predicates(plan_a, plan_b, rename_a),
        _compare_group_keys(plan_a, plan_b, rename_a),
        _compare_aggregates(plan_a, plan_b, rename_a),
        _compare_projections(plan_a, plan_b, rename_a),
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
