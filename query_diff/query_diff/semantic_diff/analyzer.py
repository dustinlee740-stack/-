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

import re

from query_diff.models import (
    Dialect,
    DimensionName,
    DimensionResult,
    LogicalPlan,
    SemanticDiff,
    SemanticVerdict,
)
from query_diff.semantic_diff.ods_lineage import reconcile_ods_base
from query_diff.semantic_diff.optimizer import _detect_limitations, normalize_query
from query_diff.semantic_diff.planner import (
    POSITIONAL_AGG_MARK,
    build_logical_plan,
    recover_column_qualifiers,
    resolve_derived_passthrough,
)
from query_diff.semantic_diff.plan_compare import (
    _absorb_date_range,
    _absorb_parameterized,
    _absorb_qualifier_noise,
    _bare_cols,
    _da,
    _DATE_RANGE_CAVEAT,
    _year_month_detail,
    _diff_sets,
    _diff_sets_by_column,
    _group_edges,
    _lookup_raw_on,
    _orig_text,
    _RawSrc,
    _raw_group_map,
    _raw_on_map,
    _raw_predicate_map,
    _raw_select_map,
    _ref_cols,
    _upper_disp,
)
from query_diff.semantic_diff.decorrelation import (
    DecorrelationInfo,
    decorrelation_caveat,
    detect_decorrelation,
    excise_decorrelation,
)
from query_diff.structure_diff.normalizer import YEAR_MONTH_MARK
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


def _diff_lines(headline: str, parts: list[str], guidance: str = "") -> str:
    """불일치 차원 설명을 **다중 줄**로 구성(가독성) — 헤드라인 / A·B 항목(각 줄) / 안내.

    프런트엔드는 explanation 을 `white-space:pre-line` 으로 렌더하므로 `\\n` 이 줄바꿈이 된다.
    한 줄 run-on(`— … / … . (…)`) 대신 직관적인 블록 형태로 보여준다.
    """
    lines = [headline, *parts]
    if guidance:
        lines.append(guidance)
    return "\n".join(lines)


