"""의미 기반 쿼리 비교 엔진

sqlglot 옵티마이저로 CTE 인라인·서브쿼리 머지·컬럼 qualify를 수행한 뒤,
논리 계획(LogicalPlan)을 추출해 차원별로 비교한다.

구문(syntax)이 달라도 같은 데이터를 반환하면 EQUIVALENT로 판정한다.
- 예: A(FROM에서 JOIN) vs B(WITH으로 먼저 JOIN) → EQUIVALENT
"""

from query_diff.semantic_diff.analyzer import compare_semantic

__all__ = ["compare_semantic"]
