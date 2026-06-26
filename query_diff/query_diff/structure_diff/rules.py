"""구조 비교 — 절 우선순위 / dominant clause 선정

차이 검출 로직 자체는 `comparator._findings_from_plans`(의미 비교와 공유하는
LogicalPlan 기반)로 이동했다. 이 모듈은 fast-path 신호에 쓰이는 절 우선순위만 보유한다.
"""

from __future__ import annotations

from query_diff.models import ClauseType, DiffFinding, Severity

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