def _compare_base_tables(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str] | None = None
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.base_tables, b.base_tables)
    caveats: list[str] = []
    if not matched:
        # ODS 집계 테이블을 정의 쿼리의 원천 스파인으로 귀속(게이트: 정의 있을 때만). 사이드이펙트 0.
        oa, ob, caveats = reconcile_ods_base(oa, ob, a.base_tables, b.base_tables)
        matched = not oa and not ob
    oa = [_upper_disp(t) for t in _da(oa, rename)]
    ob = [_upper_disp(t) for t in ob]
    if matched:
        expl = (
            "읽는 테이블 — ODS 집계 경유분을 원천으로 귀속하면 동일 (실데이터 대사 필요)"
            if caveats
            else f"읽는 테이블 {len(sh)}개 모두 동일 — {', '.join(_upper_disp(t) for t in sh)}"
        )
    else:
        parts = []
        if oa:
            parts.append(f"A에만 있는 테이블: {', '.join(oa)}")
        if ob:
            parts.append(f"B에만 있는 테이블: {', '.join(ob)}")
        expl = _diff_lines("읽는 기본 테이블이 다릅니다", parts)
    return DimensionResult(
        dimension=DimensionName.BASE_TABLES,
        matched=matched,
        limited=bool(matched and caveats),   # 귀속으로 동일해진 경우 제한적(대사 필요)
        only_in_a=oa,
        only_in_b=ob,
        shared=sh,
        explanation=expl,
        caveat="\n\n".join(caveats) if caveats else "",
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
        label = "↔".join(sorted(t.upper() for t in tables))
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

    # 원문(원본 ON·확인 컬럼) 대문자 통일 — 라벨은 위에서 이미 대문자, ON/컬럼은 따옴표 밖만 대문자.
    only_a = [_upper_disp(s) for s in only_a]
    only_b = [_upper_disp(s) for s in only_b]
    matched = not only_a and not only_b
    param_note = (
        f" · 값만 다른 항목(날짜·코드 등) {param_cnt}개는 비교 제외" if param_cnt else ""
    )
    if matched:
        expl = (
            f"테이블 연결(JOIN) 모두 동일{param_note}"
            if (shared_cnt or param_cnt)
            else "양쪽 모두 조인 없음"
        )
    else:
        expl = _diff_lines(
            "테이블 연결 방식(JOIN)이 다릅니다" + param_note,
            only_a + only_b,
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
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str] | None = None,
    raw_pred_a: _RawSrc | None = None,
    raw_pred_b: _RawSrc | None = None,
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets(a.all_predicates, b.all_predicates)
    oa, ob, param = _absorb_parameterized(oa, ob)
    oa, ob, _qnoise = _absorb_qualifier_noise(oa, ob)   # 한정자만 다른 동일 술어(노이즈) 흡수
    oa, ob, date_range = _absorb_date_range(oa, ob)     # 원시↔일추출 날짜범위(제한적) 흡수
    oa = _da(oa, rename)
    matched = not oa and not ob
    # 차이 술어는 **원문 그대로·대문자 통일**(원본 별칭·연산자·값) 노출 — 쿼리에서 바로 찾게.
    disp_a = _orig_text(oa, raw_pred_a)
    disp_b = _orig_text(ob, raw_pred_b)
    param_note = (
        f" · 값만 다른 항목(날짜·코드 등) {len(param)}개는 비교 제외" if param else ""
    )
    if matched:
        expl = (
            f"조회 조건(WHERE/HAVING) {len(sh)}건 모두 동일{param_note}"
            if sh or param
            else "양쪽 모두 조회 조건 없음"
        )
        if date_range:
            expl += " · 날짜 범위(원시↔일추출) 동치 간주(제한적)"
    else:
        parts = []
        if disp_a:
            parts.append(f"A 쿼리에만: {', '.join(_ref_cols(disp_a)) or ', '.join(disp_a)}")
        if disp_b:
            parts.append(f"B 쿼리에만: {', '.join(_ref_cols(disp_b)) or ', '.join(disp_b)}")
        expl = _diff_lines(
            "조회 조건(WHERE/HAVING)이 다릅니다" + param_note,
            parts,
            "해당 쿼리 WHERE 절에서 위 조건을 확인하세요",
        )
    return DimensionResult(
        dimension=DimensionName.PREDICATES,
        matched=matched,
        limited=bool(matched and date_range),
        only_in_a=disp_a,
        only_in_b=disp_b,
        shared=sh,
        explanation=expl,
        caveat=_DATE_RANGE_CAVEAT if (matched and date_range) else "",
    )


def _ym_token_col(tok: str) -> str | None:
    """`⟨YM:{col}:{gran}⟩` → col(테이블 한정 컬럼). 형식 아니면 None."""
    if not tok.startswith(YEAR_MONTH_MARK) or not tok.endswith("⟩"):
        return None
    inner = tok[len(YEAR_MONTH_MARK):-1]   # "{col}:{gran}"
    col, _, _gran = inner.rpartition(":")
    return col or None


def _ym_status(shared: list[str], op_an: OpAnMap | None) -> tuple[bool, bool]:
    """(연-월 관용구 존재, 타입확정 신뢰). 모든 YM 컬럼이 양쪽 시간형이면 reliable=True.

    reliable 이면 동일(✓)로 승격, 아니면(미상/비시간형/op_an 없음) 제한적 판정 유지."""
    toks = [s for s in shared if YEAR_MONTH_MARK in s]
    if not toks:
        return False, False
    if op_an is None:
        return True, False
    reliable = all(
        (c := _ym_token_col(t)) is not None and op_an.temporal_reliable(c)
        for t in toks
    )
    return True, reliable


def _compare_group_keys(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str] | None = None,
    op_an: OpAnMap | None = None,
    raw_group_a: _RawSrc | None = None,
    raw_group_b: _RawSrc | None = None,
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets_by_column(a.group_keys, b.group_keys)
    oa = _da(oa, rename)
    # 연-월 관용구로 일치한 경우: 타입 확정이면 동일(✓), 아니면 제한적 판정.
    ym_present, ym_reliable = _ym_status(sh, op_an)
    ym_soft = ym_present and not ym_reliable
    # 표시는 **원문 GROUP BY 식 그대로**(내부 토큰 ⟨YM:⟩ 미노출, 대문자 통일).
    disp_a = _orig_text(oa, raw_group_a)
    disp_b = _orig_text(ob, raw_group_b)
    if matched:
        expl = (
            f"묶음 기준(GROUP BY) {len(sh)}개 모두 동일"
            if sh
            else "양쪽 모두 GROUP BY 없음"
        )
        if ym_present and ym_reliable:
            expl += " · 날짜 추출 관용구 인식(타입 검증)"
    else:
        parts = []
        if disp_a:
            parts.append(f"A 쿼리에만: {', '.join(_ref_cols(disp_a)) or ', '.join(disp_a)}")
        if disp_b:
            parts.append(f"B 쿼리에만: {', '.join(_ref_cols(disp_b)) or ', '.join(disp_b)}")
        expl = _diff_lines(
            "묶음 기준(GROUP BY)이 다릅니다",
            parts,
            "해당 쿼리 GROUP BY 절에서 위 조건을 확인하세요. 한쪽만 묶으면 합계 단위가 달라집니다",
        )
    # 제한적 판정 캐비엣은 **실제 GROUP BY 추출식·정확한 입도**로 동적 생성(하드코딩 아님).
    caveat = (
        _year_month_detail(sh, [raw_group_a], [raw_group_b], rename)[0]
        if (matched and ym_soft) else ""
    )
    return DimensionResult(
        dimension=DimensionName.GROUP_KEYS,
        matched=matched,
        limited=bool(matched and ym_soft),
        only_in_a=disp_a,
        only_in_b=disp_b,
        shared=sh,
        explanation=expl,
        caveat=caveat,
    )


def _compare_aggregates(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str] | None = None,
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
) -> DimensionResult:
    # tuple(func, arg) → 문자열 표현으로 집합 비교
    def _fmt(pairs: list[tuple[str, str]]) -> list[str]:
        return [f"{f}({g})" for f, g in pairs]

    sa, sb = _fmt(a.aggregates), _fmt(b.aggregates)
    matched, oa, ob, sh = _diff_sets(sa, sb)
    oa = _da(oa, rename)
    # 표시는 **원문 집계식 그대로**(내부 토큰 MAX⟨KEEP_…⟩ 미노출, 대문자 통일).
    disp_a = _orig_text(oa, raw_select_a)
    disp_b = _orig_text(ob, raw_select_b)

    # 소프트 신호: 매칭된 집계 중 정렬 기반 "최신 1건" 관용구(KEEP↔윈도우)는 자동 동치로
    # 처리하되, 진짜 잔여(정렬 키 NULL 처리)를 구조화 주의블록(caveat)으로 안내한다(과추출 우선).
    soft = sum(1 for s in sh if POSITIONAL_AGG_MARK in s)
    caveat = (
        "단, 정렬 Key에 NULL이 있는 경우 Oracle·Hive 기본 정렬 차이로 조회 데이터에 차이가 발생할 수 있습니다.\n"
        "Oracle : NULL FIRST\n"
        "Hive : NULL LAST\n"
        "→ 정렬 기준 검토 필요"
        if soft
        else ""
    )

    if matched:
        expl = f"집계식 {len(sh)}개 모두 동일" if sh else "양쪽 모두 집계 없음"
    else:
        parts = []
        if disp_a:
            parts.append(f"A 쿼리: {', '.join(disp_a)}")
        if disp_b:
            parts.append(f"B 쿼리: {', '.join(disp_b)}")
        expl = _diff_lines(
            "계산식(SELECT 집계)이 다릅니다",
            parts,
            "각 쿼리 SELECT 절에서 위 집계식을 확인하세요",
        )
    return DimensionResult(
        dimension=DimensionName.AGGREGATES,
        matched=matched,
        # 소프트 동치(관용구)로만 통과한 경우 = 제한적 판정(✓ 통과 아님 — 확인 권장)
        limited=bool(matched and soft),
        only_in_a=disp_a,
        only_in_b=disp_b,
        shared=sh,
        explanation=expl,
        caveat=caveat,
    )


