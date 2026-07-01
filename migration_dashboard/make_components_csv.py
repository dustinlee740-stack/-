"""pilot/components.xlsx (읽기 전용 입력) → data/components.csv (이 워크스페이스 사본).

격리 원칙: pilot 코드를 import하지 않고 xlsx를 자체 파서(common.read_xlsx_first_sheet)로 읽는다.
컴포넌트 역할 설명의 원천을 이 워크스페이스 안으로 사본 복제하는 단계.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from common import BASE_DIR, DATA_DIR, read_xlsx_first_sheet, write_csv

# 출력 표준 헤더 (한글/영문 입력 헤더를 이 표준으로 정규화)
OUT_FIELDS = ["Name", "Full Name", "Korean Description", "English Description",
              "대분류", "중분류", "소분류"]

# 입력 헤더 → 출력 헤더 매핑 (한/영 모두 허용)
HEADER_MAP = {
    "name": "Name",
    "full name": "Full Name",
    "korean description": "Korean Description",
    "english description": "English Description",
    "major categories": "대분류", "대분류": "대분류",
    "medium category": "중분류", "중분류": "중분류",
    "subcategories": "소분류", "소분류": "소분류",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", default=str(BASE_DIR.parent / "pilot" / "components.xlsx"),
                    help="입력 components.xlsx 경로(읽기 전용)")
    args = ap.parse_args()

    rows2d = read_xlsx_first_sheet(Path(args.xlsx))
    if not rows2d:
        raise SystemExit(f"빈 xlsx: {args.xlsx}")

    header = [HEADER_MAP.get(h.strip().lower(), h.strip()) for h in rows2d[0]]
    out_rows = []
    for r in rows2d[1:]:
        if not any(str(c).strip() for c in r):
            continue
        rec = {header[i]: r[i] for i in range(min(len(header), len(r)))}
        if not str(rec.get("Name", "")).strip():
            continue
        out_rows.append({f: rec.get(f, "") for f in OUT_FIELDS})

    out = DATA_DIR / "components.csv"
    write_csv(out, OUT_FIELDS, out_rows)
    print(f"[make_components_csv] {len(out_rows)}개 컴포넌트 → {out}")


if __name__ == "__main__":
    main()
