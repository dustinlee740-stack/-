"""
Deterministic validator for impact-analysis artifacts in D:/da/pilot.

Checks (no LLM, no scoring):
  1) impact_<basename>.md headers — analysis time is ISO (no '<...>' placeholder)
  2) Anchors — every `components.md#<slug>` link resolves to a slug of a real
     component Name (slugify() from xlsx_to_md.py, components.xlsx as truth)
  3) impact_log.jsonl — every line is valid JSON + has required keys + ISO ts
  4) Consistency keyword warnings — e.g., outdated KFDS catalog phrase in
     current artifacts (warning only, does not fail)

Exit code 0 on pass, 1 on any non-warning error.

Usage:
    python validate_impact.py [--dir D:\\da\\pilot]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

from xlsx_to_md import pick, slugify, COL_MAJOR, COL_MID, COL_MINOR  # noqa: F401

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\da\pilot")
XLSX = ROOT / "components.xlsx"
LOG = ROOT / "impact_log.jsonl"

ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")
ANCHOR_RE = re.compile(r"\(components\.md#([^\)\s]+)\)")

REQUIRED_KEYS = ("ts", "requirement_file", "summary")
NEW_ENTRY_KEYS = ({"derived_categories", "impacted"}, {"derived_categories", "impacted_primary", "impacted_secondary"})
CONTINUATION_KEYS = ("correction_of", "reverification_of", "revision_type")

WARNING_PATTERNS = [
    (re.compile(r"A-safe\s*대체"), "KFDS 카탈로그 어휘 'A-safe 대체' 사용 — outdated 표현 (CLAUDE.md 도메인 메모 참조)"),
    (re.compile(r"환불.{0,10}원장.{0,5}IAS"), "환불 원장을 IAS로 표기 의심 — 환불 원장은 RS"),
]


def _build_slug_map(df: pd.DataFrame) -> dict[str, str]:
    return {slugify(str(n)): str(n).strip() for n in df["Name"]}


def check_md(md_path: Path, slug_to_name: dict[str, str]) -> list[str]:
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")

    m = re.search(r"분석 시각:\s*(\S+)", text)
    if not m:
        errors.append(f"{md_path.name}: 헤더 '분석 시각' 라인 없음")
    else:
        time_val = m.group(1)
        if PLACEHOLDER_RE.search(time_val):
            errors.append(f"{md_path.name}: 분석 시각에 placeholder 잔존 ({time_val})")
        elif not ISO_RE.match(time_val):
            errors.append(f"{md_path.name}: 분석 시각 ISO 형식 아님 ({time_val})")

    unresolved = sorted({m.group(1) for m in ANCHOR_RE.finditer(text) if m.group(1) not in slug_to_name})
    for slug in unresolved:
        errors.append(f"{md_path.name}: 미해결 anchor 'components.md#{slug}'")

    for pat, msg in WARNING_PATTERNS:
        if pat.search(text):
            errors.append(f"WARN {md_path.name}: {msg}")

    return errors


def check_log() -> list[str]:
    errors: list[str] = []
    if not LOG.exists():
        return [f"{LOG.name}: 파일 없음"]
    for i, line in enumerate(LOG.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"{LOG.name}:line{i}: JSON 파싱 실패 — {e}")
            continue
        missing = [k for k in REQUIRED_KEYS if k not in obj]
        if missing:
            errors.append(f"{LOG.name}:line{i}: 필수 키 누락 {missing}")
        keys = set(obj.keys())
        is_new = any(needed.issubset(keys) for needed in NEW_ENTRY_KEYS)
        is_continuation = any(k in keys for k in CONTINUATION_KEYS)
        if not (is_new or is_continuation):
            errors.append(
                f"{LOG.name}:line{i}: 신규 항목 키 세트(derived_categories+impacted[_primary/_secondary]) 또는 정정·재검증 키(correction_of/reverification_of/revision_type) 중 하나 필요"
            )
        ts = obj.get("ts", "")
        if not ISO_RE.match(ts):
            errors.append(f"{LOG.name}:line{i}: ts ISO 형식 아님 ({ts})")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate impact-analysis artifacts in D:/da/pilot.")
    ap.add_argument("--dir", type=Path, default=ROOT)
    args = ap.parse_args()
    root: Path = args.dir

    df = pd.read_excel(XLSX).dropna(subset=["Name"]).reset_index(drop=True)
    slug_to_name = _build_slug_map(df)

    md_files = sorted(p for p in root.glob("impact_*.md") if p.name != "impact_context.md")

    findings: list[str] = []
    for md in md_files:
        findings.extend(check_md(md, slug_to_name))
    findings.extend(check_log())

    errors = [f for f in findings if not f.startswith("WARN")]
    warnings = [f for f in findings if f.startswith("WARN")]

    for w in warnings:
        print(w)
    for e in errors:
        print(f"ERROR: {e}")

    if not errors:
        print(f"OK: {len(md_files)} md + {LOG.name} valid ({len(warnings)} warnings)")
        return 0
    print(f"FAIL: {len(errors)} errors, {len(warnings)} warnings")
    return 1


if __name__ == "__main__":
    sys.exit(main())
