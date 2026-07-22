"""구조 비교 오케스트레이터

의미 비교(compare_semantic)와 **같은 정규화 프런트엔드**(옵티마이저 → 번역 →
CTE 관통 해소 → LogicalPlan 전 스코프 추출) 위에서 동작한다. 두 화면의 결론이
항상 일관되도록, 같은 LogicalPlan 차이를 **절별 DiffFinding + severity + fast-path**
형태로 렌더한다.

작성 스타일(WITH vs JOIN vs 서브쿼리)·앵커·스키마명·파라미터·NULL/''·캐스트·숫자따옴표 등
방언·표기 차이는 흡수되고, 진짜 차이만 finding 으로 남는다.

Critical 1건 이상이면 fast_path_terminate=True 로 상위 flow 에 Row diff 생략 신호를 준다.
"""

from __future__ import annotations

from query_diff.models import (
    ClauseType,
    DiffFinding,
    LogicalPlan,
    QueryInput,
    Severity,
    StructureDiff,
)
from query_diff.semantic_diff.ods_lineage import reconcile_ods_base
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.semantic_diff.plan_compare import (
    _absorb_date_range,
    _absorb_parameterized,
    _absorb_qualifier_noise,
    _bare,
    _bare_cols,
    _strip_qualifiers,
    _da,
    _DATE_RANGE_CAVEAT,
    _detranslate,
    _diff_sets,
    _diff_sets_by_column,
    _edge_reps,
    _group_edges,
    _join_label,
    _raw_on_for,
    _orig_text,
    _pred_disp1,
    _pred_display_list,
    _RawSrc,
    _raw_group_map,
    _raw_on_map,
    _raw_select_map,
    _ref_cols,
    _shape,
    _upper_disp,
    _year_month_detail,
)
from query_diff.structure_diff.rules import dominant_clause
from query_diff.structure_diff.schema_mapping import (
    IdentitySchemaMapping,
    OpAnMap,
    SchemaMapping,
    translate_op_to_an,
)
from query_diff.validation_service import _DIALECT_MAP


def recompute_state(diff: StructureDiff) -> StructureDiff:
    """findings의 user_acknowledged 반영해 fast_path/unresolved_count 재계산."""
    unresolved = [
        f for f in diff.findings
        if f.severity == Severity.CRITICAL and not f.user_acknowledged
    ]
    diff.unresolved_critical_count = len(unresolved)
    diff.fast_path_terminate = len(unresolved) > 0
    diff.dominant_clause = dominant_clause(unresolved) if unresolved else None
    diff.has_difference = bool(diff.findings)
    return diff


# --- 절별 렌더러 (LogicalPlan 차원 diff → DiffFinding) ---

def _disp(canon_items: list[str], src: _RawSrc | None) -> str:
    """canonical 차이 항목 → **원문 리터럴**(대문자·별칭·원문순서) 한 줄(의미 비교와 동일)."""
    return ", ".join(_orig_text(canon_items, src))


def _from_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets(a.base_tables, b.base_tables)
    if matched:
        return []
    # ODS 집계 테이블을 원천 스파인으로 귀속(게이트: 정의 있을 때만). 의미 비교와 결론 일치.
    oa, ob, caveats = reconcile_ods_base(oa, ob, a.base_tables, b.base_tables)
    findings: list[DiffFinding] = []
    if not oa and not ob and caveats:
        # 원천 귀속으로 동일 → CRITICAL 아닌 소프트매치 WARNING(대사 필요 지점 안내)
        return [DiffFinding(
            clause=ClauseType.FROM,
            rule_id="ODS_LINEAGE_SOFT_MATCH",
            severity=Severity.WARNING,
            a_snippet="원천 동일(귀속)",
            b_snippet="ODS 집계 경유",
            description="ODS 집계 테이블을 정의 쿼리의 원천으로 귀속하면 읽는 테이블이 동일합니다 (실데이터 대사 필요).",
            impact=" || ".join(c.replace("\n", " ") for c in caveats),
        )]
    if not oa and not ob:
        return []
    oa = [_upper_disp(t) for t in _da(oa, rename)]
    ob = [_upper_disp(t) for t in ob]
    parts = []
    if oa:
        parts.append(f"A에만: {', '.join(oa)}")
    if ob:
        parts.append(f"B에만: {', '.join(ob)}")
    findings.append(DiffFinding(
        clause=ClauseType.FROM,
        rule_id="TABLE_IDENTITY_MISMATCH",
        severity=Severity.CRITICAL,
        a_snippet=", ".join(oa),
        b_snippet=", ".join(ob),
        description="읽는 기본 테이블이 다릅니다. " + " / ".join(parts),
        impact="원천 테이블이 달라 집계 대상 자체가 다릅니다. 스키마 매핑 보강이 필요할 수 있습니다.",
    ))
    # 귀속되지 않았지만 ODS 리니지 정보가 있으면 부가 안내(정보)
    if caveats:
        findings.append(DiffFinding(
            clause=ClauseType.FROM,
            rule_id="ODS_LINEAGE_NOTE",
            severity=Severity.INFO,
            a_snippet="",
            b_snippet="ODS 집계 경유",
            description="한쪽이 ODS 집계 테이블을 읽습니다 (원천/대사 필요 지점 참고).",
            impact=" || ".join(c.replace("\n", " ") for c in caveats),
        ))
    return findings


