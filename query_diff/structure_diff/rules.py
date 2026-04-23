"""규칙 엔진 — CanonicalQuery 쌍을 입력받아 DiffFinding 목록 반환

MVP 12개 규칙을 절별로 구현. 각 규칙 함수는 순수 함수로,
(canonical_a, canonical_b, schema_mapping) → list[DiffFinding] 시그니처를 따른다.
"""

from __future__ import annotations

import re

from query_diff.models import ClauseType, DiffFinding, Severity
from query_diff.structure_diff.normalizer import (
    CanonicalJoin,
    CanonicalProjection,
    CanonicalQuery,
)
from query_diff.structure_diff.schema_mapping import SchemaMapping

# predicate 리터럴 추출용 (문자열/숫자)
_LITERAL_RE = re.compile(r"'[^']*'|\b\d+(?:\.\d+)?\b")


# --- FROM ---

def check_from(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    findings: list[DiffFinding] = []

    names_a = [t.name for t in a.from_tables]
    names_b = [t.name for t in b.from_tables]

    if len(names_a) != len(names_b):
        findings.append(DiffFinding(
            clause=ClauseType.FROM,
            rule_id="TABLE_COUNT_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=", ".join(names_a),
            b_snippet=", ".join(names_b),
            description=f"FROM 절 테이블 수가 다릅니다 (A={len(names_a)}, B={len(names_b)}).",
            impact="집계 대상 테이블 집합이 달라 합계 차이의 직접 원인일 가능성이 높습니다.",
        ))
        return findings

    # 개수가 같을 때만 동일성 검사
    unmatched_a, unmatched_b = [], list(names_b)
    for name in names_a:
        matched = None
        for cand in unmatched_b:
            if mapping.same_table(name, cand):
                matched = cand
                break
        if matched is not None:
            unmatched_b.remove(matched)
        else:
            unmatched_a.append(name)

    if unmatched_a or unmatched_b:
        findings.append(DiffFinding(
            clause=ClauseType.FROM,
            rule_id="TABLE_IDENTITY_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=", ".join(unmatched_a),
            b_snippet=", ".join(unmatched_b),
            description="FROM 절 테이블이 스키마 매핑상 대응되지 않습니다.",
            impact="원천이 다르므로 Row 단위 비교가 불가능합니다. 스키마 매핑 보정이 필요합니다.",
        ))

    return findings


# --- JOIN ---

def _jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def _match_joins(
    joins_a: list[CanonicalJoin],
    joins_b: list[CanonicalJoin],
    mapping: SchemaMapping,
) -> list[tuple[CanonicalJoin | None, CanonicalJoin | None]]:
    """테이블명 + ON 유사도(Jaccard) 기반 탐욕 매칭.

    같은 테이블에 여러 번 조인(예: contract con, contract aq)해도 올바른 짝을 찾는다.
    각 A-join에 대해 (same_table=True)인 B-join 중 ON 유사도가 가장 높은 것을 선택.
    동률이면 alias 일치를 우선. 매칭 실패 시 None 페어.
    """
    pairs: list[tuple[CanonicalJoin | None, CanonicalJoin | None]] = []
    remaining_b = list(joins_b)

    for ja in joins_a:
        candidates = [jb for jb in remaining_b if mapping.same_table(ja.right_table, jb.right_table)]
        if not candidates:
            pairs.append((ja, None))
            continue

        def _score(jb: CanonicalJoin) -> tuple[float, int]:
            sim = _jaccard(ja.on_predicates, jb.on_predicates)
            alias_match = 1 if ja.right_alias and ja.right_alias == jb.right_alias else 0
            return (sim, alias_match)

        best = max(candidates, key=_score)
        remaining_b.remove(best)
        pairs.append((ja, best))

    for jb in remaining_b:
        pairs.append((None, jb))
    return pairs


def _join_label(j: CanonicalJoin) -> str:
    """사용자 표시용 레이블: contract(con) 형태. alias 없으면 테이블명만."""
    return f"{j.right_table}({j.right_alias})" if j.right_alias else j.right_table


def check_join(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    findings: list[DiffFinding] = []
    pairs = _match_joins(a.joins, b.joins, mapping)

    for ja, jb in pairs:
        if ja is None or jb is None:
            present = ja or jb
            label = _join_label(present)
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=f"{ja.join_type} JOIN {_join_label(ja)}" if ja else "",
                b_snippet=f"{jb.join_type} JOIN {_join_label(jb)}" if jb else "",
                description=f"JOIN 대상 '{label}'이 한쪽에만 존재합니다.",
                impact="조인 대상 변경은 결과 row 수에 직접 영향을 미칩니다.",
            ))
            continue

        label_a = _join_label(ja)
        label_b = _join_label(jb)
        # alias까지 포함한 위치 레이블 (A·B가 같은 테이블이므로 통합 레이블 가능)
        pair_label = label_a if label_a == label_b else f"{label_a} vs {label_b}"

        if ja.join_type != jb.join_type:
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_TYPE_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=f"{ja.join_type} JOIN {label_a}",
                b_snippet=f"{jb.join_type} JOIN {label_b}",
                description=f"JOIN 유형이 다릅니다 ({pair_label}: A={ja.join_type}, B={jb.join_type}).",
                impact="INNER/LEFT 차이는 누락 행 수를 직접 바꿔 합계 gap의 주 원인이 될 수 있습니다.",
            ))

        if set(ja.on_predicates) != set(jb.on_predicates):
            only_a = sorted(set(ja.on_predicates) - set(jb.on_predicates))
            only_b = sorted(set(jb.on_predicates) - set(ja.on_predicates))
            findings.append(DiffFinding(
                clause=ClauseType.JOIN,
                rule_id="JOIN_CONDITION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=" AND ".join(only_a),
                b_snippet=" AND ".join(only_b),
                description=f"JOIN '{pair_label}' ON 조건이 다릅니다.",
                impact="조인 키 차이는 매칭되는 row 조합 자체를 바꿉니다.",
            ))

    return findings


