"""LogicalPlan 추출기

sqlglot optimizer가 CTE 인라인·서브쿼리 머지·컬럼 qualify를 끝낸 AST에서
차원별 정보를 뽑아 `LogicalPlan`을 만든다.

A(FROM 직접 조인)와 B(WITH CTE로 먼저 조인)는 최적화 후 동일 AST로 수렴하므로
이 단계의 추출 결과도 같아진다.
"""

from __future__ import annotations

from sqlglot import exp

from query_diff.models import JoinEdge, LogicalPlan, _TABLE_REF_RE
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


def _all_selects(tree: exp.Expression) -> list[exp.Select]:
    """트리 내 모든 SELECT 스코프(메인 + CTE + 서브쿼리)."""
    return list(tree.find_all(exp.Select))


def _cte_names(tree: exp.Expression) -> set[str]:
    """CTE 이름 집합(소문자). base table·집계 재참조 판정에서 제외용."""
    names: set[str] = set()
    for cte in tree.find_all(exp.CTE):
        alias = cte.alias
        if alias:
            names.add(_norm_ident(alias))
    return names


def _arg_refs_cte(arg: str, cte_names: set[str]) -> bool:
    """집계 인자가 CTE 파생 컬럼(재집계)인지 — `txn.원결제금액` 처럼 CTE 한정자."""
    if not arg or "." not in arg:
        return False
    return arg.split(".", 1)[0].strip().lower() in cte_names


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


def _is_tautology(pred: str) -> bool:
    """항상 참인 무의미 술어(예: `1 = 1`, `'x' = 'x'`) 판정."""
    if " = " not in pred:
        return False
    left, _, right = pred.partition(" = ")
    return left.strip() == right.strip()