def _join_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    raw_on_a: dict[str, str],
    raw_on_b: dict[str, str],
    disp_a: dict[tuple[str, str], str] | None = None,
    disp_b: dict[tuple[str, str], str] | None = None,
) -> list[DiffFinding]:
    """조인을 ON 참조 테이블 집합으로 페어링(앵커 무관)하고 타입·ON 술어 차이를 렌더.

    페어링은 앵커-무관 테이블집합(패스스루 해소)으로 하되, 표시 **라벨**은 CTE 경계를 존중하는
    '실제 조인 쌍'(`disp_a`/`disp_b`, `planner.join_display_labels`)으로 보여준다 — 없으면 폴백.
    """
    ga, gb = _group_edges(a.join_edges), _group_edges(b.join_edges)
    ea, eb = _edge_reps(a.join_edges), _edge_reps(b.join_edges)
    disp_a = disp_a or {}
    disp_b = disp_b or {}

    def _rep(reps: dict, ts: frozenset, types: set[str]):
        """ts 의 존재 타입 중 하나로 대표 엣지 조회(라벨 표기용)."""
        for t in sorted(types):
            r = reps.get((ts, t))
            if r is not None:
                return r
        return None

    # 테이블 집합 단위로 묶어 타입/술어를 비교 (타입 차이를 JOIN_TYPE_MISMATCH 로 분리)
    tablesets = {k[0] for k in ga} | {k[0] for k in gb}
    findings: list[DiffFinding] = []

    for ts in sorted(tablesets, key=lambda s: sorted(s)):
        a_types = {k[1] for k in ga if k[0] == ts}
        b_types = {k[1] for k in gb if k[0] == ts}
        rep_a, rep_b = _rep(ea, ts, a_types), _rep(eb, ts, b_types)
        label_a = _join_label(rep_a, disp_a, ts)
        label_b = _join_label(rep_b, disp_b, ts)
        a_preds: set[str] = set()
        for k in ga:
            if k[0] == ts:
                a_preds |= ga[k]
        b_preds: set[str] = set()
        for k in gb:
            if k[0] == ts:
                b_preds |= gb[k]

        # 한쪽에만 있는 조인
        if not a_types:
            raw = _upper_disp(_raw_on_for(raw_on_b, rep_b, ts))
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet="",
                b_snippet=label_b + (f" (ON: {raw})" if raw else ""),
                description=f"`{label_b}` 조인이 B 쿼리에만 있습니다.",
                impact="조인 대상이 한쪽에만 있으면 결과 row 수가 달라집니다.",
            ))
            continue
        if not b_types:
            raw = _upper_disp(_raw_on_for(raw_on_a, rep_a, ts))
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=label_a + (f" (ON: {raw})" if raw else ""),
                b_snippet="",
                description=f"`{label_a}` 조인이 A 쿼리에만 있습니다.",
                impact="조인 대상이 한쪽에만 있으면 결과 row 수가 달라집니다.",
            ))
            continue

        # 타입 차이
        if a_types != b_types:
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_TYPE_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=f"{'/'.join(sorted(a_types))} JOIN {label_a}",
                b_snippet=f"{'/'.join(sorted(b_types))} JOIN {label_b}",
                description=(
                    f"`{label_a}` 조인 유형이 다릅니다 "
                    f"(A={'/'.join(sorted(a_types))}, B={'/'.join(sorted(b_types))})."
                ),
                impact="INNER/LEFT 차이는 누락 행 수를 바꿔 합계 gap 의 주 원인이 될 수 있습니다.",
            ))

        # ON 술어 차이 (파라미터 흡수, A측 역번역)
        dpa = sorted(a_preds - b_preds)
        dpb = sorted(b_preds - a_preds)
        dpa, dpb, _param = _absorb_parameterized(dpa, dpb)
        dpa = _da(dpa, rename)
        if dpa or dpb:
            raw_a = _upper_disp(_raw_on_for(raw_on_a, rep_a, ts))
            raw_b = _upper_disp(_raw_on_for(raw_on_b, rep_b, ts))
            anchors = [_upper_disp(c) for c in _ref_cols(dpa) + _ref_cols(dpb)]
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=_upper_disp(" AND ".join(dpa)) + (f"  (원본 ON: {raw_a})" if raw_a else ""),
                b_snippet=_upper_disp(" AND ".join(dpb)) + (f"  (원본 ON: {raw_b})" if raw_b else ""),
                description=(
                    f"`{label_a}` 조인 ON 조건이 다릅니다. 확인할 컬럼: "
                    f"{', '.join(anchors) or '(상수 조건)'}"
                ),
                impact="조인 키 차이는 매칭되는 row 조합 자체를 바꿉니다.",
            ))

    return findings