def _compare_projections(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str] | None = None,
    op_an: OpAnMap | None = None,
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
) -> DimensionResult:
    matched, oa, ob, sh = _diff_sets_by_column(a.projections, b.projections)
    oa = _da(oa, rename)
    ym_present, ym_reliable = _ym_status(sh, op_an)
    ym_soft = ym_present and not ym_reliable
    # 표시는 **원문 SELECT 식 그대로**(내부 토큰·정규화 CASE 미노출, 대문자 통일).
    disp_a = _orig_text(oa, raw_select_a)
    disp_b = _orig_text(ob, raw_select_b)
    if matched:
        expl = "출력 컬럼(SELECT) 모두 동일"
        if ym_present and ym_reliable:
            expl += " · 날짜 추출 관용구 인식(타입 검증)"
    else:
        parts = []
        if disp_a:
            parts.append(f"A 쿼리에만: {', '.join(_ref_cols(disp_a)) or ', '.join(disp_a)}")
        if disp_b:
            parts.append(f"B 쿼리에만: {', '.join(_ref_cols(disp_b)) or ', '.join(disp_b)}")
        expl = _diff_lines(
            "출력(SELECT) 컬럼이 다릅니다",
            parts,
            "해당 쿼리 SELECT 절에서 위 출력을 확인하세요",
        )
    caveat = (
        _year_month_detail(sh, [raw_select_a], [raw_select_b], rename)[0]
        if (matched and ym_soft) else ""
    )
    return DimensionResult(
        dimension=DimensionName.PROJECTIONS,
        matched=matched,
        limited=bool(matched and ym_soft),
        only_in_a=disp_a,
        only_in_b=disp_b,
        shared=sh,
        explanation=expl,
        caveat=caveat,
    )


