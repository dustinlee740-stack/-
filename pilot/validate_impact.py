"""
Deterministic validator for impact-analysis artifacts in D:/da/pilot.

Checks (no LLM, no scoring):
  1) impact_<basename>.md headers — analysis time is ISO (no '<...>' placeholder)
  2) Anchors — every `components.md#<slug>` link resolves to a slug of a real
     component Name (slugify() from xlsx_to_md.py, components.xlsx as truth)
  3) Cross-artifact count consistency — header "영향 가능 컴포넌트 N개" matches
     unique anchor count in body "## 영향 컴포넌트" section; "flat 인덱스 행 N행"
     matches data-row count in flat-index table(s)
  4) impact_log.jsonl — every line valid JSON, required keys, ISO ts; continuation
     lines (correction/reverification) must declare at least one impacted count
  5) Consistency keyword warnings — outdated catalog phrases; quoted/code-cited
     uses are exempt via negative-lookaround

Exit code 0 on pass, 1 on any non-warning error.

Usage:
    python validate_impact.py
"""

import json
import re
import sys
from pathlib import Path

import pandas as pd

from xlsx_to_md import slugify

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
XLSX = ROOT / "components.xlsx"
LOG = ROOT / "impact_log.jsonl"

ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")
ANCHOR_RE = re.compile(r"\(components\.md#([^\)\s]+)\)")
HEADER_COUNT_RE = re.compile(r"영향 (?:가능 )?컴포넌트:\s*\*{0,2}(\d+)\*{0,2}개")
FLAT_HEADER_RE = re.compile(r"flat 인덱스 행:\s*\*{0,2}(\d+)\s*행")
SECTION_SPLIT_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)

REQUIRED_KEYS = ("ts", "requirement_file", "summary")
NEW_ENTRY_KEYS = (
    {"derived_categories", "impacted"},
    {"derived_categories", "impacted_primary", "impacted_secondary"},
)
CONTINUATION_KEYS = ("correction_of", "reverification_of", "revision_type")
CONTINUATION_COUNT_KEYS = (
    "impacted_total_count",
    "impacted_primary_count",
    "impacted_secondary_count",
)

# Quoted/code-cited contexts are exempt: ` " ' 「 」 『 』 ' ' " "
_QUOTE_CHARS = r"`\"'‘’“”「」『』"
WARNING_PATTERNS = [
    (
        re.compile(rf"(?<![{_QUOTE_CHARS}])A-safe\s*대체(?![{_QUOTE_CHARS}])"),
        "KFDS 카탈로그 어휘 'A-safe 대체' 사용 — outdated 표현 (CLAUDE.md 도메인 메모 참조)",
    ),
    (
        re.compile(r"환불.{0,10}원장.{0,5}IAS"),
        "환불 원장을 IAS로 표기 의심 — 환불 원장은 RS",
    ),
]


def _build_slug_map(df: pd.DataFrame) -> dict[str, str]:
    slug_map: dict[str, str] = {}
    for name in df["Name"]:
        n = str(name).strip()
        s = slugify(n)
        if s in slug_map and slug_map[s] != n:
            print(
                f"WARN: duplicate slug {s!r} from Names ({slug_map[s]!r}, {n!r}) — dict keeps last",
                file=sys.stderr,
            )
        slug_map[s] = n
    return slug_map


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown into top-level sections keyed by '## title'."""
    sections: dict[str, str] = {}
    parts = re.split(r"^##\s+", text, flags=re.M)
    for part in parts[1:]:
        lines = part.splitlines()
        if not lines:
            continue
        title = lines[0].strip()
        sections[title] = "\n".join(lines[1:])
    return sections


def _section_lookup(sections: dict[str, str], *needles: str) -> str:
    for title, body in sections.items():
        if all(n in title for n in needles):
            return body
    return ""


def _unique_anchors(section_text: str) -> set[str]:
    return {m.group(1) for m in ANCHOR_RE.finditer(section_text)}


def _flat_row_count(section_text: str) -> int:
    count = 0
    for line in section_text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        if re.match(r"^\|[\s\-:|]+\|?\s*$", s):
            continue
        if "components.md" not in line:
            continue
        count += 1
    return count


def check_md(md_path: Path, slug_to_name: dict[str, str]) -> list[str]:
    errors: list[str] = []
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    m_time = re.search(r"분석 시각:\s*(\S+)", text)
    if not m_time:
        errors.append(f"{md_path.name}: 헤더 '분석 시각' 라인 없음")
    else:
        time_val = m_time.group(1)
        if PLACEHOLDER_RE.search(time_val):
            errors.append(f"{md_path.name}: 분석 시각에 placeholder 잔존 ({time_val})")
        elif not ISO_RE.match(time_val):
            errors.append(f"{md_path.name}: 분석 시각 ISO 형식 아님 ({time_val})")

    seen: set[tuple[str, int]] = set()
    unresolved: list[tuple[int, str]] = []
    for ln_no, line in enumerate(lines, 1):
        for m in ANCHOR_RE.finditer(line):
            slug = m.group(1)
            if slug in slug_to_name:
                continue
            key = (slug, ln_no)
            if key in seen:
                continue
            seen.add(key)
            unresolved.append((ln_no, slug))
    for ln_no, slug in unresolved:
        errors.append(f"{md_path.name}:line{ln_no}: 미해결 anchor 'components.md#{slug}'")

    sections = _split_sections(text)
    body_section = _section_lookup(sections, "영향 컴포넌트")
    pre_section_text = text.split("\n## ", 1)[0]
    m_count = HEADER_COUNT_RE.search(pre_section_text)
    if m_count and body_section:
        header_n = int(m_count.group(1))
        unique_n = len(_unique_anchors(body_section))
        if header_n != unique_n:
            errors.append(
                f"{md_path.name}: 헤더 영향 컴포넌트 수({header_n}개)와 본문 ## 영향 컴포넌트 unique 앵커 수({unique_n}) 불일치"
            )

    m_flat = FLAT_HEADER_RE.search(pre_section_text)
    flat_section = _section_lookup(sections, "flat 인덱스")
    if m_flat and flat_section:
        header_rows = int(m_flat.group(1))
        actual_rows = _flat_row_count(flat_section)
        if header_rows != actual_rows:
            errors.append(
                f"{md_path.name}: flat 인덱스 헤더({header_rows}행)와 실제 표 행수({actual_rows}) 불일치"
            )

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
        if is_continuation and not is_new:
            has_count = any(k in keys for k in CONTINUATION_COUNT_KEYS)
            if not has_count:
                errors.append(
                    f"{LOG.name}:line{i}: 정정·재검증 라인에 카운트 키({'/'.join(CONTINUATION_COUNT_KEYS)}) 중 하나 이상 필요 — IMPACT-INDEX 누적 검색 부담 회피"
                )
        ts = obj.get("ts", "")
        if not ISO_RE.match(ts):
            errors.append(f"{LOG.name}:line{i}: ts ISO 형식 아님 ({ts})")
    return errors


def main() -> int:
    if len(sys.argv) > 1:
        print(
            f"usage: python validate_impact.py (no arguments; got {sys.argv[1:]})",
            file=sys.stderr,
        )
        return 2

    df = pd.read_excel(XLSX).dropna(subset=["Name"]).reset_index(drop=True)
    slug_to_name = _build_slug_map(df)

    md_files = sorted(p for p in ROOT.glob("impact_*.md") if p.name != "impact_context.md")

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