def _where_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
) -> list[DiffFinding]:
    _matched, oa, ob, _sh = _diff_sets(a.where_predicates, b.where_predicates)
    oa, ob, _param = _absorb_parameterized(oa, ob)  # 플레이스홀더 값차 흡수
    oa, ob, _qnoise = _absorb_qualifier_noise(oa, ob)  # 한정자만 다른 동일 술어(노이즈) 흡수
    oa, ob, date_range = _absorb_date_range(oa, ob)  # 원시↔일추출 날짜범위(제한적) 흡수

    findings: list[DiffFinding] = []
    if date_range:  # 의미 비교의 PREDICATES 제한적 판정과 정합 — 소프트매치 WARNING
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="DATE_RANGE_SOFT_MATCH",
            severity=Severity.WARNING,
            a_snippet="원시 타임스탬프 범위(>, <)",
            b_snippet="일 추출 + BETWEEN(>=, <=) + 파라미터",
            description="A 원시 타임스탬프 범위 ↔ B 일 추출 BETWEEN 날짜 범위를 동치로 간주했습니다.",
            impact=_DATE_RANGE_CAVEAT.replace("\n", " "),
        ))

    # 같은 형태인데 **구체 리터럴** 값만 다른 쌍 → CRITICAL (필터 범위가 실제로 다름)
    shape_a: dict[str, str] = {}
    for p in oa:
        shape_a.setdefault(_shape(p), p)
    shape_b: dict[str, str] = {}
    for p in ob:
        shape_b.setdefault(_shape(p), p)
    for s in sorted(set(shape_a) & set(shape_b)):
        pa, pb = shape_a[s], shape_b[s]
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_LITERAL_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=_pred_disp1(pa, a, rename),
            b_snippet=_pred_disp1(pb, b),
            description="WHERE 조건의 비교 값(리터럴)이 다릅니다.",
            impact="필터 값 차이는 집계 범위를 직접 바꿉니다 (예: 기간/상태 값).",
        ))
        oa = [p for p in oa if p != pa]
        ob = [p for p in ob if p != pb]

    for p in sorted(oa, key=lambda c: a.pred_order.get(c, 1_000_000)):
        snip = _pred_disp1(p, a, rename)
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_A",
            severity=Severity.WARNING,
            a_snippet=snip,
            b_snippet="",
            description=(
                "A 쿼리에만 있는 WHERE 조건입니다. 확인할 컬럼: "
                f"{', '.join(_ref_cols([snip])) or snip}"
            ),
            impact="A가 더 제한적이면 B보다 결과 집합이 작을 수 있습니다.",
        ))
    for p in sorted(ob, key=lambda c: b.pred_order.get(c, 1_000_000)):
        snip = _pred_disp1(p, b)
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_B",
            severity=Severity.WARNING,
            a_snippet="",
            b_snippet=snip,
            description=(
                "B 쿼리에만 있는 WHERE 조건입니다. 확인할 컬럼: "
                f"{', '.join(_ref_cols([snip])) or snip}"
            ),
            impact="B가 더 제한적이면 A보다 결과 집합이 작을 수 있습니다.",
        ))
    return findings