# 차원 → 사람이 읽는 짧은 라벨(문제 총합 롤업용)
_DIM_LABEL: dict[DimensionName, str] = {
    DimensionName.BASE_TABLES: "읽는 테이블",
    DimensionName.JOIN_GRAPH: "테이블 연결(JOIN)",
    DimensionName.PREDICATES: "조회 조건(WHERE·HAVING)",
    DimensionName.GROUP_KEYS: "묶음 기준(GROUP BY)",
    DimensionName.AGGREGATES: "집계식",
    DimensionName.PROJECTIONS: "출력 컬럼(SELECT)",
}


def _issue_diff(d: DimensionResult) -> str:
    """불일치 차원의 짧은 요약(A에만/B에만 핵심 — 상세는 차원별 비교에)."""
    def _cap(items: list[str]) -> str:
        head = ", ".join(items[:3])
        return head + (" …" if len(items) > 3 else "")
    parts = []
    if d.only_in_a:
        parts.append("A에만 " + _cap(d.only_in_a))
    if d.only_in_b:
        parts.append("B에만 " + _cap(d.only_in_b))
    return " / ".join(parts) if parts else "다름"


def _short_limitation(lim: str) -> str:
    """정규화 한계 한 줄 — 좌표(Line/Col) 노이즈 제거."""
    return re.sub(r"\s*Line:\s*\d+,\s*Col:\s*\d+", "", lim).strip()


def _decide_verdict(
    dims: list[DimensionResult], limitations: list[str]
) -> tuple[SemanticVerdict, str, list[str]]:
    unmatched_core = [
        d for d in dims if d.dimension in _CORE_DIMENSIONS and not d.matched
    ]
    limited_dims = [d for d in dims if d.limited]

    # 전 차원 문제 총합(verdict 무관하게 모두 수집) — ✗ 차이 / ⚠ 제한·주의
    issues: list[str] = []
    for d in unmatched_core:
        issues.append(f"✗ {_DIM_LABEL.get(d.dimension, d.dimension.value)}: {_issue_diff(d)}")
    for d in limited_dims:
        detail = (d.caveat or d.explanation).splitlines()[0] if (d.caveat or d.explanation) else "확인 권장"
        issues.append(f"⚠ {_DIM_LABEL.get(d.dimension, d.dimension.value)} 제한적 판정 — {detail}")
    for lim in limitations:
        issues.append(f"⚠ 정규화 제한 — {_short_limitation(lim)}")

    if unmatched_core:
        return (
            SemanticVerdict.DIVERGENT,
            "두 쿼리는 서로 다른 결과를 낼 가능성이 높습니다.",
            issues,
        )
    if limitations or limited_dims:
        return (
            SemanticVerdict.LIMITED,
            "핵심 차원은 일치하나 일부가 제한적 판정 — 완전 동치로 단정하지 않습니다.",
            issues,
        )
    return (
        SemanticVerdict.EQUIVALENT,
        "읽는 테이블·조인·필터·집계가 모두 일치 — 동일 결과로 판정됩니다.",
        issues,
    )


