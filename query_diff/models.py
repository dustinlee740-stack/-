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


class ComparisonRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    created_at: datetime = Field(default_factory=datetime.now)
    status: ComparisonStatus = ComparisonStatus.DRAFT
    query_a: QueryInput = Field(default_factory=lambda: QueryInput(dialect=Dialect.ORACLE))
    query_b: QueryInput = Field(default_factory=lambda: QueryInput(dialect=Dialect.HIVE))
    summary: DiffSummary = Field(default_factory=DiffSummary)
    matching_keys: list[MatchingKey] = Field(default_factory=list)


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