def _having_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
) -> list[DiffFinding]:
    _matched, oa, ob, _sh = _diff_sets(a.having_predicates, b.having_predicates)
    oa, ob, _param = _absorb_parameterized(oa, ob)
    oa, ob, _qnoise = _absorb_qualifier_noise(oa, ob)  # 한정자 노이즈 흡수(WHERE 와 일관)
    if not oa and not ob:
        return []
    return [DiffFinding(
        clause=ClauseType.HAVING,
        rule_id="HAVING_MISMATCH",
        severity=Severity.WARNING,
        a_snippet=", ".join(_pred_display_list(oa, a, rename)),
        b_snippet=", ".join(_pred_display_list(ob, b)),
        description="HAVING(집계 후 필터) 조건이 다릅니다.",
        impact="집계 후 필터 차이로 포함되는 그룹 수가 달라질 수 있습니다.",
    )]


def _group_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    raw_group_a: _RawSrc | None = None,
    raw_group_b: _RawSrc | None = None,
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets_by_column(a.group_keys, b.group_keys)
    if matched:
        return []
    snip_a = _disp(_da(oa, rename), raw_group_a)   # 원문 GROUP BY 식(대문자·별칭·순서)
    snip_b = _disp(ob, raw_group_b)
    parts = []
    if snip_a:
        parts.append(f"A에만: {snip_a}")
    if snip_b:
        parts.append(f"B에만: {snip_b}")
    return [DiffFinding(
        clause=ClauseType.GROUP_BY,
        rule_id="GROUP_BY_COLUMN_MISMATCH",
        severity=Severity.CRITICAL,
        a_snippet=snip_a,
        b_snippet=snip_b,
        description="묶음 기준(GROUP BY) 키가 다릅니다. " + " / ".join(parts),
        impact="그룹핑 기준이 다르면 집계 입도(row 수)와 값이 달라집니다.",
    )]


