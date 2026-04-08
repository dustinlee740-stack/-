"""쿼리 비교 모듈 — FastAPI 엔드포인트"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from query_diff.models import (
    ComparisonRequest,
    ComparisonStatus,
    DiffSummary,
    QueryInputUpdate,
    SummaryUpdate,
    ValidateResponse,
    WikiExtractRequest,
    WikiExtractResponse,
)
from query_diff.store import store
from query_diff.validation_service import validate_query_input
from query_diff.wiki_service import extract_sql_blocks_from_html, extract_sql_from_url

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
        return FileResponse(index_path)
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

    if not req.summary.metrics:
        raise HTTPException(status_code=400, detail="차이 요약을 최소 1개 입력해주세요.")

    req.status = ComparisonStatus.COMPARING
    # TODO: Phase 1 쿼리 구조 비교 실행 연동
    req.status = ComparisonStatus.DONE
    store.update(req)

    return req
