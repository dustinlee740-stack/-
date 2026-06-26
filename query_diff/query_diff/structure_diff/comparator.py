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
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.semantic_diff.plan_compare import (
    _absorb_parameterized,
    _bare,
    _bare_cols,
    _da,
    _detranslate,
    _diff_sets,
    _diff_sets_by_column,
    _group_edges,
    _lookup_raw_on,
    _raw_on_map,
    _ref_cols,
    _shape,
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

def _from_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets(a.base_tables, b.base_tables)
    if matched:
        return []
    oa = _da(oa, rename)
    parts = []
    if oa:
        parts.append(f"A에만: {', '.join(oa)}")
    if ob:
        parts.append(f"B에만: {', '.join(ob)}")
    return [DiffFinding(
        clause=ClauseType.FROM,
        rule_id="TABLE_IDENTITY_MISMATCH",
        severity=Severity.CRITICAL,
        a_snippet=", ".join(oa),
        b_snippet=", ".join(ob),
        description="읽는 기본 테이블이 다릅니다. " + " / ".join(parts),
        impact="원천 테이블이 달라 집계 대상 자체가 다릅니다. 스키마 매핑 보강이 필요할 수 있습니다.",
    )]


def _join_findings(
    a: LogicalPlan,
    b: LogicalPlan,
    rename: dict[str, str],
    raw_on_a: dict[str, str],
    raw_on_b: dict[str, str],
) -> list[DiffFinding]:
    """조인을 ON 참조 테이블 집합으로 페어링(앵커 무관)하고 타입·ON 술어 차이를 렌더."""
    ga, gb = _group_edges(a.join_edges), _group_edges(b.join_edges)

    # 테이블 집합 단위로 묶어 타입/술어를 비교 (타입 차이를 JOIN_TYPE_MISMATCH 로 분리)
    tablesets = {k[0] for k in ga} | {k[0] for k in gb}
    findings: list[DiffFinding] = []

    for ts in sorted(tablesets, key=lambda s: sorted(s)):
        label = "↔".join(sorted(ts))
        a_types = {k[1] for k in ga if k[0] == ts}
        b_types = {k[1] for k in gb if k[0] == ts}
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
            raw = _lookup_raw_on(raw_on_b, ts)
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet="",
                b_snippet=label + (f" (ON: {raw})" if raw else ""),
                description=f"`{label}` 조인이 B 쿼리에만 있습니다.",
                impact="조인 대상이 한쪽에만 있으면 결과 row 수가 달라집니다.",
            ))
            continue
        if not b_types:
            raw = _lookup_raw_on(raw_on_a, ts)
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=label + (f" (ON: {raw})" if raw else ""),
                b_snippet="",
                description=f"`{label}` 조인이 A 쿼리에만 있습니다.",
                impact="조인 대상이 한쪽에만 있으면 결과 row 수가 달라집니다.",
            ))
            continue

        # 타입 차이
        if a_types != b_types:
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_TYPE_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=f"{'/'.join(sorted(a_types))} JOIN {label}",
                b_snippet=f"{'/'.join(sorted(b_types))} JOIN {label}",
                description=(
                    f"`{label}` 조인 유형이 다릅니다 "
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
            raw_a = _lookup_raw_on(raw_on_a, ts)
            raw_b = _lookup_raw_on(raw_on_b, ts)
            anchors = _ref_cols(dpa) + _ref_cols(dpb)
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=" AND ".join(dpa) + (f"  (원본 ON: {raw_a})" if raw_a else ""),
                b_snippet=" AND ".join(dpb) + (f"  (원본 ON: {raw_b})" if raw_b else ""),
                description=(
                    f"`{label}` 조인 ON 조건이 다릅니다. 확인할 컬럼: "
                    f"{', '.join(anchors) or '(상수 조건)'}"
                ),
                impact="조인 키 차이는 매칭되는 row 조합 자체를 바꿉니다.",
            ))

    return findings