def _agg_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
) -> list[DiffFinding]:
    """집계식((함수,인자) 집합) 차이 — 함수 다름 CRITICAL, 인자만 다름 WARNING.

    매칭된 위치 기반(최신 1건) 집계(KEEP↔윈도우 관용구)는 동치 간주하되 WARNING 안내를 남긴다.
    snippet 은 **원문 집계식**(별칭·순서·대문자) — 차이 컬럼으로 raw 조회(세트는 dedup).
    """
    # 순환 회피용 지연 import (comparator→planner)
    from query_diff.semantic_diff.planner import POSITIONAL_AGG_MARK

    # 매칭은 semantic `_compare_aggregates` 와 **동일하게** 테이블 한정자를 무시한다
    # (`_strip_qualifiers` 를 인자에 적용 — CASE·산술 등 복합식 안까지 AST 로 제거): A=`ias_transaction.x`,
    # B=`stlm_ods.x` 처럼 컬럼은 같고 접두사만 다른 noise 를 흡수해 오탐(AGG_ARGUMENT_MISMATCH)을 막는다.
    # 표시는 원문 인자 유지.
    a_keys = {(f, _strip_qualifiers(g)) for f, g in a.aggregates}
    b_keys = {(f, _strip_qualifiers(g)) for f, g in b.aggregates}
    oa = sorted((f, g) for f, g in set(a.aggregates) if (f, _strip_qualifiers(g)) not in b_keys)
    ob = sorted((f, g) for f, g in set(b.aggregates) if (f, _strip_qualifiers(g)) not in a_keys)
    findings: list[DiffFinding] = []
    used_b: set[int] = set()

    def _canon(fn: str, arg: str, de: bool = False) -> str:
        return f"{fn}({_detranslate(arg, rename) if de else arg})"

    def _da_disp(pairs: list[tuple[str, str]]) -> str:
        return _disp([_canon(f, g, de=True) for f, g in pairs], raw_select_a)

    def _db_disp(pairs: list[tuple[str, str]]) -> str:
        return _disp([_canon(f, g) for f, g in pairs], raw_select_b)

    # 1) 같은 인자, 다른 함수 → 함수 불일치(CRITICAL)
    for fa, ga in list(oa):
        for j, (fb, gb) in enumerate(ob):
            if j in used_b:
                continue
            if _strip_qualifiers(ga) == _strip_qualifiers(gb) and fa != fb:
                findings.append(DiffFinding(
                    clause=ClauseType.SELECT,
                    rule_id="AGG_FUNCTION_MISMATCH",
                    severity=Severity.CRITICAL,
                    a_snippet=_da_disp([(fa, ga)]),
                    b_snippet=_db_disp([(fb, gb)]),
                    description=f"집계 함수가 다릅니다 (A={fa}, B={fb}).",
                    impact="SUM vs COUNT 등 집계 의미가 달라 숫자 비교 자체가 부적절합니다.",
                ))
                used_b.add(j)
                oa.remove((fa, ga))
                break

    # 2) 같은 함수, 다른 인자 → 인자 불일치(WARNING)
    for fa, ga in list(oa):
        for j, (fb, gb) in enumerate(ob):
            if j in used_b:
                continue
            if fa == fb:
                findings.append(DiffFinding(
                    clause=ClauseType.SELECT,
                    rule_id="AGG_ARGUMENT_MISMATCH",
                    severity=Severity.WARNING,
                    a_snippet=_da_disp([(fa, ga)]),
                    b_snippet=_db_disp([(fb, gb)]),
                    description=f"집계 함수 {fa}의 인자 컬럼이 다릅니다.",
                    impact="같은 연산이지만 대상 컬럼이 달라 합계 의미가 달라집니다.",
                ))
                used_b.add(j)
                oa.remove((fa, ga))
                break

    # 3) 나머지(개수/구성 차이) → 함수 불일치(CRITICAL)
    rem_b = [ob[j] for j in range(len(ob)) if j not in used_b]
    if oa or rem_b:
        findings.append(DiffFinding(
            clause=ClauseType.SELECT,
            rule_id="AGG_FUNCTION_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=_da_disp(oa),
            b_snippet=_db_disp(rem_b),
            description=f"집계 구성이 다릅니다 (A={len(oa)}개, B={len(rem_b)}개 추가 집계).",
            impact="비교할 집계 지표 자체가 대응되지 않습니다.",
        ))

    # 4) 매칭된 위치 기반(최신 1건) 집계 — 관용구 동치 간주, 확인 권장(WARNING 안내).
    #    한정자 무시 교집합(`(func, _strip_qualifiers(arg))`)으로 접두사 차이에도 NULL정렬 캐비엇이 계속
    #    발화되게 하고, A·B 표시 스니펫은 각 측 원문 인자로 따로 만든다.
    b_pos = {(f, _strip_qualifiers(g)): (f, g) for f, g in b.aggregates if POSITIONAL_AGG_MARK in f}
    shared_pos_a = sorted(
        (f, g) for f, g in a.aggregates
        if POSITIONAL_AGG_MARK in f and (f, _strip_qualifiers(g)) in b_pos
    )
    shared_pos_b = [b_pos[(f, _strip_qualifiers(g))] for f, g in shared_pos_a]
    if shared_pos_a:
        findings.append(DiffFinding(
            clause=ClauseType.SELECT,
            rule_id="POSITIONAL_AGG_SOFT_MATCH",
            severity=Severity.WARNING,
            a_snippet=_da_disp(shared_pos_a),
            b_snippet=_db_disp(shared_pos_b),
            description=(
                f"정렬 기반 최신 1건 집계 {len(shared_pos_a)}건을 관용구"
                "(Oracle KEEP ↔ Hive 윈도우+CASE)로 동치 간주했습니다."
            ),
            impact=(
                "집계·정렬키·파티션·랭크종류는 검증됨(동률 시 결과 동일). 단 정렬 키에 NULL이 "
                "있으면 Oracle(NULLS FIRST)·Hive(NULLS LAST) 기본값 차이로 결과가 다를 수 있어 "
                "확인 권장."
            ),
        ))
    return findings


def _projection_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets_by_column(a.projections, b.projections)
    if matched:
        return []
    return [DiffFinding(
        clause=ClauseType.SELECT,
        rule_id="SELECT_PROJECTION_DIFF",
        severity=Severity.INFO,
        a_snippet=_disp(_da(oa, rename), raw_select_a),
        b_snippet=_disp(ob, raw_select_b),
        description="출력(SELECT) 비집계 컬럼 집합이 다릅니다.",
        impact="출력 컬럼 차이로 리포트 포맷이 달라집니다. 합계 자체에는 영향 없을 수 있습니다.",
    )]


