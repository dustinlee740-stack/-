"""op↔an 스키마 매핑 아티팩트 빌드 스크립트.

migration_dashboard 의 두 로컬 CSV 를 병합해 비교 엔진이 읽을 `op_an_map.json` 을 만든다.

- an_schema.csv  : 운영(op)→분석(an) 컬럼 리네임 매핑 + 변환식(source_expr).
                   meta3.table_col_mapping 의 로컬 등가물(검증 보고서에서 일치 확인).
- op_schema.csv  : 운영 물리 카탈로그(컴포넌트/테이블/컬럼). identity 판정용
                   (= meta3.v_oltp_table_columns 의 로컬 등가물).

산출물 `op_an_map.json` 구조:
  {
    "columns": { "OP_TABLE.OP_COL": {"an_table","an_col","source_expr"}, ... },  # 리네임
    "tables":  { "OP_TABLE": "AN_TABLE", ... },                                   # 테이블 매핑
    "op_catalog": { "OP_TABLE": ["OP_COL", ...], ... },                           # identity 후보
    "an_derived": { "AN_TABLE.AN_COL": "source_expr", ... },                      # op 대응 없는 분석 컬럼
    "meta": {...}
  }

식별자는 전부 **대문자**로 정규화한다(meta3 조회 규칙과 동일).
재실행: `python build_op_an_map.py` (로컬 파일만 읽으므로 DB/네트워크 불필요).
"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent
# 기본 입력 경로(로컬). 환경변수로 재정의 가능.
_DASH_DATA = Path(
    os.environ.get("MIGRATION_DASHBOARD_DATA", r"D:\da\migration_dashboard\data")
)
AN_SCHEMA_CSV = _DASH_DATA / "an_schema.csv"
OP_SCHEMA_CSV = _DASH_DATA / "op_schema.csv"
META3_OVERRIDES = _HERE / "meta3_overrides.json"
OUT_JSON = _HERE / "op_an_map.json"


def _u(s: str | None) -> str:
    return (s or "").strip().upper()


def _read_csv(path: Path) -> list[dict[str, str]]:
    # utf-8-sig 로 BOM 제거
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _load_from_meta3(dsn: str) -> tuple[dict[str, str], dict[str, list[str]]]:
    """META3_DSN 으로 PostgreSQL 직결, table_col_mapping 전체 + v_oltp 카탈로그 적재.

    반환: (columns_an: "OP_TABLE.OP_COL"->an_col, op_catalog: OP_TABLE->[OP_COL,...]).
    1:N 모호성: 한 (op_table,op_col)에 tobe 여러 개면 identity(tobe==op_col) 우선,
    아니면 1개일 때만 채택, 진짜 다수면 제외(=identity 유지).
    psycopg 는 지연 import.
    """
    from collections import defaultdict

    try:
        import psycopg2 as _pg  # type: ignore
    except Exception:
        try:
            import psycopg as _pg  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "META3_DSN 적재에는 psycopg2(-binary) 또는 psycopg 가 필요합니다. "
                "pip install psycopg2-binary"
            ) from e

    grp: dict[tuple[str, str], set[str]] = defaultdict(set)
    op_catalog: dict[str, list[str]] = {}
    conn = _pg.connect(dsn)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT upper(asis_table_id), upper(asis_col_id), upper(tobe_col_id) "
            "FROM meta3.table_col_mapping "
            "WHERE asis_table_id<>'' AND asis_col_id<>'' AND tobe_col_id<>''"
        )
        for ot, oc, tc in cur.fetchall():
            if ot and oc and tc:
                grp[(ot, oc)].add(tc)
        cur.execute(
            "SELECT upper(tbl_id), upper(col_id) FROM meta3.v_oltp_table_columns "
            "WHERE tbl_id<>'' AND col_id<>''"
        )
        for t, c in cur.fetchall():
            if t and c:
                lst = op_catalog.setdefault(t, [])
                if c not in lst:
                    lst.append(c)
    finally:
        conn.close()

    cols: dict[str, str] = {}
    for (ot, oc), tcs in grp.items():
        if oc in tcs:
            an = oc  # identity 우선
        elif len(tcs) == 1:
            an = next(iter(tcs))
        else:
            continue  # 모호 → identity 유지
        cols[f"{ot}.{oc}"] = an
    return cols, op_catalog


def build() -> dict:
    an_rows = _read_csv(AN_SCHEMA_CSV)
    op_rows = _read_csv(OP_SCHEMA_CSV)

    columns: dict[str, dict[str, str]] = {}
    tables: dict[str, str] = {}
    an_derived: dict[str, str] = {}

    for r in an_rows:
        op_table = _u(r.get("op_table"))
        op_col = _u(r.get("op_column"))
        an_table = _u(r.get("an_table"))
        an_col = _u(r.get("an_column"))
        src = (r.get("source_expr") or "").strip()

        if an_table and op_table:
            tables.setdefault(op_table, an_table)

        if op_table and op_col and an_col:
            key = f"{op_table}.{op_col}"
            # 1:N(드묾)이면 첫 매핑 유지
            columns.setdefault(
                key, {"an_table": an_table, "an_col": an_col, "source_expr": src}
            )
        elif an_table and an_col and not op_col:
            # 운영 대응 없는 분석 파생 컬럼 (B에만 존재 후보)
            an_derived.setdefault(f"{an_table}.{an_col}", src)

    op_catalog: dict[str, list[str]] = {}
    for r in op_rows:
        t = _u(r.get("table"))
        c = _u(r.get("column"))
        if t and c:
            op_catalog.setdefault(t, [])
            if c not in op_catalog[t]:
                op_catalog[t].append(c)

    # meta3 전체 직결 덤프(권위) — META3_DSN 있으면 an_schema 위에 덮어쓴다. 영구 커버리지.
    meta3_dump_count = 0
    dsn = os.environ.get("META3_DSN")
    if dsn:
        try:
            m3_cols, m3_catalog = _load_from_meta3(dsn)
            for key, an_col in m3_cols.items():
                op_table = key.split(".", 1)[0]
                prev = columns.get(key, {})
                columns[key] = {
                    "an_table": prev.get("an_table") or op_table,
                    "an_col": an_col,
                    "source_expr": prev.get("source_expr", ""),
                }
            for t, cs in m3_catalog.items():
                lst = op_catalog.setdefault(t, [])
                for c in cs:
                    if c not in lst:
                        lst.append(c)
            meta3_dump_count = len(m3_cols)
        except Exception as e:
            print(f"[warn] META3_DSN 적재 실패 — overrides+an_schema 로 진행: {e}")

    # meta3 권위 오버라이드 — an_schema/덤프 값을 덮어쓴다(수동 최종).
    override_count = 0
    if META3_OVERRIDES.exists():
        ov = json.loads(META3_OVERRIDES.read_text(encoding="utf-8"))
        for key, an_col in (ov.get("columns") or {}).items():
            key = _u(key)
            op_table = key.split(".", 1)[0] if "." in key else ""
            prev = columns.get(key, {})
            columns[key] = {
                "an_table": prev.get("an_table") or op_table,  # 테이블명은 번역 안 함(identity)
                "an_col": _u(an_col),
                "source_expr": prev.get("source_expr", ""),
            }
            override_count += 1

    return {
        "columns": columns,
        "tables": tables,
        "op_catalog": op_catalog,
        "an_derived": an_derived,
        "meta": {
            "an_schema_rows": len(an_rows),
            "op_schema_rows": len(op_rows),
            "column_mappings": len(columns),
            "table_mappings": len(tables),
            "op_catalog_tables": len(op_catalog),
            "an_derived_cols": len(an_derived),
            "meta3_overrides_applied": override_count,
            "meta3_dump_columns": meta3_dump_count,
            "source": (
                "META3_DSN 전체덤프(권위) > meta3_overrides.json > an_schema.csv + op_schema.csv"
                if meta3_dump_count
                else "meta3_overrides.json > an_schema.csv + op_schema.csv (META3_DSN 미설정)"
            ),
        },
    }


def main() -> None:
    artifact = build()
    OUT_JSON.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    m = artifact["meta"]
    print(f"wrote {OUT_JSON}")
    print(
        f"  columns={m['column_mappings']} tables={m['table_mappings']} "
        f"op_catalog_tables={m['op_catalog_tables']} an_derived={m['an_derived_cols']}"
    )


if __name__ == "__main__":
    main()