def _where_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    _matched, oa, ob, _sh = _diff_sets(a.where_predicates, b.where_predicates)
    oa, ob, _param = _absorb_parameterized(oa, ob)  # 플레이스홀더 값차 흡수

    findings: list[DiffFinding] = []

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
            a_snippet=_detranslate(pa, rename),
            b_snippet=pb,
            description="WHERE 조건의 비교 값(리터럴)이 다릅니다.",
            impact="필터 값 차이는 집계 범위를 직접 바꿉니다 (예: 기간/상태 값).",
        ))
        oa = [p for p in oa if p != pa]
        ob = [p for p in ob if p != pb]

    for p in oa:
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_A",
            severity=Severity.WARNING,
            a_snippet=_detranslate(p, rename),
            b_snippet="",
            description=(
                "A 쿼리에만 있는 WHERE 조건입니다. 확인할 컬럼: "
                f"{', '.join(_ref_cols([p])) or _detranslate(p, rename)}"
            ),
            impact="A가 더 제한적이면 B보다 결과 집합이 작을 수 있습니다.",
        ))
    for p in ob:
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_B",
            severity=Severity.WARNING,
            a_snippet="",
            b_snippet=p,
            description=(
                "B 쿼리에만 있는 WHERE 조건입니다. 확인할 컬럼: "
                f"{', '.join(_ref_cols([p])) or p}"
            ),
            impact="B가 더 제한적이면 A보다 결과 집합이 작을 수 있습니다.",
        ))
    return findings


def _having_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    _matched, oa, ob, _sh = _diff_sets(a.having_predicates, b.having_predicates)
    oa, ob, _param = _absorb_parameterized(oa, ob)
    oa = _da(oa, rename)
    if not oa and not ob:
        return []
    return [DiffFinding(
        clause=ClauseType.HAVING,
        rule_id="HAVING_MISMATCH",
        severity=Severity.WARNING,
        a_snippet=" AND ".join(oa),
        b_snippet=" AND ".join(ob),
        description="HAVING(집계 후 필터) 조건이 다릅니다.",
        impact="집계 후 필터 차이로 포함되는 그룹 수가 달라질 수 있습니다.",
    )]


def _group_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets_by_column(a.group_keys, b.group_keys)
    if matched:
        return []
    oa = _da(oa, rename)
    parts = []
    if oa:
        parts.append(f"A에만: {', '.join(_bare_cols(oa))}")
    if ob:
        parts.append(f"B에만: {', '.join(_bare_cols(ob))}")
    return [DiffFinding(
        clause=ClauseType.GROUP_BY,
        rule_id="GROUP_BY_COLUMN_MISMATCH",
        severity=Severity.CRITICAL,
        a_snippet=", ".join(_bare_cols(oa)),
        b_snippet=", ".join(_bare_cols(ob)),
        description="묶음 기준(GROUP BY) 키가 다릅니다. " + " / ".join(parts),
        impact="그룹핑 기준이 다르면 집계 입도(row 수)와 값이 달라집니다.",
    )]


def _agg_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    """집계식((함수,인자) 집합) 차이 — 함수 다름 CRITICAL, 인자만 다름 WARNING."""
    oa = sorted(set(a.aggregates) - set(b.aggregates))
    ob = sorted(set(b.aggregates) - set(a.aggregates))
    findings: list[DiffFinding] = []
    used_b: set[int] = set()

    def _fmt(fn: str, arg: str, de: bool = False) -> str:
        return f"{fn}({_detranslate(arg, rename) if de else arg})"

    # 1) 같은 인자, 다른 함수 → 함수 불일치(CRITICAL)
    for fa, ga in list(oa):
        for j, (fb, gb) in enumerate(ob):
            if j in used_b:
                continue
            if _bare(ga) == _bare(gb) and fa != fb:
                findings.append(DiffFinding(
                    clause=ClauseType.SELECT,
                    rule_id="AGG_FUNCTION_MISMATCH",
                    severity=Severity.CRITICAL,
                    a_snippet=_fmt(fa, ga, de=True),
                    b_snippet=_fmt(fb, gb),
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
                    a_snippet=_fmt(fa, ga, de=True),
                    b_snippet=_fmt(fb, gb),
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
            a_snippet=", ".join(_fmt(f, g, de=True) for f, g in oa),
            b_snippet=", ".join(_fmt(f, g) for f, g in rem_b),
            description=f"집계 구성이 다릅니다 (A={len(oa)}개, B={len(rem_b)}개 추가 집계).",
            impact="비교할 집계 지표 자체가 대응되지 않습니다.",
        ))
    return findings


