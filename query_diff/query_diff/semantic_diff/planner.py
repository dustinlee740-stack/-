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
    _display_expr,
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


def _join_type(join: exp.Join) -> str:
    """조인 타입 문자열(INNER/LEFT/RIGHT/FULL/CROSS)."""
    side = (join.args.get("side") or "").upper()
    kind = (join.args.get("kind") or "").upper()
    if "CROSS" in kind:
        return "CROSS"
    if side in ("LEFT", "RIGHT", "FULL"):
        return side
    return "INNER"


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
        jtype = _join_type(join)

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


def join_display_labels(tree: exp.Expression) -> dict[tuple[str, str], str]:
    """패스스루 해소 **이전** 트리에서 조인별 표시 라벨을 만든다(CTE 경계 존중).

    라벨은 각 조인의 **등치 조인 키**(양변이 모두 `테이블.컬럼`)가 실제로 잇는 두 엔티티를
    쿼리에 쓰인 이름 그대로 보여준다:
      - 실제 테이블 → 테이블명
      - 파생 스코프(CTE/서브쿼리)가 단일 베이스 → 그 베이스명 (예: `ksd` → `service_discount`)
      - 파생 스코프가 다중 베이스(환원 불가) → 파생/CTE 이름 (예: `address_info`)
    반환: `(right_table, join_type)` → `"SIDE_A ↔ SIDE_B"`(정렬·대문자). 등치 키가 없거나
    조인 대상(right)이 테이블이 아니면(무명 서브쿼리 조인 등) 항목을 생략 → 호출측이 폴백.

    **표시 전용**이다. 조인 매칭은 여전히 패스스루 해소된 베이스 테이블 집합(`_edge_table_set`)을
    쓴다 — 평면 조인 쿼리와 CTE 쿼리를 같은 조인으로 짝짓기 위함.
    """
    # 파생 스코프 별칭 → 표시명: 단일 베이스면 그 베이스, 다중 베이스면 파생명 자체(환원 불가)
    derived_disp: dict[str, str] = {}
    for alias, sel in _derived_selects(tree):
        bases = _extract_base_tables(sel)
        derived_disp[alias] = bases[0] if len(set(bases)) == 1 else alias

    def _disp(name: str) -> str:
        return derived_disp.get(name, name)

    labels: dict[tuple[str, str], str] = {}
    for sel in _all_selects(tree):
        amap = _build_alias_map(sel)
        for join in sel.args.get("joins", []) or []:
            inner = join.this
            if not isinstance(inner, exp.Table):
                continue
            right = _norm_ident(inner.name)
            on = join.args.get("on")
            if on is None:
                continue
            # 등치 조인 키(양변 모두 테이블.컬럼)가 잇는 테이블만 수집 — `col = 리터럴` 필터·CASE 제외
            sides: set[str] = set()
            for part in _split_and(on):
                if not isinstance(part, exp.EQ):
                    continue
                left, rt = part.left, part.right
                if not (isinstance(left, exp.Column) and isinstance(rt, exp.Column)):
                    continue
                for col in (left, rt):
                    if not col.table:
                        continue
                    ref = _norm_ident(col.table)
                    sides.add(_disp(amap.get(ref, ref)))
            if len(sides) < 2:
                continue
            label = " ↔ ".join(sorted(s.upper() for s in sides if s))
            labels.setdefault((right, _join_type(join)), label)
    return labels


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


def _extract_pred_provenance(
    select: exp.Select, alias_map: dict[str, str]
) -> list[tuple[str, str]]:
    """WHERE→HAVING **절 순서**로 `(canonical, display)` 쌍 목록. 항상 참인 필러 제외.

    canonical 은 매칭·정렬 색인 키, display 는 표시용 자연형(`컬럼 op 값`·`!=`). 표시 순서·문법
    복원용 provenance(비교 집합과 별개)."""
    out: list[tuple[str, str]] = []
    for clause in ("where", "having"):
        node = select.args.get(clause)
        if node is None:
            continue
        for p in _split_and(node.this):
            canon = _canonical_expr(p, alias_map)
            if _is_tautology(canon):
                continue
            out.append((canon, _display_expr(p, alias_map)))
    return out


