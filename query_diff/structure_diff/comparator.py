"""구조 비교 오케스트레이터

두 QueryInput을 받아 파싱 → 정규화 → 규칙 순회 → StructureDiff 반환.
Critical 1건 이상이면 fast_path_terminate=True로 설정하여
상위 flow에서 Row diff를 건너뛰도록 신호를 준다.
"""

from __future__ import annotations

from query_diff.models import (
    ClauseType,
    DiffFinding,
    QueryInput,
    Severity,
    StructureDiff,
)
from query_diff.structure_diff.normalizer import extract_canonical
from query_diff.structure_diff.rules import ALL_RULES, dominant_clause
from query_diff.structure_diff.schema_mapping import (
    IdentitySchemaMapping,
    SchemaMapping,
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


def compare_structures(
    query_a: QueryInput,
    query_b: QueryInput,
    mapping: SchemaMapping | None = None,
) -> StructureDiff:
    """A·B 쿼리의 구조 차이를 계산하여 StructureDiff 반환.

    사전 조건: query_a.is_valid, query_b.is_valid가 True이어야 한다.
    (validation_service.validate_query_input 선행 필요)
    """
    if mapping is None:
        mapping = IdentitySchemaMapping()

    if not query_a.sql_raw or not query_b.sql_raw:
        raise ValueError("두 쿼리 모두 sql_raw가 채워져 있어야 합니다.")

    dialect_a = _DIALECT_MAP[query_a.dialect]
    dialect_b = _DIALECT_MAP[query_b.dialect]

    try:
        canonical_a = extract_canonical(query_a.sql_raw, dialect_a)
    except Exception as e:
        raise ValueError(f"A쿼리 파싱 실패: {e}") from e
    try:
        canonical_b = extract_canonical(query_b.sql_raw, dialect_b)
    except Exception as e:
        raise ValueError(f"B쿼리 파싱 실패: {e}") from e

    findings: list[DiffFinding] = []
    for rule in ALL_RULES:
        findings.extend(rule(canonical_a, canonical_b, mapping))

    diff = StructureDiff(findings=findings)
    return recompute_state(diff)
