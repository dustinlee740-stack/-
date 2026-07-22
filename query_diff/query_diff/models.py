"""쿼리 비교 모듈 도메인 모델"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, computed_field

# ON 조건 문자열에서 `table.col` 의 테이블 한정자 추출용
_TABLE_REF_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.[A-Za-z_]")

# 두 단순 피연산자의 등치(조인 키) 판정 — 양변이 공백 없는 토큰(컬럼/리터럴)일 때만.
# `t.channel = CASE WHEN u.x ... END` 같은 필터성 조건은 매칭되지 않는다(값 표현식에 공백/괄호).
_EQUI_JOIN_RE = re.compile(r"""^[\w.'"]+ = [\w.'"]+$""")


def _is_equi_join_key(p: str) -> bool:
    """조인 **키**(양변이 모두 `테이블.컬럼`)인 등치만 인정 — `컬럼 = 리터럴` 필터는 제외.

    ON 절에 `AI.RN = 1`(윈도우 순위 필터)처럼 `컬럼 = 리터럴` 이 섞이면, 조인 대상이 아닌
    테이블(예: CTE명 `address_info`)을 조인 테이블집합에 잘못 끌어와 페어링·라벨을 오염시킨다.
    조인 키는 두 테이블 컬럼을 잇는 등치뿐이므로 양변 모두 `테이블.컬럼` 일 때만 조인 키로 본다.
    """
    if not _EQUI_JOIN_RE.match(p):
        return False
    lhs, _, rhs = p.partition(" = ")
    return bool(_TABLE_REF_RE.search(lhs)) and bool(_TABLE_REF_RE.search(rhs))


def _edge_table_set(
    on_predicates: list[str], left_table: str = "", right_table: str = ""
) -> set[str]:
    """조인 엣지의 테이블 집합(앵커 무관). 조인 그래프는 **등치 조인 키**로 정의한다.

    `t.channel = CASE WHEN u.x ... END` 처럼 값 표현식(CASE·함수) 안에서만 참조되는 테이블(u)
    은 조인 대상으로 끌어오지 않는다 — 그러면 같은 조인이 한쪽에서만 테이블집합이 부풀어
    페어링이 깨진다(예: 채널 CASE 가 ias_transaction 을 끌어와 2-테이블 조인이 3-테이블로).
    마찬가지로 `AI.RN = 1` 같은 `컬럼 = 리터럴` 필터도 조인 키가 아니므로 제외한다
    (`_is_equi_join_key`). 등치 키로 2개 미만이면(CROSS·복합조건 등) 전체 참조 + left/right 로 보강.
    """
    ts: set[str] = set()
    for p in on_predicates:
        if _is_equi_join_key(p):
            ts.update(_TABLE_REF_RE.findall(p))
    if len(ts) < 2:
        for p in on_predicates:
            ts.update(_TABLE_REF_RE.findall(p))
        ts.update(t for t in (left_table, right_table) if t)
    return ts


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
        """동일성 비교를 위한 canonical key.

        **앵커-독립:** FROM 앵커(left_table)가 아니라 **ON 조건이 참조하는 테이블 집합**으로
        조인을 식별한다. A(FROM 직접 조인)는 모든 조인을 FROM 테이블에 매달고, B(WITH CTE)는
        CTE 내부 테이블에 매달아 left_table 이 달라지는데, 실제 조인 의미는 ON 조건의 테이블·
        컬럼에 있으므로 이를 기준으로 비교해야 같은 조인이 매칭된다.
        """
        tables = _edge_table_set(self.on_predicates, self.left_table, self.right_table)
        tbl = ",".join(sorted(t for t in tables if t))
        preds = "|".join(sorted(self.on_predicates))
        return f"{tbl}::{self.join_type}::{preds}"


class LogicalPlan(BaseModel):
    base_tables: list[str] = Field(default_factory=list)           # sorted lower-case names
    join_edges: list[JoinEdge] = Field(default_factory=list)
    all_predicates: list[str] = Field(default_factory=list)        # sorted canonical (WHERE ∪ HAVING)
    where_predicates: list[str] = Field(default_factory=list)      # sorted canonical (WHERE만)
    having_predicates: list[str] = Field(default_factory=list)     # sorted canonical (HAVING만)
    pred_display: dict[str, str] = Field(default_factory=dict)     # canonical → 표시용 자연형(컬럼 op 값·!=)
    pred_order: dict[str, int] = Field(default_factory=dict)       # canonical → 원문 WHERE/HAVING 등장 순서
    group_keys: list[str] = Field(default_factory=list)
    aggregates: list[tuple[str, str]] = Field(default_factory=list)  # (func, arg)
    projections: list[str] = Field(default_factory=list)           # non-aggregate
    limitations: list[str] = Field(default_factory=list)           # 정규화 불가 사유
    empty_form_preds: list[str] = Field(default_factory=list)      # '' 형(= ''/!= '')에서 온 null-체크 canonical


class DimensionResult(BaseModel):
    dimension: DimensionName
    matched: bool
    limited: bool = False            # 통과지만 '제한적 판정'(소프트 동치 등 — 확인 권장)
    only_in_a: list[str] = Field(default_factory=list)
    only_in_b: list[str] = Field(default_factory=list)
    shared: list[str] = Field(default_factory=list)
    explanation: str = ""            # 간결 헤드라인 (한 줄)
    caveat: str = ""                 # 제한/주의 상세 (여러 줄, \n 구분 — 구조화 블록 렌더)


