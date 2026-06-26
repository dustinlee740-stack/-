"""인메모리 비교 요청 저장소

제약사항:
  - 싱글톤 dict 기반이므로 단일 워커(uvicorn --workers 1)에서만 동작합니다.
  - 멀티 워커 환경에서는 프로세스 간 상태가 격리되므로 DB(Redis/PostgreSQL)로 교체해야 합니다.
"""

from __future__ import annotations

from query_diff.models import ComparisonRequest


class ComparisonStore:
    def __init__(self) -> None:
        self._data: dict[str, ComparisonRequest] = {}

    def create(self, req: ComparisonRequest) -> ComparisonRequest:
        self._data[req.id] = req
        return req

    def get(self, req_id: str) -> ComparisonRequest | None:
        return self._data.get(req_id)

    def update(self, req: ComparisonRequest) -> ComparisonRequest:
        self._data[req.id] = req
        return req

    def list_all(self) -> list[ComparisonRequest]:
        return list(self._data.values())

    def clear(self) -> None:
        """저장소 초기화 (테스트용)"""
        self._data.clear()


# 싱글턴 인스턴스
store = ComparisonStore()
