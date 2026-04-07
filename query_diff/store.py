"""인메모리 비교 요청 저장소"""

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


# 싱글턴 인스턴스
store = ComparisonStore()