def _extract_group_keys(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    group = select.args.get("group")
    if group is None:
        return []
    # 원본 GROUP BY 절 순서 보존(표시 정합) — 매칭은 집합 기반이라 순서 무관.
    return [_canonical_expr(e, alias_map) for e in group.expressions]


# --- 위치 기반(최신 1건) 집계 인식 — Oracle KEEP(DENSE_RANK FIRST/LAST) ↔ AGG(CASE WHEN rank()=k …) ---
_RANK_FUNCS = {"DENSE_RANK", "RANK", "ROW_NUMBER"}

# 위치 기반 집계 func 토큰 마커(소프트 동치 신호 탐지용)
POSITIONAL_AGG_MARK = "⟨KEEP_"


def _order_canonical(order: exp.Expression | None, alias_map: dict[str, str]) -> str:
    """ORDER BY 절을 `col DIR[, col DIR]` canonical 문자열로."""
    if order is None:
        return ""
    parts = []
    for o in order.expressions:
        col = _canonical_expr(o.this, alias_map)
        direction = "DESC" if o.args.get("desc") else "ASC"
        parts.append(f"{col} {direction}")
    return ", ".join(parts)


def _rank_class(fname: str) -> str:
    """랭크 함수 → 동률 의미 클래스. dense_rank·rank(동률 모두 1=SET) / row_number(1행=ONE).

    SET 끼리는 `=1` 이 같은 행 집합을 고르므로 동치, ONE 은 임의 1행이라 동률 시 결과가 다르다.
    """
    return "ONE" if _normalize_function_name(fname) == "ROW_NUMBER" else "SET"


def _group_canonical(select: exp.Select, alias_map: dict[str, str]) -> str:
    """GROUP BY 키 집합 canonical(정렬). 위치 집계의 '암묵 파티션' 비교용."""
    g = select.args.get("group")
    if g is None:
        return ""
    return ", ".join(sorted(_canonical_expr(e, alias_map) for e in g.expressions))


def _positional_agg_token(
    agg_func: str, rankclass: str, order_canon: str, partition_canon: str
) -> str:
    """위치 기반 집계의 func 토큰(동치 비교 키 + 관용구 마커).

    예: `MIN⟨KEEP_SET:recharge_deposit.dpsi_dttm DESC|P:recharge_deposit.rc_id⟩`.
    집계·랭크클래스·정렬키·**파티션**이 모두 같아야 A(KEEP)와 B(윈도우-CASE)가 동일 토큰으로
    수렴해 매칭된다. 파티션/랭크가 다르면 토큰이 갈려 하드 차이로 남는다.
    """
    return (
        f"{agg_func}{POSITIONAL_AGG_MARK}{rankclass}:{order_canon}"
        f"|P:{partition_canon}⟩"
    )


def _build_rank_windows(tree: exp.Expression) -> dict[str, tuple[str, str, str]]:
    """트리 전역 `랭크 윈도우 출력 alias(소문자) → (ORDER BY, PARTITION BY, rankclass)` 맵.

    `dense_rank() over (partition by p order by y desc) as rn` 같은 출력을 모아, 다른
    스코프의 `CASE WHEN rn = 1` 이 가리키는 윈도우의 정렬·파티션·랭크종류를 역참조한다.
    """
    rw: dict[str, tuple[str, str, str]] = {}
    for sel in tree.find_all(exp.Select):
        am = _build_alias_map(sel)
        for proj in sel.expressions:
            if not isinstance(proj, exp.Alias) or not isinstance(proj.this, exp.Window):
                continue
            w = proj.this
            fn = w.this
            if fn is None:
                continue
            fname = _normalize_function_name(fn.sql_name() or type(fn).__name__)
            if fname not in _RANK_FUNCS:
                continue
            order_c = _order_canonical(w.args.get("order"), am)
            part_c = ", ".join(
                sorted(_canonical_expr(p, am) for p in (w.args.get("partition_by") or []))
            )
            rw[_norm_ident(proj.alias)] = (order_c, part_c, _rank_class(fname))
    return rw


def _recognize_positional_agg(
    base: exp.Expression,
    select: exp.Select,
    alias_map: dict[str, str],
    rank_windows: dict[str, tuple[str, str, str]],
) -> tuple[str, str] | None:
    """위치 기반(최신 1건) 집계면 (func 토큰, 인자 canonical) 반환, 아니면 None.

    패턴 A: `AGG(x) KEEP(DENSE_RANK FIRST ORDER BY y)` (exp.Window, over==KEEP) — 암묵 파티션은
      소속 SELECT 의 GROUP BY.
    패턴 B: `AGG(CASE WHEN <rankcol> = 1 THEN x END)` (ELSE 없음). <rankcol> 의 윈도우
      PARTITION BY 가 **소속 SELECT 의 GROUP BY 와 같을 때만** '그룹별 최신' 으로 인식.
    토큰에 집계·랭크클래스·정렬키·파티션(GROUP BY)을 모두 담아, 파티션·랭크가 다르면 하드 차이.
    """
    group_canon = _group_canonical(select, alias_map)

    # 패턴 A — Oracle KEEP
    for w in base.find_all(exp.Window):
        if str(w.args.get("over") or "").upper() != "KEEP":
            continue
        agg = w.this
        if not isinstance(agg, exp.Func):
            continue
        aggname = _normalize_function_name(agg.sql_name() or type(agg).__name__)
        if aggname not in _AGG_FUNCTIONS:
            continue
        if not w.args.get("first"):
            continue  # FIRST(최신/선두)만 — LAST 는 별도 의미
        arg = (
            _canonical_expr(agg.this, alias_map)
            if isinstance(agg.this, exp.Expression)
            else ""
        )
        alias_node = w.args.get("alias")
        rank_name = getattr(alias_node, "name", "") if alias_node is not None else ""
        rankclass = _rank_class(rank_name)
        order_canon = _order_canonical(w.args.get("order"), alias_map)
        return (
            _positional_agg_token(aggname, rankclass, order_canon, group_canon),
            arg,
        )

    # 패턴 B — AGG(CASE WHEN rankcol = 1 THEN x END), ELSE 없음
    for f in base.find_all(exp.Func):
        aggname = _normalize_function_name(f.sql_name() or type(f).__name__)
        if aggname not in _AGG_FUNCTIONS:
            continue
        case = f.this if isinstance(f.this, exp.Case) else None
        if case is None:
            continue
        default = case.args.get("default")
        if default is not None and not isinstance(default, exp.Null):
            continue  # ELSE 가 있으면(예: SUM(CASE … ELSE 0)) 위치 집계 아님
        ifs = case.args.get("ifs") or []
        if len(ifs) != 1:
            continue
        cond = ifs[0].this
        if not isinstance(cond, exp.EQ):
            continue
        win = None
        for side, other in ((cond.left, cond.right), (cond.right, cond.left)):
            if (
                isinstance(side, exp.Column)
                and isinstance(other, exp.Literal)
                and other.name == "1"  # rn = 1 → 최신/선두
            ):
                win = rank_windows.get(_norm_ident(side.name))
                if win is not None:
                    break
        if win is None:
            continue
        order_canon, part_canon, rankclass = win
        # 윈도우 PARTITION BY 가 GROUP BY 와 같을 때만 '그룹별 최신' = A 의 KEEP 과 동형
        if part_canon != group_canon:
            continue
        arg = (
            _canonical_expr(ifs[0].args.get("true"), alias_map)
            if isinstance(ifs[0].args.get("true"), exp.Expression)
            else ""
        )
        return (
            _positional_agg_token(aggname, rankclass, order_canon, group_canon),
            arg,
        )
    return None


def _extract_aggregates_and_projections(
    select: exp.Select,
    alias_map: dict[str, str],
    rank_windows: dict[str, str] | None = None,
) -> tuple[list[tuple[str, str]], list[str]]:
    """SELECT 절에서 집계식과 비집계 출력을 분리.

    - aggregates: (함수명, 인자 canonical) 튜플 집합 (정렬). 위치 기반(최신 1건) 집계는
      함수명에 `⟨KEEP_…⟩` 마커를 단 토큰으로 표현(KEEP↔윈도우 관용구 동치 + 소프트 노트용).
    - projections: 비집계 출력 canonical 문자열 집합 (정렬)
    """
    rank_windows = rank_windows or {}
    aggregates: list[tuple[str, str]] = []
    projections: list[str] = []

    for proj in select.expressions:
        base = proj.this if isinstance(proj, exp.Alias) else proj

        positional = _recognize_positional_agg(base, select, alias_map, rank_windows)
        if positional is not None:
            aggregates.append(positional)
            continue

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
    # projections 는 정렬하지 않는다 — 최외곽 select(쿼리) 순서를 표시에 보존(group_keys 와 동일).
    return aggregates, projections


def projection_aliases(tree: exp.Expression) -> dict[str, str]:
    """최외곽 SELECT 의 출력 별칭 맵: canonical 식 → 출력명(별칭).

    표시에서 canonical 폴백(원문 raw 단위 매칭 실패 — 예: CTE 인라인된 CASE)에 별칭을 덧붙이기 위함.
    canonical 은 `plan.projections`(=`_extract_aggregates_and_projections`)와 동일하게
    `_canonical_expr(식, 최외곽 alias_map)` 로 만들어 키를 정합시킨다. 집계 별칭도 포함될 수 있으나
    조회는 projection 에서만 하므로 무해. **GROUP BY 표시에도 재사용** — group-by 가 참조하는 SELECT
    출력이 최외곽에 인라인되면 group key canonical == 해당 SELECT canonical 이라 같은 키로 매칭된다."""
    top = _top_select(tree)
    if top is None:
        return {}
    amap = _build_alias_map(top)
    out: dict[str, str] = {}
    for proj in top.expressions:
        if isinstance(proj, exp.Alias) and proj.alias:
            out.setdefault(_canonical_expr(proj, amap), proj.alias)
    return out


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


def _derived_selects(tree: exp.Expression) -> list[tuple[str, exp.Select]]:
    """파생 테이블(별칭 있는 CTE + 인라인 서브쿼리)의 (별칭, SELECT) 목록.

    CTE(`WITH txn AS (...)`)뿐 아니라 `FROM/JOIN (SELECT ...) c` 형태의 인라인
    서브쿼리도 포함한다. 둘 다 바깥에서 `별칭.컬럼` 으로 참조되는 파생 테이블이므로
    동일하게 pass-through 해소 대상이다.
    """
    out: list[tuple[str, exp.Select]] = []
    for cte in tree.find_all(exp.CTE):
        if cte.alias:
            sel = cte.this if isinstance(cte.this, exp.Select) else cte.this.find(exp.Select)
            if sel is not None:
                out.append((_norm_ident(cte.alias), sel))
    for sq in tree.find_all(exp.Subquery):
        alias = sq.alias
        if alias:
            sel = sq.this if isinstance(sq.this, exp.Select) else sq.find(exp.Select)
            if sel is not None:
                out.append((_norm_ident(alias), sel))
    return out


def resolve_derived_passthrough(tree: exp.Expression) -> exp.Expression:
    """파생 테이블(CTE + 인라인 서브쿼리)의 단순 컬럼 통과를 원천 베이스 컬럼으로 해소.

    `txn.stlm_mc_id`(WITH CTE)뿐 아니라 `c.player_id`처럼 **인라인 서브쿼리**
    (`FROM/JOIN (SELECT ...) c`)의 출력 컬럼도 원천 베이스 컬럼
    (`recharge_deposit.player_id`)으로 치환한다. 이로써 WITH/서브쿼리로 먼저 푼 쪽과
    JOIN 으로 직접 푼 쪽이 같은 베이스 조인으로 식별된다. 집계·표현식 출력
    (`txn.원결제금액`, `grp.grp_nm`)은 통과가 아니라 그대로 둔다(조인키 아님).
    파생 테이블이 없으면 무동작.

    중첩 파생 테이블(서브쿼리 위의 서브쿼리)은 변화가 없을 때까지 반복(fixpoint)한다.
    베이스 테이블명은 파생 별칭이 아니므로 재매칭되지 않아 수렴이 보장되며,
    상한(6회)은 병리적 입력 대비 안전장치다.
    """
    if not _derived_selects(tree):
        return tree
    tree = tree.copy()

    for _ in range(6):
        pmap: dict[str, dict[str, tuple[str, str]]] = {}
        for alias, sel in _derived_selects(tree):
            pmap[alias] = _passthrough_outputs(sel, _build_alias_map(sel))
        if not pmap:
            break

        global_alias = _build_alias_map(tree)  # 외부 별칭(t→txn, g→grp, c→서브쿼리) 해소용
        changed = False
        for col in tree.find_all(exp.Column):
            if not col.table:
                continue
            scope = global_alias.get(_norm_ident(col.table), _norm_ident(col.table))
            if scope not in pmap:
                continue
            res = pmap[scope].get(_norm_ident(col.name))
            if not res:
                continue
            base_tbl, base_col = res
            if _norm_ident(col.table) != base_tbl or _norm_ident(col.name) != base_col:
                col.set("table", exp.to_identifier(base_tbl))
                col.set("this", exp.to_identifier(base_col))
                changed = True
        if not changed:
            break
    return tree


# 하위호환: 기존 import 명(resolve_cte_passthrough) 유지 — 의미는 CTE+서브쿼리로 확장됨.
resolve_cte_passthrough = resolve_derived_passthrough


def recover_column_qualifiers(tree: exp.Expression) -> exp.Expression:
    """미한정 컬럼의 테이블 한정을 회복한다(옵티마이저 폴백 보정).

    sqlglot 옵티마이저(qualify)는 스키마 없이 해소 불가한 컬럼이 있으면 **전체 폴백**한다
    (예: A의 `decode(b.RCGR_TYPE, …, RCGR_TYPE)` 미한정 기본값 → OptimizeError → raw AST).
    폴백 시 한쪽(B)은 한정, 다른쪽(A)은 미한정으로 남아 **같은 컬럼이 다르게 보인다**.
    두 전략으로 보정하되, 결정 못 하면 보존(=identity, 안전):

    1. **단일 테이블 스코프**: 소속 SELECT 의 직접 소스가 베이스 테이블 1개뿐(파생/다중 아님)
       이면 그 테이블로 한정.
    2. **동명 한정 형제**: 그 외에는, 같은 SELECT 스코프 안에 같은 이름의 컬럼이 **유일한
       테이블로 한정**돼 있으면 그 테이블로 한정(`decode(b.RCGR_TYPE, …, RCGR_TYPE)` 의 bare
       기본값을 형제 `b.RCGR_TYPE` 로 해소).

    직접 FROM/JOIN 소스·같은 스코프 형제만 본다(서브쿼리 내부로 내려가지 않음).
    """
    tree = tree.copy()
    for col in tree.find_all(exp.Column):
        if col.table:
            continue
        sel = col.find_ancestor(exp.Select)
        if sel is None:
            continue

        # 전략 1: 단일 베이스 테이블 스코프
        from_ = sel.args.get("from_") or sel.args.get("from")
        sources = ([from_.this] if from_ is not None else []) + [
            j.this for j in (sel.args.get("joins") or [])
        ]
        tbls: set[str] = set()
        derived = False
        for s in sources:
            if isinstance(s, exp.Table):
                tbls.add(_norm_ident(s.name))
            else:
                derived = True  # 서브쿼리 등 파생 소스 — 모호
        if not derived and len(tbls) == 1:
            col.set("table", exp.to_identifier(next(iter(tbls))))
            continue

        # 전략 2: 같은 스코프의 동명 한정 형제가 유일 테이블이면 그 테이블로
        amap = _build_alias_map(sel)
        name = _norm_ident(col.name)
        cand: set[str] = set()
        for other in sel.find_all(exp.Column):
            if (
                other.table
                and _norm_ident(other.name) == name
                and other.find_ancestor(exp.Select) is sel
            ):
                tref = _norm_ident(other.table)
                cand.add(amap.get(tref, tref))
        if len(cand) == 1:
            col.set("table", exp.to_identifier(next(iter(cand))))
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
    rank_windows = _build_rank_windows(tree)  # 교차 스코프 랭크 윈도우 역참조용

    base: set[str] = set()
    where_preds: set[str] = set()
    having_preds: set[str] = set()
    aggs: set[tuple[str, str]] = set()
    edges: list[JoinEdge] = []
    seen_edge_keys: set[str] = set()
    pred_display: dict[str, str] = {}   # canonical → 표시용 자연형
    pred_order: dict[str, int] = {}     # canonical → 원문 등장 순서(전 스코프 누적)

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

        # 표시용 provenance(절 순서·자연문법) — 비교 집합과 별개, 최초 등장 기준으로 누적.
        for canon, disp in _extract_pred_provenance(sel, amap):
            pred_display.setdefault(canon, disp)
            if canon not in pred_order:
                pred_order[canon] = len(pred_order)

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

        a, _pr = _extract_aggregates_and_projections(sel, amap, rank_windows)
        for fn, arg in a:
            if not _arg_refs_cte(arg, cte_names):
                aggs.add((fn, arg))

    # group_keys / projections 는 **최외곽 select** 기준(최종 집계 단위).
    # 전 스코프 합집합은 2단계 집계에서 내부 CTE의 더 잘게 쪼갠 키까지 끌어와 noise를 만든다.
    top = _top_select(tree)
    top_amap = _build_alias_map(top) if top is not None else {}
    group_keys = _extract_group_keys(top, top_amap) if top is not None else []
    _, projections = (
        _extract_aggregates_and_projections(top, top_amap, rank_windows)
        if top is not None
        else ([], [])
    )

    return LogicalPlan(
        base_tables=sorted(base),
        join_edges=edges,
        all_predicates=sorted(where_preds | having_preds),
        where_predicates=sorted(where_preds),
        having_predicates=sorted(having_preds),
        pred_display=pred_display,
        pred_order=pred_order,
        group_keys=group_keys,   # 쿼리 절 순서 보존(표시용) — 정렬 안 함
        aggregates=sorted(aggs),
        projections=projections,   # 쿼리 절 순서 보존(표시용) — group_keys 와 동일, 정렬 안 함

        limitations=list(limitations),
    )
