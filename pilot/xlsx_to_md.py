"""
Convert D:/da/pilot/components.xlsx to D:/da/pilot/components.md.
Keeps the .xlsx untouched. Re-runnable.

Input columns required:
  - Name, Full Name, Korean Description, English Description (exact, English headers)
  - 대분류 / 중분류 / 소분류 (Korean or English headers, resolved via pick())

Output structure:
  - Header + summary
  - TOC grouped by 대분류 > 중분류 (links to component sections)
  - One section per component, sorted alphabetically by Name
"""

import re
import pandas as pd
import unicodedata
from collections import OrderedDict
from pathlib import Path

_HERE = Path(__file__).parent
XLSX = _HERE / "components.xlsx"
OUT = _HERE / "components.md"

# Column names tolerant to either Korean or English headers
COL_MAJOR = ("Major Categories", "대분류")
COL_MID = ("Medium Category", "중분류")
COL_MINOR = ("Subcategories", "소분류")


def pick(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"None of {candidates} found in columns: {df.columns.tolist()}")


def slugify(name: str) -> str:
    """GitHub-like Markdown anchor slug for headings (Unicode-friendly)."""
    s = unicodedata.normalize("NFKC", str(name)).lower().strip()
    # Drop characters disallowed in anchors except letters, digits, hyphen, underscore, hangul.
    out = []
    for ch in s:
        if ch.isalnum() or ch in "-_" or "가" <= ch <= "힯":
            out.append(ch)
        elif ch.isspace():
            out.append("-")
        # else: drop (parens, slashes, dots, etc.)
    slug = "".join(out)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "section"


def main():
    df = pd.read_excel(XLSX)
    cmajor = pick(df, COL_MAJOR)
    cmid = pick(df, COL_MID)
    cminor = pick(df, COL_MINOR)
    for c in ("Name", "Full Name", "Korean Description", "English Description"):
        if c not in df.columns:
            raise KeyError(f"Required column missing: {c!r} (got {df.columns.tolist()})")
    df = df.dropna(subset=["Name"]).reset_index(drop=True)
    # Case-insensitive sort for English component names (Hangul unaffected by upper()).
    df = df.sort_values(by="Name", key=lambda s: s.str.upper(), kind="stable").reset_index(drop=True)

    # Group by major > mid (preserve a stable ordering by first appearance)
    grouped: "OrderedDict[str, OrderedDict[str, list]]" = OrderedDict()
    for _, r in df.iterrows():
        major = str(r[cmajor]) if pd.notna(r[cmajor]) else "(미분류)"
        mid = str(r[cmid]) if pd.notna(r[cmid]) else "(미분류)"
        grouped.setdefault(major, OrderedDict()).setdefault(mid, []).append(r)

    lines: list[str] = []
    lines.append("# 코나카드 컴포넌트 목록")
    lines.append("")
    lines.append(f"- 총 컴포넌트 수: **{len(df)}**")
    lines.append(f"- 대분류 수: {df[cmajor].nunique()} · 중분류 수: {df[cmid].nunique()} · 소분류 수: {df[cminor].nunique()}")
    lines.append(f"- 원본: `{XLSX}` (이 md는 자동 생성, 수정 시 원본 갱신 후 재변환)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # TOC
    lines.append("## 목차")
    lines.append("")
    for major, mids in grouped.items():
        total = sum(len(v) for v in mids.values())
        lines.append(f"- **{major}** ({total})")
        for mid, rows in mids.items():
            lines.append(f"  - {mid} ({len(rows)})")
            for r in rows:
                name = str(r["Name"])
                full = str(r["Full Name"]) if pd.notna(r["Full Name"]) else ""
                anchor = slugify(name)
                label = f"{name} — {full.strip()}" if full.strip() else name
                lines.append(f"    - [{label}](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Per-component sections
    lines.append("## 컴포넌트 상세")
    lines.append("")
    for _, r in df.iterrows():
        name = str(r["Name"])
        full = str(r["Full Name"]) if pd.notna(r["Full Name"]) else ""
        major = str(r[cmajor]) if pd.notna(r[cmajor]) else ""
        mid = str(r[cmid]) if pd.notna(r[cmid]) else ""
        minor = str(r[cminor]) if pd.notna(r[cminor]) else ""
        kr = str(r["Korean Description"]) if pd.notna(r["Korean Description"]) else ""
        en = str(r["English Description"]) if pd.notna(r["English Description"]) else ""

        heading = f"### {name}"
        if full.strip():
            heading += f" — {full.strip()}"
        lines.append(heading)
        lines.append("")
        crumbs = " > ".join([x for x in (major, mid, minor) if x])
        if crumbs:
            lines.append(f"**분류**: {crumbs}")
            lines.append("")

        if kr.strip():
            lines.append("**한글 설명**")
            lines.append("")
            lines.append("```")
            lines.append(kr.rstrip())
            lines.append("```")
            lines.append("")

        if en.strip():
            lines.append("**English Description**")
            lines.append("")
            lines.append("```")
            lines.append(en.rstrip())
            lines.append("```")
            lines.append("")

        lines.append("---")
        lines.append("")

    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))

    print(f"OK: {len(df)} components -> {OUT}")


if __name__ == "__main__":
    main()