def _year_month_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    op_an: OpAnMap | None = None,
    raw_group_a: _RawSrc | None = None,
    raw_group_b: _RawSrc | None = None,
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
) -> list[DiffFinding]:
    """연-월(날짜 prefix) 추출 관용구로 동치 간주된 GROUP BY/SELECT 항목 — 소프트매칭 안내.

    매칭된 `⟨YM:…⟩` 토큰을 동치로 보되, **실제 A/B 추출식·정확한 입도**로 안내(하드코딩 아님).
    단, 컬럼이 양쪽 시간형으로 **타입 확정**되면(op_an.temporal_reliable) 경고를 생략한다(동일 확정).
    """
    from query_diff.structure_diff.normalizer import YEAR_MONTH_MARK

    def _col(tok: str) -> str:
        return tok[len(YEAR_MONTH_MARK):-1].rpartition(":")[0]

    shared_ym = sorted(
        s for s in (
            (set(a.group_keys) & set(b.group_keys))
            | (set(a.projections) & set(b.projections))
        )
        if YEAR_MONTH_MARK in s
    )
    # 타입 확정 컬럼은 동일로 보고 경고 생략 — 미상/비시간형만 남긴다.
    shared_ym = [s for s in shared_ym if not (op_an and op_an.temporal_reliable(_col(s)))]
    if not shared_ym:
        return []
    # 실제 GROUP BY/SELECT 추출식·입도로 동적 생성(의미 비교 캐비엣과 동일 — 두 화면 일치).
    caveat, a_snip, b_snip = _year_month_detail(
        shared_ym, [raw_group_a, raw_select_a], [raw_group_b, raw_select_b], rename
    )
    gran_label = caveat.split(" 추출")[0] if caveat else "날짜"
    return [DiffFinding(
        clause=ClauseType.SELECT,
        rule_id="YEAR_MONTH_SOFT_MATCH",
        severity=Severity.WARNING,
        a_snippet=a_snip,
        b_snippet=b_snip,
        description=f"날짜 추출 관용구 {len(shared_ym)}건을 동치로 간주했습니다 ({gran_label}).",
        impact=caveat.replace("\n", " "),
    )]


def _findings_from_plans(
    plan_a: LogicalPlan,
    plan_b: LogicalPlan,
    rename: dict[str, str],
    raw_on_a: dict[str, str],
    raw_on_b: dict[str, str],
    op_an: OpAnMap | None = None,
    raw_group_a: _RawSrc | None = None,
    raw_group_b: _RawSrc | None = None,
    raw_select_a: _RawSrc | None = None,
    raw_select_b: _RawSrc | None = None,
    disp_a: dict[tuple[str, str], str] | None = None,
    disp_b: dict[tuple[str, str], str] | None = None,
) -> list[DiffFinding]:
    """두 LogicalPlan 의 차이를 절별 DiffFinding 목록으로 렌더(절 우선순위 순).

    snippet 은 의미 비교와 **동일하게 원문 리터럴**(대문자·별칭·순서) — 원본 소스 raw 맵 전달."""
    findings: list[DiffFinding] = []
    findings += _from_findings(plan_a, plan_b, rename)
    findings += _join_findings(plan_a, plan_b, rename, raw_on_a, raw_on_b, disp_a, disp_b)
    findings += _where_findings(plan_a, plan_b, rename)
    findings += _having_findings(plan_a, plan_b, rename)
    findings += _group_findings(plan_a, plan_b, rename, raw_group_a, raw_group_b)
    findings += _agg_findings(plan_a, plan_b, rename, raw_select_a, raw_select_b)
    findings += _projection_findings(plan_a, plan_b, rename, raw_select_a, raw_select_b)
    findings += _year_month_findings(
        plan_a, plan_b, rename, op_an,
        raw_group_a, raw_group_b, raw_select_a, raw_select_b,
    )
    return findings


