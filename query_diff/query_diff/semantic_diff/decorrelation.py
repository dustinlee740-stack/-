"""상관 스칼라 서브쿼리(A) ↔ LEFT JOIN 최신1건(B) 디코릴레이션 인식.

Oracle은 SELECT 절 **상관 스칼라 서브쿼리**로 'per-key 최신값'을 구할 수 있지만, Hive는 상관
서브쿼리가 안 돼 **LEFT JOIN + ROW_NUMBER()=1(최신1건)**으로 우회한다. 같은 베이스 테이블 T에
대해 이 두 구조가 함께 보이면 디코릴레이션으로 인식하고, 비교 전 양쪽 트리에서 해당 조회를
**절제(excise)**한 뒤 나머지를 정상 비교한다 — JOIN/조건/집계/출력에 걸친 거짓 차이 4개가 동시에
사라지고, simple_nm↔mc_nm 같은 진짜 차이는 그대로 남는다. 동률 처리 등 잔여 검증 지점은 호출부가
'제한적 판정' 캐비엇으로 안내한다(완전 동일 아님 — A KEEP DENSE_RANK+MAX vs B ROW_NUMBER).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlglot import exp


def _strip(name: str) -> str:
    """스키마/따옴표 제거한 순수 식별자(lower)."""
    return (name or "").split(".")[-1].lower().strip('"').strip("`")


def _outer_select(tree: exp.Expression) -> exp.Select | None:
    return tree.find(exp.Select)


def _from_tables(select: exp.Select) -> list[exp.Table]:
    src = select.args.get("from") or select.args.get("from_")
    return list(src.find_all(exp.Table)) if src is not None else []


def _first_col_name(node: exp.Expression | None) -> str:
    if node is None:
        return ""
    c = node.find(exp.Column)
    return _strip(c.name) if c is not None else ""


@dataclass
class _ASide:
    proj: exp.Expression   # 절제할 outer projection (스칼라 서브쿼리 포함)
    table: str             # T (base name, lower)
    order_col: str         # 최신 기준 컬럼(KEEP ORDER BY)
    value_col: str         # 집계 대상 값 컬럼
    corr_col: str          # 외부 상관 컬럼


@dataclass
class _BSide:
    join: exp.Join         # 절제할 LEFT join
    alias: str             # join 별칭
    table: str
    order_col: str         # ROW_NUMBER ORDER BY 컬럼
    value_col: str
    key_col: str           # 조인 키


@dataclass
class DecorrelationInfo:
    table: str
    a: _ASide
    b: _BSide


def _is_latest_window(select: exp.Select) -> bool:
    """파생 select 안에 순위 윈도우(ROW_NUMBER/RANK/DENSE_RANK)가 있으면 최신N건 후보."""
    for w in select.find_all(exp.Window):
        inner = w.this
        name = (
            inner.name if isinstance(inner, exp.Anonymous) else (inner.sql_name() or type(inner).__name__)
        ).upper()
        if isinstance(inner, exp.RowNumber) or name in {"ROW_NUMBER", "RANK", "DENSE_RANK"}:
            return True
    return False


def _detect_a(tree: exp.Expression) -> _ASide | None:
    """A: projection 안 상관 스칼라 서브쿼리(단일 베이스 테이블, 외부 별칭 참조)."""
    outer = _outer_select(tree)
    if outer is None:
        return None
    ftabs = _from_tables(outer)
    outer_aliases = {a.lower() for t in ftabs if (a := t.alias)} | {_strip(t.name) for t in ftabs}

    for proj in list(outer.expressions):
        inner = next((s for s in proj.find_all(exp.Select) if s is not outer), None)
        if inner is None:
            continue
        itabs = _from_tables(inner)
        if len(itabs) != 1:
            continue
        T = _strip(itabs[0].name)
        inner_scope = {a.lower() for t in itabs if (a := t.alias)} | {_strip(t.name) for t in itabs}
        # 상관: inner 의 컬럼이 외부 별칭을 참조(내부 스코프에 없는 한정자)
        corr_col = ""
        for c in inner.find_all(exp.Column):
            tref = (c.table or "").lower().split(".")[0]
            if tref and tref in outer_aliases and tref not in inner_scope:
                corr_col = _strip(c.name)
                break
        if not corr_col:
            continue
        order = inner.find(exp.Order)
        order_col = _first_col_name(order.expressions[0]) if (order and order.expressions) else ""
        agg = inner.find(exp.AggFunc)
        value_col = _first_col_name(agg.this) if agg is not None else ""
        return _ASide(proj=proj, table=T, order_col=order_col, value_col=value_col, corr_col=corr_col)
    return None


def _detect_b(tree: exp.Expression) -> _BSide | None:
    """B: 파생 테이블(최신N건 윈도우)을 우변으로 하는 LEFT JOIN."""
    outer = _outer_select(tree)
    if outer is None:
        return None
    for j in outer.args.get("joins") or []:
        if (j.args.get("side") or "").upper() != "LEFT":
            continue
        derived = next((s for s in j.this.find_all(exp.Select)), None)
        if derived is None or not _is_latest_window(j.this):
            continue
        dtabs = {_strip(t.name) for t in j.this.find_all(exp.Table)}
        if len(dtabs) != 1:
            continue
        T = next(iter(dtabs))
        alias = (j.this.alias_or_name or "").lower()
        win = next((w for w in j.this.find_all(exp.Window)), None)
        order_col = ""
        if win is not None:
            wo = win.args.get("order")
            order_col = _first_col_name(wo.expressions[0]) if (wo and wo.expressions) else ""
        on = j.args.get("on")
        key_col = _first_col_name(on) if on is not None else ""
        value_col = ""
        for e in outer.expressions:
            for c in e.find_all(exp.Column):
                if (c.table or "").lower() == alias:
                    value_col = _strip(c.name)
                    break
            if value_col:
                break
        return _BSide(join=j, alias=alias, table=T, order_col=order_col, value_col=value_col, key_col=key_col)
    return None


def detect_decorrelation(
    tree_a: exp.Expression, tree_b: exp.Expression
) -> DecorrelationInfo | None:
    """A(상관 스칼라 서브쿼리)·B(LEFT JOIN 최신N건)가 **같은 베이스 테이블**이면 인식.

    둘 다 만족할 때만 반환(고정밀) — 일반 조인/서브쿼리는 영향 없음.
    """
    a = _detect_a(tree_a)
    if a is None:
        return None
    b = _detect_b(tree_b)
    if b is None or a.table != b.table:
        return None
    return DecorrelationInfo(table=a.table, a=a, b=b)


def excise_decorrelation(tree_a: exp.Expression, tree_b: exp.Expression, info: DecorrelationInfo) -> None:
    """양쪽 트리에서 디코릴레이션 조회를 제거(in-place). 절제 후 나머지가 정상 비교된다.

    - A: 스칼라 서브쿼리를 담은 projection 제거(→ KEEP 집계·상관 predicate 소멸).
    - B: LEFT JOIN 제거 + 그 별칭 참조 projection 제거(→ join edge·rn=1·값 출력 소멸).
    """
    outer_a = _outer_select(tree_a)
    if outer_a is not None:
        outer_a.set("expressions", [e for e in outer_a.expressions if e is not info.a.proj])

    outer_b = _outer_select(tree_b)
    if outer_b is not None:
        outer_b.set("joins", [j for j in (outer_b.args.get("joins") or []) if j is not info.b.join])
        alias = info.b.alias
        outer_b.set(
            "expressions",
            [
                e
                for e in outer_b.expressions
                if not any((c.table or "").lower() == alias for c in e.find_all(exp.Column))
            ],
        )


def decorrelation_caveat(info: DecorrelationInfo) -> str:
    """제한적 판정 구조화 주의블록(차원 caveat 스타일)."""
    a, b = info.a, info.b
    a_ord = a.order_col or "정렬키"
    b_ord = b.order_col or "정렬키"
    val_a = a.value_col or "값"
    val_b = b.value_col or "값"
    key = b.key_col or a.corr_col or "키"
    return (
        "A 상관 스칼라 서브쿼리 ↔ B LEFT JOIN(최신1건) — 디코릴레이션, 동치로 간주\n"
        f"A : (SELECT {val_a} … FROM {info.table} WHERE {a.corr_col or '키'}=…) 최신 {a_ord}\n"
        f"B : LEFT JOIN ROW_NUMBER() OVER(… ORDER BY {b_ord} DESC)=1 ON {key}\n"
        f"※ 정렬키({a_ord}↔{b_ord})·값({val_a}↔{val_b})·키({key}) 매핑과 "
        "동률 처리(A KEEP DENSE_RANK+MAX vs B ROW_NUMBER) 검토 필요"
    )