# --- WHERE ---

def _strip_literals(pred: str) -> str:
    return _LITERAL_RE.sub("?", pred)


def check_where(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    findings: list[DiffFinding] = []
    set_a = set(a.where_predicates)
    set_b = set(b.where_predicates)

    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)

    # 리터럴만 다른 쌍 탐지 (SHAPE 같으면 LITERAL_MISMATCH)
    shape_a = {_strip_literals(p): p for p in only_a}
    shape_b = {_strip_literals(p): p for p in only_b}
    common_shapes = set(shape_a) & set(shape_b)

    for shape in sorted(common_shapes):
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_LITERAL_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=shape_a[shape],
            b_snippet=shape_b[shape],
            description="WHERE 조건의 비교 리터럴이 다릅니다.",
            impact="필터 값 차이는 집계 범위를 직접 바꿉니다 (예: 기간/상태 값).",
        ))
        only_a_list = [p for p in only_a if p != shape_a[shape]]
        only_b_list = [p for p in only_b if p != shape_b[shape]]
        only_a = only_a_list
        only_b = only_b_list

    for pred in only_a:
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_A",
            severity=Severity.WARNING,
            a_snippet=pred,
            b_snippet="",
            description="A쿼리에만 존재하는 WHERE 조건입니다.",
            impact="A가 더 제한적인 필터를 가지므로 B보다 결과 집합이 작을 수 있습니다.",
        ))
    for pred in only_b:
        findings.append(DiffFinding(
            clause=ClauseType.WHERE,
            rule_id="WHERE_PREDICATE_ONLY_IN_B",
            severity=Severity.WARNING,
            a_snippet="",
            b_snippet=pred,
            description="B쿼리에만 존재하는 WHERE 조건입니다.",
            impact="B가 더 제한적인 필터를 가지므로 A보다 결과 집합이 작을 수 있습니다.",
        ))

    return findings


# --- GROUP BY ---

