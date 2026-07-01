"""공통 헬퍼 — 정규화 / CSV·xlsx 읽기 / 상태 판정 / 사유 코드.

이 워크스페이스는 격리되어 있다(CLAUDE.md). 다른 폴더의 코드를 import 하지 않으며
필요한 로직(xlsx 읽기 등)은 모두 여기에 자체 구현한다. 외부 의존성 없음(표준 라이브러리만).
"""
from __future__ import annotations

import csv
import io
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

# --- 미이관 사유 코드 (README와 일치, 확정 5종) -----------------------------
REASON_LABELS = {
    "NO_REQUEST": "이관 요청 없음",
    "PII_EXCLUDED": "개인정보로 이관 제외",
    "UNFIT": "요청 부적합",
    "PENDING": "이관 예정",
    "ETC": "기타",
}
# 이관율 분모에서 제외되는("이관 대상 아님") 사유
EXCLUDING_REASONS = {"NO_REQUEST", "PII_EXCLUDED", "UNFIT"}

# 컬럼 상태
ST_MIGRATED = "이관"
ST_NOT_MIGRATED = "미이관"
ST_EXCLUDED = "제외"
ST_AN_DERIVED = "파생컬럼"
ST_AN_ORPHAN = "운영계미등재"

# 컴포넌트/테이블 상태 배지
BADGE_DONE = "완료"
BADGE_PARTIAL = "부분"
BADGE_NONE = "미이관"
BADGE_NA = "대상아님"


def norm(s) -> str:
    """조인 키 정규화: trim + 대문자. None/숫자도 안전 처리."""
    if s is None:
        return ""
    return str(s).strip().upper()


def truthy_pii(v) -> bool:
    return norm(v) in {"Y", "YES", "TRUE", "1"}


def read_csv(path: Path) -> list[dict]:
    """UTF-8(BOM 허용) CSV를 dict 리스트로. 헤더는 trim."""
    path = Path(path)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames:
            reader.fieldnames = [h.strip() for h in reader.fieldnames]
        return [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def badge_for(migrated: int, denom: int) -> str:
    """이관/분모 카운트로 상태 배지 산출."""
    if denom <= 0:
        return BADGE_NA
    if migrated >= denom:
        return BADGE_DONE
    if migrated <= 0:
        return BADGE_NONE
    return BADGE_PARTIAL


def rate_for(migrated: int, denom: int) -> float:
    """이관율(0~100). 분모 0이면 0."""
    return round(migrated * 100.0 / denom, 1) if denom > 0 else 0.0


# --- components.xlsx 직접 읽기 (openpyxl 없이 표준 라이브러리로) --------------
# .xlsx = zip(xml). 첫 시트의 행/열을 추출한다. 컴포넌트 카탈로그 변환 전용.
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _col_to_idx(ref: str) -> int:
    """'B3' 같은 셀 참조 → 0-based 열 인덱스."""
    letters = "".join(c for c in ref if c.isalpha())
    idx = 0
    for ch in letters:
        idx = idx * 26 + (ord(ch.upper()) - ord("A") + 1)
    return idx - 1


def read_xlsx_first_sheet(path: Path) -> list[list[str]]:
    """xlsx 첫 시트를 2차원 문자열 리스트로 반환(빈 셀은 '')."""
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            sroot = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in sroot.findall("m:si", _NS):
                # <si> 안의 모든 <t> 텍스트 이어붙임 (rich text 대응)
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
        # 첫 시트 경로 확인 (보통 sheet1.xml)
        sheet_name = "xl/worksheets/sheet1.xml"
        if sheet_name not in z.namelist():
            sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
            sheet_name = sheets[0]
        root = ET.fromstring(z.read(sheet_name))
        rows = []
        for row in root.iter("{%s}row" % _NS["m"]):
            cells = {}
            maxc = 0
            for c in row.findall("m:c", _NS):
                ref = c.get("r", "")
                ci = _col_to_idx(ref) if ref else len(cells)
                t = c.get("t")
                v = c.find("m:v", _NS)
                if t == "s" and v is not None:  # shared string
                    val = shared[int(v.text)] if v.text else ""
                elif t == "inlineStr":
                    isn = c.find("m:is", _NS)
                    val = "".join(x.text or "" for x in isn.iter("{%s}t" % _NS["m"])) if isn is not None else ""
                else:
                    val = v.text if v is not None and v.text is not None else ""
                cells[ci] = val
                maxc = max(maxc, ci)
            rows.append([cells.get(i, "") for i in range(maxc + 1)])
        return rows
