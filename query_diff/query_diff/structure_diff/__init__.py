"""AST 기반 쿼리 구조 비교 엔진 (flow.md No.2)

A쿼리(Oracle)·B쿼리(Hive)를 sqlglot으로 파싱한 뒤 절별(SELECT/FROM/JOIN/WHERE/GROUP BY/HAVING)
구조 차이를 규칙 매칭으로 탐지한다. Critical 1건 이상이면 fast-path로 종결하여
Row diff 단계를 건너뛴다.
"""

from query_diff.structure_diff.comparator import compare_structures
from query_diff.structure_diff.schema_mapping import (
    IdentitySchemaMapping,
    SchemaMapping,
)

__all__ = ["compare_structures", "SchemaMapping", "IdentitySchemaMapping"]
