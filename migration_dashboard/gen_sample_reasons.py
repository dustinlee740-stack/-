"""샘플 미이관 사유 매핑 CSV 생성 (data/reasons.csv).

op_schema와 an_schema를 대조해 '미이관' 컬럼을 찾고, 결정론적으로 사유를 부여한다:
- 개인정보(is_pii=Y) → PII_EXCLUDED (컬럼 단위)
- 전체 미이관 테이블 → NO_REQUEST (column 빈칸 = 테이블 와일드카드). 단 그 안의 PII는 컬럼 행으로 override
- 부분 미이관 테이블의 나머지 컬럼 → 해시 버킷으로 UNFIT / PENDING / ETC / (일부는 무부여=사유미지정)

실데이터에서는 이 파일을 사용자가 직접 제공한다. 여기선 데모용 자동 생성.
"""
from __future__ import annotations

from common import DATA_DIR, read_csv, write_csv, norm, truthy_pii

OUT_FIELDS = ["component", "table", "column", "reason_code", "reason_note"]


def bucket(name: str, n: int) -> int:
    import hashlib
    return int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16) % n


def main() -> None:
    op = read_csv(DATA_DIR / "op_schema.csv")
    an = read_csv(DATA_DIR / "an_schema.csv")
    if not op:
        raise SystemExit("data/op_schema.csv 없음 — 먼저 gen_sample_op_schema.py 실행")

    migrated = {(norm(r["op_component"]), norm(r["op_table"]), norm(r["op_column"]))
                for r in an if r.get("op_column", "").strip()}

    # 테이블별 미이관/전체 카운트
    by_table: dict[tuple, dict] = {}
    for r in op:
        comp, table, col = r["component"], r["table"], r["column"]
        key = (norm(comp), norm(table))
        t = by_table.setdefault(key, {"comp": comp, "table": table, "total": 0,
                                      "unmig": [], "all_cols": []})
        t["total"] += 1
        is_mig = (norm(comp), norm(table), norm(col)) in migrated
        t["all_cols"].append(col)
        if not is_mig:
            t["unmig"].append(r)

    rows = []
    for key, t in sorted(by_table.items()):
        comp, table, unmig = t["comp"], t["table"], t["unmig"]
        if not unmig:
            continue
        whole = len(unmig) == t["total"]  # 테이블 전체가 미이관인가
        if whole:
            # 테이블 와일드카드 NO_REQUEST 1행
            rows.append({"component": comp, "table": table, "column": "",
                         "reason_code": "NO_REQUEST",
                         "reason_note": "이관 요청에 포함되지 않은 테이블"})
            # PII 컬럼은 override (컬럼 행 PII_EXCLUDED)
            for r in unmig:
                if truthy_pii(r.get("is_pii")):
                    rows.append({"component": comp, "table": table, "column": r["column"],
                                 "reason_code": "PII_EXCLUDED",
                                 "reason_note": "개인정보 — 이관 대상 제외"})
            continue
        # 부분 미이관: 컬럼별 사유
        for r in unmig:
            col = r["column"]
            if truthy_pii(r.get("is_pii")):
                rows.append({"component": comp, "table": table, "column": col,
                             "reason_code": "PII_EXCLUDED",
                             "reason_note": "개인정보 — 이관 대상 제외"})
                continue
            b = bucket(f"{comp}.{table}.{col}", 4)
            if b == 0:
                rows.append({"component": comp, "table": table, "column": col,
                             "reason_code": "UNFIT", "reason_note": "분석 요건에 부적합한 컬럼"})
            elif b == 1:
                rows.append({"component": comp, "table": table, "column": col,
                             "reason_code": "PENDING", "reason_note": "차기 이관 예정"})
            elif b == 2:
                rows.append({"component": comp, "table": table, "column": col,
                             "reason_code": "ETC", "reason_note": "운영계 전용 내부 항목"})
            # b == 3 → 사유 미부여(대시보드에서 '사유미지정'으로 노출)

    write_csv(DATA_DIR / "reasons.csv", OUT_FIELDS, rows)
    from collections import Counter
    cnt = Counter(r["reason_code"] for r in rows)
    print(f"[gen_sample_reasons] 사유 {len(rows)}행 → {DATA_DIR / 'reasons.csv'}  {dict(cnt)}")


if __name__ == "__main__":
    main()