def _extract_where_predicates(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    """WHERE predicate 집합. 항상 참인 필러(1=1 등)는 제외."""
    where = select.args.get("where")
    if where is None:
        return []
    parts = [_canonical_expr(p, alias_map) for p in _split_and(where.this)]
    return sorted(p for p in parts if not _is_tautology(p))


def _extract_having_predicates(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    """HAVING predicate 집합. 항상 참인 필러(1=1 등)는 제외."""
    having = select.args.get("having")
    if having is None:
        return []
    parts = [_canonical_expr(p, alias_map) for p in _split_and(having.this)]
    return sorted(p for p in parts if not _is_tautology(p))


def _extract_all_predicates(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    """WHERE + HAVING 통합 predicate 집합. 항상 참인 필러(1=1 등)는 제외."""
    return sorted(
        _extract_where_predicates(select, alias_map)
        + _extract_having_predicates(select, alias_map)
    )


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


def _passthrough_outputs(
    select: exp.Select, alias_map: dict[str, str]
) -> dict[str, tuple[str, str]]:
    """CTE select 의 **단순 컬럼 통과(pass-through)** 출력맵.

    out_col(lower) → (base_table, base_col). 집계·표현식 출력은 제외(조인키 아님).
    """
    out: dict[str, tuple[str, str]] = {}
    base_tbls = _extract_base_tables(select)
    single = base_tbls[0] if len(set(base_tbls)) == 1 else None
    for proj in select.expressions:
        if isinstance(proj, exp.Alias):
            oname = _norm_ident(proj.alias)
            base = proj.this
        elif isinstance(proj, exp.Column):
            oname = _norm_ident(proj.name)
            base = proj
        else:
            continue
        if not isinstance(base, exp.Column):
            continue  # 집계/표현식 — 통과 아님
        col = _norm_ident(base.name)
        if base.table:
            tbl = alias_map.get(_norm_ident(base.table), _norm_ident(base.table))
        elif single:
            tbl = single
        else:
            continue
        out[oname] = (tbl, col)
    return out


def resolve_cte_passthrough(tree: exp.Expression) -> exp.Expression:
    """집계 CTE(WITH)로 만든 main spine 을 꿰뚫는다.

    `txn.stlm_mc_id` 같은 **CTE pass-through 컬럼**을 원천 베이스 컬럼
    (`ias_transaction.stlm_mc_id`)으로 치환해, WITH 로 먼저 푼 B 와 JOIN 으로 직접 푼 A 가
    같은 조인으로 식별되게 한다. 집계 출력(`txn.원결제금액`, `grp.grp_nm`)은 통과가 아니라
    그대로 둔다. CTE 가 없으면 무동작.
    """
    ctes = [c for c in tree.find_all(exp.CTE) if c.alias]
    if not ctes:
        return tree
    tree = tree.copy()
    ctes = [c for c in tree.find_all(exp.CTE) if c.alias]

    pmap: dict[str, dict[str, tuple[str, str]]] = {}
    for c in ctes:
        sel = c.this if isinstance(c.this, exp.Select) else c.this.find(exp.Select)
        if sel is None:
            continue
        pmap[_norm_ident(c.alias)] = _passthrough_outputs(sel, _build_alias_map(sel))

    if not pmap:
        return tree

    global_alias = _build_alias_map(tree)  # 외부 별칭(t→txn, g→grp) 해소용
    for col in tree.find_all(exp.Column):
        if not col.table:
            continue
        scope = global_alias.get(_norm_ident(col.table), _norm_ident(col.table))
        if scope in pmap:
            res = pmap[scope].get(_norm_ident(col.name))
            if res:
                base_tbl, base_col = res
                col.set("table", exp.to_identifier(base_tbl))
                col.set("this", exp.to_identifier(base_col))
    return tree


def build_logical_plan(
    tree: exp.Expression, limitations: list[str]
) -> LogicalPlan:
    """정규화된 AST에서 LogicalPlan 생성.

    **전 스코프 추출:** 메인 SELECT뿐 아니라 CTE·서브쿼리의 SELECT까지 모두 순회해
    base_tables/predicates/joins/aggregates를 **합집합**으로 모은다. 이로써 운영(단층
    조인)과 분석(집계 CTE 분해)이 같은 집합으로 정렬돼, 스타일 차이가 아닌 **진짜 차이**만
    드러난다. CTE 이름은 base table에서 제외하고, CTE 파생 컬럼의 재집계는 제외한다.
    CTE/서브쿼리가 없으면 단일 SELECT 추출과 동일(하위호환).
    """
    selects = _all_selects(tree)
    if not selects:
        return LogicalPlan(limitations=limitations + ["SELECT 문을 찾을 수 없습니다."])

    cte_names = _cte_names(tree)

    base: set[str] = set()
    where_preds: set[str] = set()
    having_preds: set[str] = set()
    aggs: set[tuple[str, str]] = set()
    edges: list[JoinEdge] = []
    seen_edge_keys: set[str] = set()

    # base/predicate/join/aggregate 는 전 스코프 합집합(CTE 관통)
    for sel in selects:
        amap = _build_alias_map(sel)

        for t in _extract_base_tables(sel):
            if t not in cte_names:
                base.add(t)

        for p in _extract_where_predicates(sel, amap):
            where_preds.add(p)
        for p in _extract_having_predicates(sel, amap):
            having_preds.add(p)

        for e in _extract_join_edges(sel, amap):
            # CTE 해소 후 ON 이 참조하는 테이블이 전부 CTE명일 때만(미해소 CTE↔CTE noise) 제외.
            # grp↔txn 처럼 ON 이 베이스 테이블로 풀린 조인은 유지한다.
            on_tables: set[str] = set()
            for p in e.on_predicates:
                on_tables.update(_TABLE_REF_RE.findall(p))
            if on_tables:
                if on_tables <= cte_names:
                    continue
            elif e.right_table in cte_names:
                continue
            key = e.canonical_key() if hasattr(e, "canonical_key") else str(e)
            if key not in seen_edge_keys:
                seen_edge_keys.add(key)
                edges.append(e)

        a, _pr = _extract_aggregates_and_projections(sel, amap)
        for fn, arg in a:
            if not _arg_refs_cte(arg, cte_names):
                aggs.add((fn, arg))

    # group_keys / projections 는 **최외곽 select** 기준(최종 집계 단위).
    # 전 스코프 합집합은 2단계 집계에서 내부 CTE의 더 잘게 쪼갠 키까지 끌어와 noise를 만든다.
    top = _top_select(tree)
    top_amap = _build_alias_map(top) if top is not None else {}
    group_keys = _extract_group_keys(top, top_amap) if top is not None else []
    _, projections = (
        _extract_aggregates_and_projections(top, top_amap)
        if top is not None
        else ([], [])
    )

    return LogicalPlan(
        base_tables=sorted(base),
        join_edges=edges,
        all_predicates=sorted(where_preds | having_preds),
        where_predicates=sorted(where_preds),
        having_predicates=sorted(having_preds),
        group_keys=sorted(group_keys),
        aggregates=sorted(aggs),
        projections=sorted(projections),
        limitations=list(limitations),
    )
