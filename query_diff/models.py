"""쿼리 비교 모듈 도메인 모델"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class SourceType(str, Enum):
    FILE = "FILE"
    TEXT = "TEXT"
    WIKI = "WIKI"


class Dialect(str, Enum):
    ORACLE = "oracle"
    HIVE = "hive"
    MYSQL = "mysql"
    POSTGRES = "postgres"


class ComparisonStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    READY = "READY"
    COMPARING = "COMPARING"
    DONE = "DONE"
    ERROR = "ERROR"


class QueryStructure(BaseModel):
    """sqlglot 파싱 후 절별 구조 요약"""
    select_columns: int = 0
    from_tables: int = 0
    joins: int = 0
    where_conditions: int = 0
    group_by_columns: int = 0
    having_conditions: int = 0
    order_by_columns: int = 0
    subqueries: int = 0


class QueryInput(BaseModel):
    source_type: SourceType = SourceType.TEXT
    sql_raw: str = ""
    sql_normalized: Optional[str] = None
    dialect: Dialect = Dialect.ORACLE
    file_name: Optional[str] = None
    wiki_url: Optional[str] = None
    is_valid: Optional[bool] = None
    validation_error: Optional[str] = None
    structure: Optional[QueryStructure] = None


class DiffMetric(BaseModel):
    metric_name: str = Field(..., examples=["매출합계", "건수"])
    value_a: Decimal
    value_b: Decimal

    @computed_field
    @property
    def diff_value(self) -> Decimal:
        return self.value_a - self.value_b

    @computed_field
    @property
    def diff_pct(self) -> Decimal:
        if self.value_a == 0:
            return Decimal("0")
        return (self.diff_value / self.value_a * 100).quantize(Decimal("0.01"))


class DiffSummary(BaseModel):
    metrics: list[DiffMetric] = Field(default_factory=list)


class MatchingKey(BaseModel):
    column_a: str
    column_b: str


# --- 구조 비교 결과 (No.2 AST 기반 쿼리 구조 비교 엔진) ---

class ClauseType(str, Enum):
    SELECT = "SELECT"
    FROM = "FROM"
    JOIN = "JOIN"
    WHERE = "WHERE"
    GROUP_BY = "GROUP_BY"
    HAVING = "HAVING"


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class DiffFinding(BaseModel):
    clause: ClauseType
    rule_id: str
    severity: Severity
    a_snippet: str = ""
    b_snippet: str = ""
    description: str
    impact: str = ""
    user_acknowledged: bool = False  # 사용자가 "동일하다고 판단"한 finding


class StructureDiff(BaseModel):
    has_difference: bool = False
    fast_path_terminate: bool = False       # 미확인 Critical 1건 이상 시 True
    dominant_clause: Optional[ClauseType] = None
    unresolved_critical_count: int = 0      # 사용자 확인되지 않은 Critical 건수
    findings: list[DiffFinding] = Field(default_factory=list)


class AcknowledgeRequest(BaseModel):
    acknowledged: bool = True


# --- 의미 비교 (신규) ---

class SemanticVerdict(str, Enum):
    EQUIVALENT = "EQUIVALENT"     # 두 쿼리가 같은 데이터를 반환할 것으로 판정
    DIVERGENT = "DIVERGENT"       # 차이가 있어 다른 결과 예상
    LIMITED = "LIMITED"           # 정규화 불가 구문이 있어 부분 비교만 수행


class DimensionName(str, Enum):
    BASE_TABLES = "BASE_TABLES"         # 실제 읽는 base 테이블 집합
    JOIN_GRAPH = "JOIN_GRAPH"           # 조인 edge (left,right,type,on) 집합
    PREDICATES = "PREDICATES"           # WHERE + HAVING 통합 predicate 집합
    GROUP_KEYS = "GROUP_KEYS"           # GROUP BY 키 집합
    AGGREGATES = "AGGREGATES"           # (함수, 인자) 집합
    PROJECTIONS = "PROJECTIONS"         # 비집계 출력 컬럼 집합 (참고용)


class JoinEdge(BaseModel):
    left_table: str
    right_table: str
    join_type: str
    on_predicates: list[str] = Field(default_factory=list)

    def canonical_key(self) -> str:
        """동일성 비교를 위한 canonical key. left/right 순서 무관 처리."""
        l, r = sorted([self.left_table, self.right_table])
        preds = "|".join(sorted(self.on_predicates))
        return f"{l}<->{r}::{self.join_type}::{preds}"


class LogicalPlan(BaseModel):
    base_tables: list[str] = Field(default_factory=list)           # sorted lower-case names
    join_edges: list[JoinEdge] = Field(default_factory=list)
    all_predicates: list[str] = Field(default_factory=list)        # sorted canonical
    group_keys: list[str] = Field(default_factory=list)
    aggregates: list[tuple[str, str]] = Field(default_factory=list)  # (func, arg)
    projections: list[str] = Field(default_factory=list)           # non-aggregate
    limitations: list[str] = Field(default_factory=list)           # 정규화 불가 사유


class DimensionResult(BaseModel):
    dimension: DimensionName
    matched: bool
    only_in_a: list[str] = Field(default_factory=list)
    only_in_b: list[str] = Field(default_factory=list)
    shared: list[str] = Field(default_factory=list)
    explanation: str = ""            # 해당 차원이 같은 이유 / 다른 이유 자연어 설명


class SemanticDiff(BaseModel):
    verdict: SemanticVerdict
    reason: str = ""                 # 최종 판정 요약 (자연어)
    plan_a: Optional[LogicalPlan] = None
    plan_b: Optional[LogicalPlan] = None
    dimensions: list[DimensionResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)  # A·B 통합 제한 사유
    error: Optional[str] = None      # 정규화 자체가 실패한 경우


class ComparisonRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    status: ComparisonStatus = ComparisonStatus.DRAFT
    query_a: QueryInput = Field(default_factory=lambda: QueryInput(dialect=Dialect.ORACLE))
    query_b: QueryInput = Field(default_factory=lambda: QueryInput(dialect=Dialect.HIVE))
    summary: DiffSummary = Field(default_factory=DiffSummary)
    matching_keys: list[MatchingKey] = Field(default_factory=list)
    structure_diff: Optional[StructureDiff] = None
    semantic_diff: Optional[SemanticDiff] = None


# --- API 요청/응답 스키마 ---

class QueryInputUpdate(BaseModel):
    source_type: Optional[SourceType] = None
    sql_raw: Optional[str] = None
    dialect: Optional[Dialect] = None
    file_name: Optional[str] = None
    wiki_url: Optional[str] = None


class SummaryUpdate(BaseModel):
    metrics: list[DiffMetric]


class WikiExtractRequest(BaseModel):
    url: str


class WikiBlock(BaseModel):
    index: int
    preview: str
    lines: int
    language: str = "sql"


class WikiExtractResponse(BaseModel):
    blocks: list[WikiBlock]


class ValidationResult(BaseModel):
    is_valid: bool
    dialect_detected: Optional[str] = None
    structure: Optional[QueryStructure] = None
    error_line: Optional[int] = None
    error_message: Optional[str] = None
    suggestion: Optional[str] = None


class ValidateResponse(BaseModel):
    query_a: Optional[ValidationResult] = None
    query_b: Optional[ValidationResult] = None
