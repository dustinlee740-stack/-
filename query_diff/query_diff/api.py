"""쿼리 비교 모듈 — FastAPI 엔드포인트"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from query_diff.models import (
    AcknowledgeRequest,
    ComparisonRequest,
    ComparisonStatus,
    DiffSummary,
    QueryInputUpdate,
    SemanticDiff,
    StructureDiff,
    SummaryUpdate,
    ValidateResponse,
    WikiExtractRequest,
    WikiExtractResponse,
)
from query_diff.semantic_diff import compare_semantic
from query_diff.store import store
from query_diff.structure_diff import compare_structures
from query_diff.structure_diff.comparator import recompute_state
from query_diff.structure_diff.schema_mapping import OpAnMap, load_op_an_map
from query_diff.validation_service import validate_query_input
from query_diff.wiki_service import extract_sql_blocks_from_html, extract_sql_from_url

import logging

_log = logging.getLogger("query_diff.api")


def _op_an_map() -> OpAnMap | None:
    """운영→분석 매핑 아티팩트를 1회 로드(캐싱). 로드 실패 시 None(매핑 미적용 fallback).

    경로는 환경변수 OP_AN_MAP_PATH 로 재정의 가능(기본: query_diff/data/op_an_map.json).
    """
    try:
        return load_op_an_map(os.environ.get("OP_AN_MAP_PATH"))
    except Exception as e:  # 아티팩트 부재/손상 시 매핑 없이 진행
        _log.warning("op_an_map 로드 실패 — 스키마 매핑 미적용으로 진행: %s", e)
        return None


app = FastAPI(title="Query Diff Module", version="0.1.0")

# CORS 설정 — 환경변수로 허용 origin 제어
# 배포 시 ALLOWED_ORIGINS 환경변수를 설정하지 않으면 서버 기동이 차단됨
_allowed_origins_env = os.environ.get("ALLOWED_ORIGINS", "")
if os.environ.get("QUERY_DIFF_ENV", "dev") == "prod" and not _allowed_origins_env:
    raise RuntimeError(
        "ALLOWED_ORIGINS 환경변수가 설정되지 않았습니다. "
        "prod 환경에서는 ALLOWED_ORIGINS=https://internal.example.com 형식으로 설정해주세요."
    )
_allowed_origins = (
    [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
    if _allowed_origins_env
    else ["*"]  # dev 환경에서만 허용
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 서빙 (프론트엔드)
_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/")
def index():
    index_path = os.path.join(_static_dir, "index.html")
    if os.path.isfile(index_path):
        # no-cache: 캐시는 하되 사용 전 ETag/Last-Modified 재검증 → 프런트엔드 변경이
        # 브라우저 휴리스틱 캐싱 때문에 옛 버전으로 굳는 것을 방지(미변경 시 304로 가벼움).
        return FileResponse(index_path, headers={"Cache-Control": "no-cache"})
    return {"message": "Query Diff Module API"}


# --- 비교 요청 CRUD ---

@app.post("/api/comparisons", response_model=ComparisonRequest)
def create_comparison(title: str = ""):
    req = ComparisonRequest(title=title)
    return store.create(req)


@app.get("/api/comparisons/{req_id}", response_model=ComparisonRequest)
def get_comparison(req_id: str):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")
    return req


@app.get("/api/comparisons", response_model=list[ComparisonRequest])
def list_comparisons():
    return store.list_all()


# --- 쿼리 입력 ---

def _apply_query_update(query: "QueryInput", body: QueryInputUpdate) -> None:
    """A/B 쿼리 공통 업데이트 로직"""
    if body.source_type is not None:
        query.source_type = body.source_type
    if body.sql_raw is not None:
        query.sql_raw = body.sql_raw
    if body.dialect is not None:
        query.dialect = body.dialect
    if body.file_name is not None:
        query.file_name = body.file_name
    if body.wiki_url is not None:
        query.wiki_url = body.wiki_url

    query.is_valid = None
    query.validation_error = None
    query.structure = None
    query.sql_normalized = None


@app.put("/api/comparisons/{req_id}/query-a", response_model=ComparisonRequest)
def update_query_a(req_id: str, body: QueryInputUpdate):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    _apply_query_update(req.query_a, body)
    req.status = ComparisonStatus.DRAFT
    return store.update(req)


@app.put("/api/comparisons/{req_id}/query-b", response_model=ComparisonRequest)
def update_query_b(req_id: str, body: QueryInputUpdate):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    _apply_query_update(req.query_b, body)
    req.status = ComparisonStatus.DRAFT
    return store.update(req)


# --- 차이 요약 ---

@app.put("/api/comparisons/{req_id}/summary", response_model=ComparisonRequest)
def update_summary(req_id: str, body: SummaryUpdate):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    req.summary = DiffSummary(metrics=body.metrics)
    return store.update(req)


# --- 검증 ---

@app.post("/api/comparisons/{req_id}/validate", response_model=ValidateResponse)
def validate_comparison(req_id: str):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    req.status = ComparisonStatus.VALIDATING

    result_a = validate_query_input(req.query_a)
    result_b = validate_query_input(req.query_b)

    if result_a.is_valid and result_b.is_valid:
        req.status = ComparisonStatus.READY
    else:
        req.status = ComparisonStatus.ERROR

    store.update(req)

    return ValidateResponse(query_a=result_a, query_b=result_b)


# --- Wiki 추출 ---

@app.post("/api/comparisons/{req_id}/extract-wiki", response_model=WikiExtractResponse)
def extract_wiki(req_id: str, body: WikiExtractRequest):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    try:
        blocks, _ = extract_sql_from_url(body.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Wiki 페이지 접근 실패: {e}")

    return WikiExtractResponse(blocks=blocks)


# --- 비교 실행 (Phase 1 진입점) ---

@app.post("/api/comparisons/{req_id}/execute", response_model=ComparisonRequest)
def execute_comparison(req_id: str):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    if req.status not in (ComparisonStatus.READY, ComparisonStatus.DONE):
        raise HTTPException(status_code=400, detail="검증 완료 상태에서만 실행할 수 있습니다.")

    # 차이 요약(metrics)은 선택 입력. 비어 있어도 비교 실행을 막지 않는다.

    op_an = _op_an_map()
    req.status = ComparisonStatus.COMPARING
    try:
        req.structure_diff = compare_structures(req.query_a, req.query_b, op_an=op_an)
    except Exception as e:
        req.status = ComparisonStatus.ERROR
        store.update(req)
        raise HTTPException(status_code=500, detail=f"구조 비교 실패: {e}")

    # 의미 비교는 구문 비교와 병존. 의미 비교 실패는 전체 실행을 막지 않고
    # SemanticDiff.error 에 사유를 담아 반환한다.
    try:
        req.semantic_diff = compare_semantic(
            req.query_a.sql_raw,
            req.query_a.dialect,
            req.query_b.sql_raw,
            req.query_b.dialect,
            op_an=op_an,
        )
    except Exception as e:
        from query_diff.models import SemanticVerdict
        req.semantic_diff = SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="의미 비교 중 예기치 못한 오류가 발생했습니다.",
            error=str(e),
        )

    # Critical 1건 이상이면 fast-path 종결, 아니면 Row diff 단계로 진행해야 하지만
    # No.5 Row diff가 아직 구현되지 않았으므로 현재는 DONE으로 종료.
    req.status = ComparisonStatus.DONE
    store.update(req)

    return req


# --- AI 비교 실행 (개인·로컬: 헤드리스 claude -p 구독 + MCP 스킬) ---

@app.post("/api/comparisons/{req_id}/execute-ai", response_model=ComparisonRequest)
async def execute_ai_comparison(req_id: str):
    """의미 비교를 파이썬 엔진 대신 Claude+MCP(query-diff-compare 스킬)로 수행.

    구문 비교는 결정적 파이썬 엔진을 유지하고, 의미 비교만 AI 경로로 대체한다(기존 execute와 병존).
    claude CLI 부재·오류는 500이 아니라 SemanticDiff(LIMITED)로 반환한다.
    """
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    if req.status not in (ComparisonStatus.READY, ComparisonStatus.DONE):
        raise HTTPException(status_code=400, detail="검증 완료 상태에서만 실행할 수 있습니다.")

    op_an = _op_an_map()
    req.status = ComparisonStatus.COMPARING
    try:
        req.structure_diff = compare_structures(req.query_a, req.query_b, op_an=op_an)
    except Exception as e:
        req.status = ComparisonStatus.ERROR
        store.update(req)
        raise HTTPException(status_code=500, detail=f"구조 비교 실패: {e}")

    try:
        from query_diff.ai_diff import compare_via_cli  # 지연 임포트

        req.semantic_diff = await compare_via_cli(
            req.query_a.sql_raw,
            req.query_a.dialect,
            req.query_b.sql_raw,
            req.query_b.dialect,
            op_an=op_an,
        )
    except Exception as e:
        from query_diff.models import SemanticVerdict

        req.semantic_diff = SemanticDiff(
            verdict=SemanticVerdict.LIMITED,
            reason="AI 의미 비교 중 예기치 못한 오류가 발생했습니다.",
            error=str(e),
        )

    req.status = ComparisonStatus.DONE
    store.update(req)

    return req


# --- 구조 비교 독립 엔드포인트 ---

@app.post("/api/comparisons/{req_id}/structure-diff", response_model=StructureDiff)
def run_structure_diff(req_id: str):
    """AST 기반 쿼리 구조 비교만 단독 실행. 검증 완료 상태에서 호출 가능.

    execute와 달리 summary 입력을 요구하지 않고 구조 차이 결과만 반환한다.
    """
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    if not (req.query_a.is_valid and req.query_b.is_valid):
        raise HTTPException(
            status_code=400,
            detail="두 쿼리 모두 검증(validate)이 성공한 상태여야 합니다.",
        )

    try:
        diff = compare_structures(req.query_a, req.query_b, op_an=_op_an_map())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"구조 비교 실패: {e}")

    req.structure_diff = diff
    store.update(req)
    return diff


@app.get("/api/comparisons/{req_id}/structure-diff", response_model=StructureDiff)
def get_structure_diff(req_id: str):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")
    if req.structure_diff is None:
        raise HTTPException(status_code=404, detail="아직 구조 비교가 실행되지 않았습니다.")
    return req.structure_diff


@app.patch(
    "/api/comparisons/{req_id}/structure-diff/findings/{index}",
    response_model=StructureDiff,
)
def acknowledge_finding(req_id: str, index: int, body: AcknowledgeRequest):
    """특정 finding을 사용자가 '동일하다고 판단'으로 마킹/해제.

    모든 Critical이 acknowledged 되면 fast_path_terminate가 False로 전환되어
    다음 단계(Row diff)로 진행 가능한 상태가 된다.
    """
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")
    if req.structure_diff is None:
        raise HTTPException(status_code=404, detail="아직 구조 비교가 실행되지 않았습니다.")
    if not (0 <= index < len(req.structure_diff.findings)):
        raise HTTPException(status_code=404, detail="해당 finding이 존재하지 않습니다.")

    req.structure_diff.findings[index].user_acknowledged = body.acknowledged
    recompute_state(req.structure_diff)
    store.update(req)
    return req.structure_diff


# --- 의미 비교 독립 엔드포인트 ---

@app.post("/api/comparisons/{req_id}/semantic-diff", response_model=SemanticDiff)
def run_semantic_diff(req_id: str):
    """sqlglot 옵티마이저 기반 의미 동치성 비교.

    구문(FROM-조인 vs WITH-CTE)이 달라도 같은 데이터를 반환하는지 판정한다.
    """
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")

    if not (req.query_a.is_valid and req.query_b.is_valid):
        raise HTTPException(
            status_code=400,
            detail="두 쿼리 모두 검증(validate)이 성공한 상태여야 합니다.",
        )

    diff = compare_semantic(
        req.query_a.sql_raw,
        req.query_a.dialect,
        req.query_b.sql_raw,
        req.query_b.dialect,
        op_an=_op_an_map(),
    )
    req.semantic_diff = diff
    store.update(req)
    return diff


@app.get("/api/comparisons/{req_id}/semantic-diff", response_model=SemanticDiff)
def get_semantic_diff(req_id: str):
    req = store.get(req_id)
    if not req:
        raise HTTPException(status_code=404, detail="비교 요청을 찾을 수 없습니다.")
    if req.semantic_diff is None:
        raise HTTPException(status_code=404, detail="아직 의미 비교가 실행되지 않았습니다.")
    return req.semantic_diff
