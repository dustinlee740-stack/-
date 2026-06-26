"""스키마 매핑 인터페이스

운영계(Oracle) ↔ 분석계(Hive) 테이블·컬럼 매핑 프로토콜 + No.3 매핑 구현.

두 가지 메커니즘을 제공한다:
1. `SchemaMapping` Protocol / `IdentitySchemaMapping` — 규칙 엔진의 same_table/same_column 주입점.
2. `OpAnMap` + `translate_op_to_an` — 운영(op) 식별자를 분석(an) 명으로 **AST 단계에서 번역**.
   비교 직전 A(운영) 쿼리를 분석 네임스페이스로 번역하면 모든 절(FROM/JOIN/WHERE/GROUP BY/
   SELECT)이 동일 네임스페이스가 되어, 기존 문자열 비교가 그대로 동작한다.

매핑 데이터는 `query_diff/data/op_an_map.json`(build_op_an_map.py 산출물,
an_schema.csv + op_schema.csv 병합)에서 로드한다. 식별자는 전부 대문자 정규화.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import sqlglot
from sqlglot import exp

_DEFAULT_MAP_PATH = Path(__file__).resolve().parent.parent / "data" / "op_an_map.json"


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


# --- op→an 매핑 데이터 + AST 번역 ---

def _u(s: str) -> str:
    return (s or "").strip().upper()


class OpAnMap:
    """운영(op)→분석(an) 컬럼/테이블 매핑. op_an_map.json 로드본."""

    def __init__(
        self,
        columns: dict[str, dict[str, str]],
        tables: dict[str, str],
        op_catalog: dict[str, list[str]],
        an_derived: dict[str, str] | None = None,
    ) -> None:
        self.columns = columns          # "OP_TABLE.OP_COL" -> {an_table, an_col, source_expr}
        self.tables = tables            # OP_TABLE -> AN_TABLE
        self.op_catalog = op_catalog    # OP_TABLE -> [OP_COL, ...]
        self.an_derived = an_derived or {}

    @classmethod
    def from_dict(cls, d: dict) -> "OpAnMap":
        return cls(
            columns=d.get("columns", {}),
            tables=d.get("tables", {}),
            op_catalog=d.get("op_catalog", {}),
            an_derived=d.get("an_derived", {}),
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "OpAnMap":
        p = Path(path) if path else _DEFAULT_MAP_PATH
        return cls.from_dict(json.loads(p.read_text(encoding="utf-8")))

    def translate_table(self, op_table: str) -> str:
        """운영 테이블 → 분석 테이블. 매핑 없으면 원본(identity)."""
        return self.tables.get(_u(op_table), op_table)

    def translate_column(self, op_table: str, op_col: str) -> str:
        """운영 컬럼 → 분석 컬럼. 매핑 없으면 원본(identity).

        op_table 에 명시 매핑이 없어도, op_catalog 에 존재하면(표준화 완료=운영=분석)
        원본을 그대로 둔다. 둘 다 없으면 역시 원본(비파괴)."""
        ent = self.columns.get(f"{_u(op_table)}.{_u(op_col)}")
        if ent and ent.get("an_col"):
            return ent["an_col"]
        return op_col


@lru_cache(maxsize=4)
def load_op_an_map(path: str | None = None) -> OpAnMap:
    """op_an_map.json 을 1회 로드해 캐싱."""
    return OpAnMap.load(path)


def translate_op_to_an(
    tree: exp.Expression, op_an: OpAnMap
) -> tuple[exp.Expression, dict[str, str]]:
    """AST 의 운영(op) 테이블·컬럼 식별자를 분석(an) 명으로 번역한 **사본**을 반환.

    반환: (번역된 트리, 역매핑) — 역매핑은 `an_col(소문자) → op_col(소문자)` 로,
    차이 표시 시 분석명을 사용자가 작성한 원본 운영명으로 되돌리는 데 쓴다.

    - 컬럼: 소속 테이블을 alias 맵으로 해소해 (op_table, op_col) → an_col 치환.
      한정자(table.) 없는 컬럼은 스코프에 테이블이 1개일 때만 해소(모호하면 보존).
    - **테이블명은 번역하지 않는다(identity).** 분석 쿼리는 표준 물리명(KOD_DC_BNF/IAS_MC)이
      아니라 운영과 동일한 뷰/논리명(service_discount/tb_all_merchant)을 그대로 쓰므로,
      테이블명을 바꾸면 오히려 매칭이 깨진다. 컬럼만 분석명으로 맞춘다.
    - 매핑에 없는 식별자는 **그대로 둔다**(비파괴). 분석쪽 식별자/CTE 파생 컬럼에 안전.
    """
    tree = tree.copy()
    rename: dict[str, str] = {}  # an_col(lower) → op_col(lower), 표시 역변환용

    alias_to_table: dict[str, str] = {}
    base_tables: list[str] = []
    for t in tree.find_all(exp.Table):
        tname = _u(t.name)
        alias_to_table.setdefault(tname, tname)
        alias = t.alias
        if alias:
            alias_to_table[_u(alias)] = tname
        base_tables.append(tname)
    distinct_tables = set(base_tables)

    # 컬럼만 번역 (테이블명은 identity 유지)
    for col in tree.find_all(exp.Column):
        tref = _u(col.table) if col.table else ""
        if tref:
            op_table = alias_to_table.get(tref, tref)
        elif len(distinct_tables) == 1:
            op_table = next(iter(distinct_tables))
        else:
            continue
        op_col = _u(col.name)
        an_col = op_an.translate_column(op_table, op_col)
        if _u(an_col) != op_col:
            col.set("this", exp.to_identifier(an_col))
            rename.setdefault(an_col.lower(), op_col.lower())

    return tree, rename