def _apply_decorrelation(dims: list[DimensionResult], info: DecorrelationInfo) -> None:
    """디코릴레이션 인식 시 JOIN_GRAPH 차원을 제한적 판정으로 표기.

    절제 후 JOIN_GRAPH 가 매칭(다른 실제 조인 차이 없음)이면 설명을 디코릴레이션으로 교체하고
    `limited=True`(→ verdict LIMITED + 문제 요약 합류). 다른 실제 조인 차이가 남아 있으면(✗)
    그 차이는 유지하고 디코릴레이션 캐비엇만 부가한다(이중 보고 방지 — limited 미설정)."""
    cav = decorrelation_caveat(info)
    for d in dims:
        if d.dimension != DimensionName.JOIN_GRAPH:
            continue
        d.caveat = cav
        if d.matched:
            d.limited = True
            d.explanation = (
                "테이블 연결(JOIN) — A 상관 스칼라 서브쿼리를 B는 LEFT JOIN(최신1건)으로 "
                "구현(디코릴레이션, 동치 간주)"
            )
        return


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
    try:
        tree_b, lim_b = normalize_query(sql_b, db)
    except ValueError as e:
        return SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="B 쿼리 정규화에 실패했습니다.",
            error=f"B: {e}",
        )

    # 디코릴레이션(A 상관 스칼라 서브쿼리 ↔ B LEFT JOIN 최신1건) — 정규화 직후·플랫닝 전에
    # 탐지하고 양쪽 트리에서 절제한다(거짓 차이 4개 동시 제거, 진짜 차이는 잔존). 호출 말미에
    # JOIN_GRAPH 를 제한적 판정으로 표기.
    decorr = detect_decorrelation(tree_a, tree_b)
    if decorr is not None:
        excise_decorrelation(tree_a, tree_b, decorr)
        # 절제로 사라진 구문(상관 서브쿼리·윈도우)의 제한사항은 디코릴레이션 캐비엇이 대신하므로 재계산.
        lim_a = _detect_limitations(tree_a)
        lim_b = _detect_limitations(tree_b)

    # 번역/해소 전 원본 ON·WHERE/HAVING 텍스트 확보(사용자가 원본 쿼리에서 찾을 수 있게)
    raw_on_a = _raw_on_map(tree_a)
    # 차이 표시는 **원본 소스 리터럴**에서 추출(재렌더 정규화 회피) — 트리 아닌 원본 SQL 사용.
    raw_pred_a = _raw_predicate_map(sql_a, da)
    raw_group_a = _raw_group_map(sql_a, da)
    raw_select_a = _raw_select_map(sql_a, da)

    # 순서: 파생 테이블(CTE+서브쿼리) 통과 해소 → 단일 테이블 스코프 미한정 컬럼 한정 → 번역.
    # pass-through 가 `c.player_id` 를 원본 운영명 그대로 `recharge_deposit.player_id` 로
    # 평탄화하고, qualify 가 옵티마이저 폴백으로 남은 미한정 컬럼을 회복적으로 한정한 뒤,
    # 번역이 베이스 테이블 컨텍스트로 `→ rc_id` 매핑한다(서브쿼리 출력 컬럼도 관통).
    tree_a = recover_column_qualifiers(resolve_derived_passthrough(tree_a))
    rename_a: dict[str, str] = {}
    if op_an is not None:
        tree_a, rename_a = translate_op_to_an(tree_a, op_an)

    raw_on_b = _raw_on_map(tree_b)
    raw_pred_b = _raw_predicate_map(sql_b, db)
    raw_group_b = _raw_group_map(sql_b, db)
    raw_select_b = _raw_select_map(sql_b, db)
    tree_b = recover_column_qualifiers(resolve_derived_passthrough(tree_b))

    plan_a = build_logical_plan(tree_a, lim_a)
    plan_b = build_logical_plan(tree_b, lim_b)

    # 비교는 분석명 기준, A측 표시(only_in_a·explanation의 A부분)만 원본 운영명으로 역변환.
    dims = [
        _compare_base_tables(plan_a, plan_b, rename_a),
        _compare_join_graph(plan_a, plan_b, rename_a, raw_on_a, raw_on_b),
        _compare_predicates(plan_a, plan_b, rename_a, raw_pred_a, raw_pred_b),
        _compare_group_keys(plan_a, plan_b, rename_a, op_an, raw_group_a, raw_group_b),
        _compare_aggregates(plan_a, plan_b, rename_a, raw_select_a, raw_select_b),
        _compare_projections(plan_a, plan_b, rename_a, op_an, raw_select_a, raw_select_b),
    ]

    # 디코릴레이션이면 JOIN_GRAPH 를 제한적 판정으로 표기(상관 서브쿼리↔LEFT JOIN 동치 간주).
    if decorr is not None:
        _apply_decorrelation(dims, decorr)

    # 중복 제거된 통합 제한사항
    merged_limitations = sorted({*plan_a.limitations, *plan_b.limitations})
    verdict, reason, issues = _decide_verdict(dims, merged_limitations)

    return SemanticDiff(
        verdict=verdict,
        reason=reason,
        issues=issues,
        plan_a=plan_a,
        plan_b=plan_b,
        dimensions=dims,
        limitations=merged_limitations,
    )