class SemanticDiff(BaseModel):
    verdict: SemanticVerdict
    reason: str = ""                 # 판정 요약 헤드라인 (한 줄)
    issues: list[str] = Field(default_factory=list)  # 전 차원 문제 총합(✗ 차이 / ⚠ 제한·주의)
    plan_a: Optional[LogicalPlan] = None
    plan_b: Optional[LogicalPlan] = None
    dimensions: list[DimensionResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)  # A·B 통합 제한 사유
    error: Optional[str] = None      # 정규화 자체가 실패한 경우


# --- 2차 판단: 실데이터 샘플 대조 (No.4/No.5 Row diff — 운영 A샘플 ↔ Hue 실행 B샘플) ---

class ReconcileStatus(str, Enum):
    MATCH = "MATCH"                # 샘플 일치 (참고 — 동치 증명 아님, 우연 일치 가능)
    MISMATCH = "MISMATCH"          # 샘플 불일치 (실차이 근거)
    PARTIAL = "PARTIAL"            # 일부 일치·일부 불일치
    UNVERIFIABLE = "UNVERIFIABLE"  # 대조 불가 (샘플 미제공·조회 실패·CLI 부재 등)


class FinalVerdict(str, Enum):
    """1차(정적)+2차(실데이터)를 종합한 단일 최종 판정."""
    SAME = "SAME"                  # 같은 결과로 판단
    DIFFERENT = "DIFFERENT"        # 다른 결과로 판단
    INCONCLUSIVE = "INCONCLUSIVE"  # 결론 유보 (근거 상충·미검증)


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class Attribution(str, Enum):
    """차이 귀인(flow.md No.6) — 차이가 있을 때 그 원인."""
    QUERY = "QUERY"      # 쿼리(구조) 차이 기인
    DATA = "DATA"        # 원천 데이터 차이 기인 (분석계 미적재·스냅샷 등)
    UNKNOWN = "UNKNOWN"  # 판단 보류 / 해당 없음


class RowMismatch(BaseModel):
    key: str = ""            # 매칭 키 값 (예: "20250501|BANK01")
    column: str = ""         # 불일치 컬럼 (해소명)
    value_a: str = ""        # 운영(A) 값
    value_b: str = ""        # 분석(B) 값
    likely_cause: str = ""   # 추정 원인 (집계 그레인/NULL·''/날짜포맷·반올림/조인 카디널리티 등)


class DataReconcileDiff(BaseModel):
    """2차 판단 결과. B(분석계)를 Hue에서 실행한 샘플과 사용자 제공 A(운영계) 샘플의 대조.

    **참고 신호이지 동치 증명이 아니다**: 일치=약한 긍정(우연 일치 가능), 불일치=강한 실차이 근거.
    """
    status: ReconcileStatus
    headline: str = ""       # 좌측 헤드라인 한 줄
    row_count_a: Optional[int] = None
    row_count_b: Optional[int] = None
    matched_keys: int = 0
    mismatches: list[RowMismatch] = Field(default_factory=list)
    only_in_a: list[str] = Field(default_factory=list)   # A(운영)에만 있는 키
    only_in_b: list[str] = Field(default_factory=list)   # B(분석)에만 있는 키
    caveats: list[str] = Field(default_factory=list)     # 우연일치·그레인·표본유계 등 주의
    binds_used: dict[str, str] = Field(default_factory=dict)  # 실제 대입한 바인드값
    b_csv_path: Optional[str] = None       # 산출된 B 결과 CSV 경로(아티팩트)
    a_sample_name: Optional[str] = None    # 업로드된 A 샘플 파일명
    sample_bounded: bool = False           # B가 ORDER BY+LIMIT 유계 표본이면 True
    error: Optional[str] = None
    # 종합 판정(1차+2차 통합) — 2차 서브프로세스가 1차 결과까지 받아 추론
    final_verdict: Optional[FinalVerdict] = None
    final_confidence: Optional[Confidence] = None
    final_reason: str = ""                 # 1·2차 근거를 종합한 한두 줄 추론
    attribution: Optional[Attribution] = None


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
    # 2차 판단(실데이터 대조) — 입력(A샘플·바인드)과 결과(data_reconcile)
    data_reconcile: Optional[DataReconcileDiff] = None
    sample_a_csv: Optional[str] = None        # 사용자 업로드 운영(A) 결과 CSV 원문
    sample_a_filename: Optional[str] = None
    # 1차 비교 값 치환용 바인드값(A는 `:name`, B는 `${name}`). B는 2차 Hue 실행에도 사용.
    sample_binds_a: dict[str, str] = Field(default_factory=dict)  # A(운영) 쿼리 바인드값
    sample_binds_b: dict[str, str] = Field(default_factory=dict)  # B(분석) 쿼리 바인드값


# --- API 요청/응답 스키마 ---

class QueryInputUpdate(BaseModel):
    source_type: Optional[SourceType] = None
    sql_raw: Optional[str] = None
    dialect: Optional[Dialect] = None
    file_name: Optional[str] = None
    wiki_url: Optional[str] = None


class SummaryUpdate(BaseModel):
    metrics: list[DiffMetric]


class SampleAUpdate(BaseModel):
    """운영(A) 결과 샘플 업로드 — 프런트가 CSV 를 클라이언트에서 읽어 텍스트로 전송."""
    csv: Optional[str] = None
    filename: Optional[str] = None
    binds_a: Optional[dict[str, str]] = None   # A(운영) 쿼리 바인드값(`:name`)
    binds_b: Optional[dict[str, str]] = None   # B(분석) 쿼리 바인드값(`${name}`)


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
