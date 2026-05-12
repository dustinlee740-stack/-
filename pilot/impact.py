"""
Generate inference material for the impact-analysis workflow.

Reads D:/da/pilot/components.xlsx and writes D:/da/pilot/impact_context.md,
a compact catalog (category tree + one-line summary per component) that
Claude Code consumes when analyzing a requirement file.

This script does NOT call any LLM and does NOT score components.
Reasoning (category derivation + comparison) is done by Claude Code in a
follow-up step, with this material as one of its inputs.

Usage:
    python impact.py
"""

import datetime as dt
import re
import unicodedata
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from xlsx_to_md import COL_MAJOR, COL_MID, COL_MINOR, pick

XLSX = Path(r"D:\da\pilot\components.xlsx")
OUT = Path(r"D:\da\pilot\impact_context.md")

SUMMARY_MAX_CHARS = 100


def one_line_summary(text: str) -> str:
    if not isinstance(text, str):
        return ""
    s = unicodedata.normalize("NFKC", text).strip()
    s = re.sub(r"\s+", " ", s)
    if len(s) > SUMMARY_MAX_CHARS:
        s = s[: SUMMARY_MAX_CHARS - 1].rstrip() + "…"
    return s


def main() -> None:
    df = pd.read_excel(XLSX)
    cmajor = pick(df, COL_MAJOR)
    cmid = pick(df, COL_MID)
    cminor = pick(df, COL_MINOR)
    df = df.dropna(subset=["Name"]).reset_index(drop=True)
    # Case-insensitive sort for English component names (Hangul unaffected by upper()).
    df = df.sort_values(by="Name", key=lambda s: s.str.upper(), kind="stable").reset_index(drop=True)

    grouped: "OrderedDict[str, OrderedDict[str, OrderedDict[str, list]]]" = OrderedDict()
    for _, r in df.iterrows():
        major = str(r[cmajor]) if pd.notna(r[cmajor]) else "(미분류)"
        mid = str(r[cmid]) if pd.notna(r[cmid]) else "(미분류)"
        minor = str(r[cminor]) if pd.notna(r[cminor]) else "(미분류)"
        grouped.setdefault(major, OrderedDict()).setdefault(mid, OrderedDict()).setdefault(minor, []).append(r)

    ts = dt.datetime.fromtimestamp(XLSX.stat().st_mtime).isoformat(timespec="seconds")
    lines: list[str] = []
    lines.append("# 영향 분석 추론 머티리얼 (impact_context)")
    lines.append("")
    lines.append(f"- 출처 갱신 시각: {ts}")
    lines.append(f"- 출처: `{XLSX}` (총 {len(df)}개 컴포넌트)")
    lines.append(f"- 대분류 {df[cmajor].nunique()} · 중분류 {df[cmid].nunique()} · 소분류 {df[cminor].nunique()}")
    lines.append("- 용도: 영향 분석 워크플로우의 1단계(분류 도출) · 2단계(비교·추론) 단계에서 AI 추론 도구가 참조하는 압축 카탈로그")
    lines.append("- 컴포넌트 전문 설명은 `components.md`에서 확인")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 분류 트리 + 한 줄 요약")
    lines.append("")
    for major, mids in grouped.items():
        major_total = sum(len(rows) for minors in mids.values() for rows in minors.values())
        lines.append(f"### {major} ({major_total}개)")
        lines.append("")
        for mid, minors in mids.items():
            mid_total = sum(len(rows) for rows in minors.values())
            lines.append(f"- **{mid}** ({mid_total}개)")
            for minor, rows in minors.items():
                lines.append(f"  - _{minor}_ ({len(rows)}개)")
                for r in rows:
                    name = str(r["Name"])
                    full = str(r["Full Name"]).strip() if pd.notna(r["Full Name"]) else ""
                    kr = one_line_summary(str(r["Korean Description"])) if pd.notna(r["Korean Description"]) else ""
                    head = f"**{name}**" + (f" — {full}" if full else "")
                    summary = f" · {kr}" if kr else ""
                    lines.append(f"    - {head}{summary}")
            lines.append("")
        lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"OK: {len(df)} components -> {OUT}")


if __name__ == "__main__":
    main()
