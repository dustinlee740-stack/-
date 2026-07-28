"""Claude 구조화 출력용 스키마 (AiSemanticDiff) + models.SemanticDiff 로의 매핑.

`claude -p --json-schema` 는 JSON Schema 를 요구하고, 구조화 출력 제약(객체마다
`additionalProperties: false` + 모든 속성 `required`, 재귀·수치제약 불가)을 지킨다.
그래서 Pydantic 모델과 **손으로 쓴 호환 스키마**(AI_SEMANTIC_DIFF_SCHEMA)를 함께 둔다.
models.py 는 무변경 — 여기서 models.SemanticDiff 로 변환한다(plan_a/plan_b 는 None).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from query_diff.models import (
    Attribution,
    Confidence,
    DataReconcileDiff,
    DimensionName,
    DimensionResult,
    FinalVerdict,
    ReconcileStatus,
    RowMismatch,
    SemanticDiff,
    SemanticVerdict,
)

_DIM_VALUES = [d.value for d in DimensionName]
_VERDICT_VALUES = [v.value for v in SemanticVerdict]
_RECON_STATUS_VALUES = [s.value for s in ReconcileStatus]
_FINAL_VERDICT_VALUES = [v.value for v in FinalVerdict]
_CONFIDENCE_VALUES = [c.value for c in Confidence]
_ATTRIBUTION_VALUES = [a.value for a in Attribution]


class AiDimensionResult(BaseModel):
    """models.DimensionResult 와 1:1 (plan 의존 없는 표시 필드만)."""

    dimension: DimensionName
    matched: bool
    limited: bool = False
    only_in_a: list[str] = Field(default_factory=list)
    only_in_b: list[str] = Field(default_factory=list)
    shared: list[str] = Field(default_factory=list)
    explanation: str = ""
    caveat: str = ""


class AiSemanticDiff(BaseModel):
    """Claude 가 제출하는 구조화 결과. models.SemanticDiff 의 렌더 필드 부분집합."""

    verdict: SemanticVerdict
    reason: str = ""
    issues: list[str] = Field(default_factory=list)
    dimensions: list[AiDimensionResult] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_semantic_diff(self) -> SemanticDiff:
        return SemanticDiff(
            verdict=self.verdict,
            reason=self.reason,
            issues=list(self.issues),
            plan_a=None,
            plan_b=None,
            dimensions=[
                DimensionResult(
                    dimension=d.dimension,
                    matched=d.matched,
                    limited=d.limited,
                    only_in_a=list(d.only_in_a),
                    only_in_b=list(d.only_in_b),
                    shared=list(d.shared),
                    explanation=d.explanation,
                    caveat=d.caveat,
                )
                for d in self.dimensions
            ],
            limitations=list(self.limitations),
        )


def _str_array() -> dict:
    return {"type": "array", "items": {"type": "string"}}


# 구조화 출력용 JSON Schema (제약 준수: additionalProperties=false, 전 속성 required).
_DIMENSION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "dimension": {"type": "string", "enum": _DIM_VALUES},
        "matched": {"type": "boolean"},
        "limited": {"type": "boolean"},
        "only_in_a": _str_array(),
        "only_in_b": _str_array(),
        "shared": _str_array(),
        "explanation": {"type": "string"},
        "caveat": {"type": "string"},
    },
    "required": [
        "dimension",
        "matched",
        "limited",
        "only_in_a",
        "only_in_b",
        "shared",
        "explanation",
        "caveat",
    ],
}

AI_SEMANTIC_DIFF_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "verdict": {"type": "string", "enum": _VERDICT_VALUES},
        "reason": {"type": "string"},
        "issues": _str_array(),
        "dimensions": {"type": "array", "items": _DIMENSION_SCHEMA},
        "limitations": _str_array(),
    },
    "required": ["verdict", "reason", "issues", "dimensions", "limitations"],
}


# ============================================================================
# 2차 판단(실데이터 대조) 구조화 출력 — AiDataReconcile
# ============================================================================

class AiRowMismatch(BaseModel):
    """models.RowMismatch 와 1:1."""

    key: str = ""
    column: str = ""
    value_a: str = ""
    value_b: str = ""
    likely_cause: str = ""


class AiDataReconcile(BaseModel):
    """Claude 가 제출하는 2차 대조 결과. models.DataReconcileDiff 의 렌더 필드 부분집합.

    binds_used·a_sample_name 은 서버가 채운다(입력을 알고 있으므로). b_csv_path 는 AI 가
    실제로 기록한 경로를 에코(서버 지정 경로가 우선).
    """

    status: ReconcileStatus
    headline: str = ""
    row_count_a: int = 0
    row_count_b: int = 0
    row_count_b_total: int = 0    # B 전체 결과 행수(SELECT COUNT(*) 결과값) — 서버가 표본/전체 표기에 사용
    matched_keys: int = 0
    mismatches: list[AiRowMismatch] = Field(default_factory=list)
    only_in_a: list[str] = Field(default_factory=list)
    only_in_b: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    sample_bounded: bool = False
    b_csv_path: str = ""
    # 종합 판정(1차+2차) — 서브프로세스가 1차 결과까지 받아 추론
    final_verdict: FinalVerdict = FinalVerdict.INCONCLUSIVE
    final_confidence: Confidence = Confidence.LOW
    final_reason: str = ""
    attribution: Attribution = Attribution.UNKNOWN

    def to_data_reconcile(
        self,
        *,
        binds: dict[str, str] | None = None,
        a_sample_name: str | None = None,
        b_csv_path: str | None = None,
    ) -> DataReconcileDiff:
        return DataReconcileDiff(
            status=self.status,
            headline=self.headline,
            row_count_a=self.row_count_a,
            row_count_b=self.row_count_b,
            row_count_b_total=self.row_count_b_total or None,
            matched_keys=self.matched_keys,
            mismatches=[
                RowMismatch(
                    key=m.key,
                    column=m.column,
                    value_a=m.value_a,
                    value_b=m.value_b,
                    likely_cause=m.likely_cause,
                )
                for m in self.mismatches
            ],
            only_in_a=list(self.only_in_a),
            only_in_b=list(self.only_in_b),
            caveats=list(self.caveats),
            binds_used=dict(binds or {}),
            b_csv_path=b_csv_path or (self.b_csv_path or None),
            a_sample_name=a_sample_name,
            sample_bounded=self.sample_bounded,
            final_verdict=self.final_verdict,
            final_confidence=self.final_confidence,
            final_reason=self.final_reason,
            attribution=self.attribution,
        )


_ROW_MISMATCH_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "key": {"type": "string"},
        "column": {"type": "string"},
        "value_a": {"type": "string"},
        "value_b": {"type": "string"},
        "likely_cause": {"type": "string"},
    },
    "required": ["key", "column", "value_a", "value_b", "likely_cause"],
}

AI_DATA_RECONCILE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {"type": "string", "enum": _RECON_STATUS_VALUES},
        "headline": {"type": "string"},
        "row_count_a": {"type": "integer"},
        "row_count_b": {"type": "integer"},
        "row_count_b_total": {"type": "integer"},
        "matched_keys": {"type": "integer"},
        "mismatches": {"type": "array", "items": _ROW_MISMATCH_SCHEMA},
        "only_in_a": _str_array(),
        "only_in_b": _str_array(),
        "caveats": _str_array(),
        "sample_bounded": {"type": "boolean"},
        "b_csv_path": {"type": "string"},
        "final_verdict": {"type": "string", "enum": _FINAL_VERDICT_VALUES},
        "final_confidence": {"type": "string", "enum": _CONFIDENCE_VALUES},
        "final_reason": {"type": "string"},
        "attribution": {"type": "string", "enum": _ATTRIBUTION_VALUES},
    },
    "required": [
        "status",
        "headline",
        "row_count_a",
        "row_count_b",
        "row_count_b_total",
        "matched_keys",
        "mismatches",
        "only_in_a",
        "only_in_b",
        "caveats",
        "sample_bounded",
        "b_csv_path",
        "final_verdict",
        "final_confidence",
        "final_reason",
        "attribution",
    ],
}