def check_group_by(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    if set(a.group_by) == set(b.group_by):
        return []
    return [DiffFinding(
        clause=ClauseType.GROUP_BY,
        rule_id="GROUP_BY_COLUMN_MISMATCH",
        severity=Severity.CRITICAL,
        a_snippet=", ".join(a.group_by),
        b_snippet=", ".join(b.group_by),
        description="GROUP BY 키 집합이 다릅니다.",
        impact="그룹핑 기준이 다르면 집계 결과의 입도(row 수)와 값이 달라집니다.",
    )]


# --- HAVING ---

def check_having(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    if set(a.having_predicates) == set(b.having_predicates):
        return []
    only_a = sorted(set(a.having_predicates) - set(b.having_predicates))
    only_b = sorted(set(b.having_predicates) - set(a.having_predicates))
    return [DiffFinding(
        clause=ClauseType.HAVING,
        rule_id="HAVING_MISMATCH",
        severity=Severity.WARNING,
        a_snippet=" AND ".join(only_a),
        b_snippet=" AND ".join(only_b),
        description="HAVING 조건이 다릅니다.",
        impact="집계 후 필터 차이로 포함되는 그룹 수가 달라질 수 있습니다.",
    )]


# --- SELECT (집계 및 프로젝션) ---

def check_select(
    a: CanonicalQuery, b: CanonicalQuery, mapping: SchemaMapping
) -> list[DiffFinding]:
    findings: list[DiffFinding] = []

    # 1) 집계 함수 비교 — 인덱스 기준으로 대응
    aggs_a = [p for p in a.projections if p.is_aggregate]
    aggs_b = [p for p in b.projections if p.is_aggregate]

    for idx in range(min(len(aggs_a), len(aggs_b))):
        pa, pb = aggs_a[idx], aggs_b[idx]
        if pa.agg_function != pb.agg_function:
            findings.append(DiffFinding(
                clause=ClauseType.SELECT,
                rule_id="AGG_FUNCTION_MISMATCH",
                severity=Severity.CRITICAL,
                a_snippet=pa.expression,
                b_snippet=pb.expression,
                description=f"집계 함수가 다릅니다 (A={pa.agg_function}, B={pb.agg_function}).",
                impact="SUM vs COUNT 등 집계 의미가 달라 숫자 비교 자체가 부적절합니다.",
            ))
        elif not mapping.same_column(pa.agg_arg, pb.agg_arg):
            findings.append(DiffFinding(
                clause=ClauseType.SELECT,
                rule_id="AGG_ARGUMENT_MISMATCH",
                severity=Severity.WARNING,
                a_snippet=pa.expression,
                b_snippet=pb.expression,
                description=f"집계 함수 {pa.agg_function}의 인자 컬럼이 다릅니다.",
                impact="같은 연산이지만 대상 컬럼이 달라 합계 의미가 달라집니다.",
            ))

    if len(aggs_a) != len(aggs_b):
        findings.append(DiffFinding(
            clause=ClauseType.SELECT,
            rule_id="AGG_FUNCTION_MISMATCH",
            severity=Severity.CRITICAL,
            a_snippet=f"{len(aggs_a)}개 집계",
            b_snippet=f"{len(aggs_b)}개 집계",
            description=f"집계 함수 개수가 다릅니다 (A={len(aggs_a)}, B={len(aggs_b)}).",
            impact="비교할 집계 지표 자체가 대응되지 않습니다.",
        ))

    # 2) 비집계 프로젝션 집합 비교
    non_agg_a = {p.expression for p in a.projections if not p.is_aggregate}
    non_agg_b = {p.expression for p in b.projections if not p.is_aggregate}
    if non_agg_a != non_agg_b:
        findings.append(DiffFinding(
            clause=ClauseType.SELECT,
            rule_id="SELECT_PROJECTION_DIFF",
            severity=Severity.INFO,
            a_snippet=", ".join(sorted(non_agg_a)),
            b_snippet=", ".join(sorted(non_agg_b)),
            description="SELECT 프로젝션(비집계) 집합이 다릅니다.",
            impact="출력 컬럼 차이로 리포트 포맷이 달라집니다. 합계 자체에는 영향 없을 수 있습니다.",
        ))

    return findings


# --- 전체 규칙 실행 순서 ---

ALL_RULES = [
    check_from,
    check_join,
    check_where,
    check_group_by,
    check_having,
    check_select,
]


_CLAUSE_PRIORITY: dict[ClauseType, int] = {
    ClauseType.FROM: 0,
    ClauseType.JOIN: 1,
    ClauseType.WHERE: 2,
    ClauseType.GROUP_BY: 3,
    ClauseType.HAVING: 4,
    ClauseType.SELECT: 5,
}


def dominant_clause(findings: list[DiffFinding]) -> ClauseType | None:
    """Critical finding 중 절 우선순위가 가장 높은 것"""
    criticals = [f for f in findings if f.severity == Severity.CRITICAL]
    if not criticals:
        return None
    return min(criticals, key=lambda f: _CLAUSE_PRIORITY[f.clause]).clause