def compare_structures(
    query_a: QueryInput,
    query_b: QueryInput,
    mapping: SchemaMapping | None = None,
    op_an: OpAnMap | None = None,
) -> StructureDiff:
    """A·B 쿼리의 구조 차이를 계산하여 StructureDiff 반환.

    사전 조건: query_a.is_valid, query_b.is_valid가 True이어야 한다.
    (validation_service.validate_query_input 선행 필요)

    의미 비교와 동일한 정규화 프런트엔드(옵티마이저 → 파생 테이블(CTE+서브쿼리) 관통
    해소 → 단일 테이블 스코프 미한정 컬럼 한정 → 번역 → LogicalPlan)를 거친 뒤 절별
    finding 으로 렌더한다. op_an 가 주어지면 A(운영) 쿼리를 분석 네임스페이스로 번역하고,
    표시는 원본 운영명으로 역변환한다.

    `mapping` 인자는 하위호환을 위해 유지하되 사용하지 않는다(번역으로 대체).
    """
    # planner 는 structure_diff.normalizer 에 의존하므로(역방향) 모듈 로드 순환을 피해 지연 import.
    from query_diff.semantic_diff.planner import (
        build_logical_plan,
        join_display_labels,
        recover_column_qualifiers,
        resolve_derived_passthrough,
    )

    if mapping is None:
        mapping = IdentitySchemaMapping()

    if not query_a.sql_raw or not query_b.sql_raw:
        raise ValueError("두 쿼리 모두 sql_raw가 채워져 있어야 합니다.")

    dialect_a = _DIALECT_MAP[query_a.dialect]
    dialect_b = _DIALECT_MAP[query_b.dialect]

    try:
        tree_a, _lim_a = normalize_query(query_a.sql_raw, dialect_a)
    except ValueError as e:
        raise ValueError(f"A쿼리 파싱 실패: {e}") from e
    try:
        tree_b, _lim_b = normalize_query(query_b.sql_raw, dialect_b)
    except ValueError as e:
        raise ValueError(f"B쿼리 파싱 실패: {e}") from e

    # 디코릴레이션(A 상관 스칼라 서브쿼리 ↔ B LEFT JOIN 최신1건) — 의미 비교와 동일하게
    # 정규화 직후 탐지·절제(두 화면 결론 일치). 인식 시 소프트매칭 WARNING 부가.
    from query_diff.semantic_diff.decorrelation import (
        decorrelation_caveat,
        detect_decorrelation,
        excise_decorrelation,
    )

    decorr = detect_decorrelation(tree_a, tree_b)
    if decorr is not None:
        excise_decorrelation(tree_a, tree_b, decorr)

    raw_on_a = _raw_on_map(tree_a)
    disp_a = join_display_labels(tree_a)  # 조인 표시 라벨(CTE 경계 존중) — 패스스루/번역 전 원본에서

    # 순서: 파생 테이블(CTE+서브쿼리) 통과 해소 → 단일 테이블 스코프 미한정 컬럼 한정 → 번역
    # (analyzer.compare_semantic 과 동일).
    tree_a = recover_column_qualifiers(resolve_derived_passthrough(tree_a))
    rename_a: dict[str, str] = {}
    if op_an is not None:
        tree_a, rename_a = translate_op_to_an(tree_a, op_an)

    raw_on_b = _raw_on_map(tree_b)
    disp_b = join_display_labels(tree_b)
    tree_b = recover_column_qualifiers(resolve_derived_passthrough(tree_b))

    plan_a = build_logical_plan(tree_a, _lim_a)
    plan_b = build_logical_plan(tree_b, _lim_b)

    # 차이 snippet 을 원문 리터럴로 — 의미 비교와 동일하게 원본 소스에서 raw 맵 캡처.
    findings = _findings_from_plans(
        plan_a, plan_b, rename_a, raw_on_a, raw_on_b, op_an,
        raw_group_a=_raw_group_map(query_a.sql_raw, dialect_a),
        raw_group_b=_raw_group_map(query_b.sql_raw, dialect_b),
        raw_select_a=_raw_select_map(query_a.sql_raw, dialect_a),
        raw_select_b=_raw_select_map(query_b.sql_raw, dialect_b),
        disp_a=disp_a,
        disp_b=disp_b,
    )
    if decorr is not None:
        findings.append(DiffFinding(
            clause=ClauseType.JOIN,
            rule_id="DECORRELATION_SOFT_MATCH",
            severity=Severity.WARNING,
            a_snippet=f"(SELECT … FROM {decorr.table} WHERE …) 상관 스칼라 서브쿼리",
            b_snippet="LEFT JOIN ROW_NUMBER()=1 (최신1건)",
            description="A 상관 스칼라 서브쿼리 ↔ B LEFT JOIN(최신1건) 디코릴레이션을 동치로 간주했습니다.",
            impact=decorrelation_caveat(decorr).replace("\n", " "),
        ))
    diff = StructureDiff(findings=findings)
    return recompute_state(diff)
