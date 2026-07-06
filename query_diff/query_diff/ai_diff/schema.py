"""Claude 구조화 출력용 스키마 (AiSemanticDiff) + models.SemanticDiff 로의 매핑.

`claude -p --json-schema` 는 JSON Schema 를 요구하고, 구조화 출력 제약(객체마다
`additionalProperties: false` + 모든 속성 `required`, 재귀·수치제약 불가)을 지킨다.
그래서 Pydantic 모델과 **손으로 쓴 호환 스키마**(AI_SEMANTIC_DIFF_SCHEMA)를 함께 둔다.
models.py 는 무변경 — 여기서 models.SemanticDiff 로 변환한다(plan_a/plan_b 는 None).
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from query_diff.models import (
    DimensionName,
    DimensionResult,
    SemanticDiff,
    SemanticVerdict,
)

_DIM_VALUES = [d.value for d in DimensionName]
_VERDICT_VALUES = [v.value for v in SemanticVerdict]


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
