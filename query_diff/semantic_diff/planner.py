"""LogicalPlan 추출기

sqlglot optimizer가 CTE 인라인·서브쿼리 머지·컬럼 qualify를 끝낸 AST에서
차원별 정보를 뽑아 `LogicalPlan`을 만든다.

A(FROM 직접 조인)와 B(WITH CTE로 먼저 조인)는 최적화 후 동일 AST로 수렴하므로
이 단계의 추출 결과도 같아진다.
"""

from __future__ import annotations

from sqlglot import exp

from query_diff.models import JoinEdge, LogicalPlan
from query_diff.structure_diff.normalizer import (
    _AGG_FUNCTIONS,
    _build_alias_map,
    _canonical_expr,
    _norm_ident,
    _normalize_function_name,
    _split_and,
)


def _top_select(tree: exp.Expression) -> exp.Select | None:
    if isinstance(tree, exp.Select):
        return tree
    return tree.find(exp.Select)


def _extract_base_tables(select: exp.Select) -> list[str]:
    """FROM + JOIN 의 실제 테이블명(스키마 제외, lower) 집합을 정렬 반환."""
    names: set[str] = set()

    from_ = select.args.get("from_") or select.args.get("from")
    if from_ is not None:
        for tbl in from_.find_all(exp.Table):
            names.add(_norm_ident(tbl.name))

    for join in select.args.get("joins", []) or []:
        inner = join.this
        if isinstance(inner, exp.Table):
            names.add(_norm_ident(inner.name))
        else:
            for tbl in join.find_all(exp.Table):
                names.add(_norm_ident(tbl.name))

    return sorted(names)


def _extract_join_edges(
    select: exp.Select, alias_map: dict[str, str]
) -> list[JoinEdge]:
    """JoinEdge 집합 추출.

    left_table은 FROM 절의 첫 테이블(앵커)로 고정한다. canonical_key가
    left/right 순서를 정렬하므로 의미상 무방하며, A/B 간 비교에서
    일관성이 확보된다.
    """
    edges: list[JoinEdge] = []

    # 앵커 (FROM 절 첫 테이블)
    anchor = ""
    from_ = select.args.get("from_") or select.args.get("from")
    if from_ is not None:
        first = from_.find(exp.Table)
        if first is not None:
            anchor = _norm_ident(first.name)

    for join in select.args.get("joins", []) or []:
        if join.args.get("on") is None and not (
            join.args.get("side") or join.args.get("kind")
        ):
            continue
        side = (join.args.get("side") or "").upper()
        kind = (join.args.get("kind") or "").upper()
        if "CROSS" in kind:
            jtype = "CROSS"
        elif side in ("LEFT", "RIGHT", "FULL"):
            jtype = side
        else:
            jtype = "INNER"

        right_name = ""
        inner = join.this
        if isinstance(inner, exp.Table):
            right_name = _norm_ident(inner.name)

        on_expr = join.args.get("on")
        preds: list[str] = []
        if on_expr is not None:
            for part in _split_and(on_expr):
                preds.append(_canonical_expr(part, alias_map))

        edges.append(
            JoinEdge(
                left_table=anchor,
                right_table=right_name,
                join_type=jtype,
                on_predicates=sorted(preds),
            )
        )

    return edges


def _extract_all_predicates(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    """WHERE + HAVING 통합 predicate 집합."""
    parts: list[str] = []

    where = select.args.get("where")
    if where is not None:
        for p in _split_and(where.this):
            parts.append(_canonical_expr(p, alias_map))

    having = select.args.get("having")
    if having is not None:
        for p in _split_and(having.this):
            parts.append(_canonical_expr(p, alias_map))

    return sorted(parts)


def _extract_group_keys(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    group = select.args.get("group")
    if group is None:
        return []
    return sorted([_canonical_expr(e, alias_map) for e in group.expressions])


def _extract_aggregates_and_projections(
    select: exp.Select, alias_map: dict[str, str]
) -> tuple[list[tuple[str, str]], list[str]]:
    """SELECT 절에서 집계식과 비집계 출력을 분리.

    - aggregates: (함수명, 인자 canonical) 튜플 집합 (정렬)
    - projections: 비집계 출력 canonical 문자열 집합 (정렬)
    """
    aggregates: list[tuple[str, str]] = []
    projections: list[str] = []

    for proj in select.expressions:
        base = proj.this if isinstance(proj, exp.Alias) else proj

        found_agg = False
        for func in base.find_all(exp.Func):
            fname = _normalize_function_name(
                func.sql_name() or type(func).__name__
            )
            if fname in _AGG_FUNCTIONS:
                arg = ""
                if "this" in func.args and isinstance(
                    func.args["this"], exp.Expression
                ):
                    arg = _canonical_expr(func.args["this"], alias_map)
                elif (
                    "expressions" in func.args
                    and func.args["expressions"]
                ):
                    arg = _canonical_expr(
                        func.args["expressions"][0], alias_map
                    )
                aggregates.append((fname, arg))
                found_agg = True
                break

        if not found_agg:
            projections.append(_canonical_expr(proj, alias_map))

    aggregates.sort()
    projections.sort()
    return aggregates, projections


def build_logical_plan(
    tree: exp.Expression, limitations: list[str]
) -> LogicalPlan:
    """정규화된 AST에서 LogicalPlan 생성.

    `limitations`는 optimizer 단계에서 채워진 사유 목록을 그대로 보존해
    이후 비교 단계에서 판정 근거로 활용한다.
    """
    select = _top_select(tree)
    if select is None:
        return LogicalPlan(limitations=limitations + ["SELECT 문을 찾을 수 없습니다."])

    alias_map = _build_alias_map(select)

    base_tables = _extract_base_tables(select)
    join_edges = _extract_join_edges(select, alias_map)
    all_predicates = _extract_all_predicates(select, alias_map)
    group_keys = _extract_group_keys(select, alias_map)
    aggregates, projections = _extract_aggregates_and_projections(
        select, alias_map
    )

    return LogicalPlan(
        base_tables=base_tables,
        join_edges=join_edges,
        all_predicates=all_predicates,
        group_keys=group_keys,
        aggregates=aggregates,
        projections=projections,
        limitations=list(limitations),
    )