def _projection_findings(
    a: LogicalPlan, b: LogicalPlan, rename: dict[str, str]
) -> list[DiffFinding]:
    matched, oa, ob, _sh = _diff_sets_by_column(a.projections, b.projections)
    if matched:
        return []
    oa = _da(oa, rename)
    return [DiffFinding(
        clause=ClauseType.SELECT,
        rule_id="SELECT_PROJECTION_DIFF",
        severity=Severity.INFO,
        a_snippet=", ".join(_bare_cols(oa)),
        b_snippet=", ".join(_bare_cols(ob)),
        description="출력(SELECT) 비집계 컬럼 집합이 다릅니다.",
        impact="출력 컬럼 차이로 리포트 포맷이 달라집니다. 합계 자체에는 영향 없을 수 있습니다.",
    )]


def _findings_from_plans(
    plan_a: LogicalPlan,
    plan_b: LogicalPlan,
    rename: dict[str, str],
    raw_on_a: dict[str, str],
    raw_on_b: dict[str, str],
) -> list[DiffFinding]:
    """두 LogicalPlan 의 차이를 절별 DiffFinding 목록으로 렌더(절 우선순위 순)."""
    findings: list[DiffFinding] = []
    findings += _from_findings(plan_a, plan_b, rename)
    findings += _join_findings(plan_a, plan_b, rename, raw_on_a, raw_on_b)
    findings += _where_findings(plan_a, plan_b, rename)
    findings += _having_findings(plan_a, plan_b, rename)
    findings += _group_findings(plan_a, plan_b, rename)
    findings += _agg_findings(plan_a, plan_b, rename)
    findings += _projection_findings(plan_a, plan_b, rename)
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

    의미 비교와 동일한 정규화 프런트엔드(옵티마이저 → 번역 → CTE 관통 해소 →
    LogicalPlan)를 거친 뒤 절별 finding 으로 렌더한다. op_an 가 주어지면 A(운영)
    쿼리를 분석 네임스페이스로 번역하고, 표시는 원본 운영명으로 역변환한다.

    `mapping` 인자는 하위호환을 위해 유지하되 사용하지 않는다(번역으로 대체).
    """
    # planner 는 structure_diff.normalizer 에 의존하므로(역방향) 모듈 로드 순환을 피해 지연 import.
    from query_diff.semantic_diff.planner import (
        build_logical_plan,
        resolve_cte_passthrough,
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

    raw_on_a = _raw_on_map(tree_a)
    rename_a: dict[str, str] = {}
    if op_an is not None:
        tree_a, rename_a = translate_op_to_an(tree_a, op_an)

    try:
        tree_b, _lim_b = normalize_query(query_b.sql_raw, dialect_b)
    except ValueError as e:
        raise ValueError(f"B쿼리 파싱 실패: {e}") from e
    raw_on_b = _raw_on_map(tree_b)

    tree_a = resolve_cte_passthrough(tree_a)
    tree_b = resolve_cte_passthrough(tree_b)

    plan_a = build_logical_plan(tree_a, _lim_a)
    plan_b = build_logical_plan(tree_b, _lim_b)

    findings = _findings_from_plans(plan_a, plan_b, rename_a, raw_on_a, raw_on_b)
    diff = StructureDiff(findings=findings)
    return recompute_state(diff)
