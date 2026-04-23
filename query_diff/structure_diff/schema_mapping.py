"""스키마 매핑 인터페이스

운영계(Oracle) ↔ 분석계(Hive) 테이블·컬럼 매핑 프로토콜.
현재는 IdentitySchemaMapping (동명이면 동일)만 제공. No.3 매핑 모듈 완성 시
동일 프로토콜 구현체로 교체 가능하도록 주입 인터페이스로 설계.
"""

from __future__ import annotations

from typing import Protocol


class SchemaMapping(Protocol):
    """A·B 쿼리의 테이블·컬럼 동일성 판정 프로토콜"""

    def same_table(self, table_a: str, table_b: str) -> bool: ...

    def same_column(self, col_a: str, col_b: str, *, table_a: str = "", table_b: str = "") -> bool: ...


class IdentitySchemaMapping:
    """이름이 같으면 동일하다고 판정하는 기본 매퍼.

    식별자는 대소문자 무시. 스키마 prefix(owner.table)는 무시하고
    테이블명만 비교한다.
    """

    @staticmethod
    def _strip_schema(name: str) -> str:
        return name.rsplit(".", 1)[-1].lower().strip('"').strip("`")

    def same_table(self, table_a: str, table_b: str) -> bool:
        return self._strip_schema(table_a) == self._strip_schema(table_b)

    def same_column(
        self, col_a: str, col_b: str, *, table_a: str = "", table_b: str = ""
    ) -> bool:
        return self._strip_schema(col_a) == self._strip_schema(col_b)
