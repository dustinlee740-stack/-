"""샘플 운영계 스키마 CSV 생성 (data/op_schema.csv).

규칙:
- an_schema.csv의 op_column이 채워진 행 = '운영계에 있고 이관된' 컬럼 → 그대로 운영계 모집단에 포함.
  (op_column이 비면 분석계 파생컬럼이므로 운영계 모집단에 없음 → 대시보드에서 '파생'으로 분류)
- 그 위에 데모용으로 '미이관' 컬럼을 주입: 개인정보(PII) 일부 + 일반 미이관 일부 + 전체 미이관 테이블 일부.
- 모든 주입은 이름 해시 기반 → 재현 가능(고정 seed 불필요, 결정론적).
"""
from __future__ import annotations

from common import DATA_DIR, read_csv, write_csv, norm
from sample_common import (PII_COLUMNS, EXTRA_COLUMNS, bucket, guess_type, guess_desc)

OUT_FIELDS = ["component", "table", "column", "data_type",
              "column_desc", "table_desc", "is_pii"]


def main() -> None:
    an = read_csv(DATA_DIR / "an_schema.csv")
    if not an:
        raise SystemExit("data/an_schema.csv 없음 — 먼저 parse_ttp_sql.py 실행")

    seen = set()           # (component, table, column) 중복 방지
    rows = []
    tables = {}            # (comp, table) -> 등장 순서 유지

    def add(comp, table, col, dtype, desc, is_pii):
        key = (norm(comp), norm(table), norm(col))
        if key in seen:
            return
        seen.add(key)
        rows.append({
            "component": comp, "table": table, "column": col,
            "data_type": dtype, "column_desc": desc,
            "table_desc": f"{table} 테이블", "is_pii": is_pii,
        })

    # 1) 이관된 컬럼 (an_schema의 op_column 채워진 것)
    for r in an:
        comp, table, col = r.get("op_component", ""), r.get("op_table", ""), r.get("op_column", "")
        if not col.strip():
            continue  # 파생컬럼 → 운영계 모집단에 없음
        tables.setdefault((comp, table), True)
        add(comp, table, col, guess_type(col), guess_desc(col), "N")

    # 2) 미이관 컬럼 주입 (각 테이블에 결정론적으로)
    for (comp, table) in list(tables):
        sig = f"{comp}.{table}"
        # 2a) PII 컬럼: 테이블의 ~40%에 1~2개
        if bucket(sig + "#pii", 5) < 2:
            n_pii = 1 + bucket(sig + "#pii_n", 2)
            for i in range(n_pii):
                pcol, ptype, pdesc = PII_COLUMNS[bucket(sig + f"#pii{i}", len(PII_COLUMNS))]
                add(comp, table, pcol, ptype, pdesc, "Y")
        # 2b) 일반 미이관 컬럼: 테이블의 ~50%에 1~2개
        if bucket(sig + "#ext", 4) < 2:
            n_ext = 1 + bucket(sig + "#ext_n", 2)
            for i in range(n_ext):
                ecol, etype, edesc = EXTRA_COLUMNS[bucket(sig + f"#ext{i}", len(EXTRA_COLUMNS))]
                add(comp, table, ecol, etype, edesc, "N")

    # 3) 전체 미이관 테이블 주입 (컴포넌트별 1개씩, 일부 컴포넌트)
    comps = sorted({c for (c, _t) in tables})
    for comp in comps:
        if bucket(comp + "#wholetable", 3) != 0:
            continue
        t = "TB_LEGACY_UNMIGRATED"
        for col, dtype, desc in EXTRA_COLUMNS[:3]:
            add(comp, t, col, dtype, desc, "N")

    write_csv(DATA_DIR / "op_schema.csv", OUT_FIELDS, rows)
    n_pii = sum(1 for r in rows if r["is_pii"] == "Y")
    n_tables = len({(r["component"], r["table"]) for r in rows})
    print(f"[gen_sample_op_schema] 운영계 컬럼 {len(rows)} (PII {n_pii}) · 테이블 {n_tables} "
          f"→ {DATA_DIR / 'op_schema.csv'}")


if __name__ == "__main__":
    main()
