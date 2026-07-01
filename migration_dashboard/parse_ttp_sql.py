"""ttp_workflow/*.sql (분석계 적재문) → data/an_schema.csv (분석계 이관 정답지).

각 SQL 파일은 분석계로 이관된 테이블 1개를 정의한다:
    upsert into table  X.Y  select  <식> as <컬럼>, ...  from temp.tmp_*  ;
    insert into table  X.Y  select  ...
    insert overwrite table X.Y select ...

추출:
- 컴포넌트 = X (SQL 스키마 접두사. 폴더명이 아님 — 폴더 KODASP도 테이블은 kod.*)
- 테이블   = Y
- 분석계 컬럼 = 각 select 항목의 depth-0 마지막 `as <식별자>` (타깃, 결정론적)
- 운영계 컬럼 = best-effort (단일 식별자 / cast(<id> as type)만 인정, 그 외 source_expr 보존)
- op_component/op_table = X / Y (분석계 SQL은 운영계 테이블명을 담지 않으므로 동일 추정.
  실데이터에서는 분석계 CSV의 op_table을 실제 운영계 테이블명으로 채워야 함 — README 참조)
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from common import BASE_DIR, DATA_DIR, write_csv

# `table` 키워드는 선택(upsert into X.Y / insert overwrite table X.Y 둘 다 존재)
# 식별자는 백틱 인용 가능(예: POR.`ROLE` — 예약어)
HEADER_RE = re.compile(
    r"(?im)^\s*(?:upsert\s+into|insert\s+into|insert\s+overwrite)\s+(?:table\s+)?"
    r"`?([A-Za-z0-9_]+)`?\.`?([A-Za-z0-9_]+)`?"
)
FROM_TEMP_RE = re.compile(r"(?is)\bfrom\s+temp\.tmp_", )
AS_TAIL_RE = re.compile(r"(?is)\bas\s+`?([A-Za-z0-9_]+)`?\s*$")
SINGLE_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
CAST_ONE_RE = re.compile(r"(?is)^cast\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s+as\s+\w+\s*\)$")

OUT_FIELDS = ["an_component", "an_table", "an_column",
              "op_component", "op_table", "op_column", "source_expr"]

BOILERPLATE_TARGETS = {"HDFS_UPD_DTTM"}


def split_top_level_commas(s: str) -> list[str]:
    """괄호 깊이를 추적해 depth-0 콤마에서만 분리(함수 인자 콤마 보호)."""
    items, buf, depth = [], [], 0
    in_str = None
    for ch in s:
        if in_str:
            buf.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in "'\"":
            in_str = ch
            buf.append(ch)
        elif ch == "(":
            depth += 1
            buf.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == "," and depth == 0:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        items.append("".join(buf))
    return items


def parse_columns(select_body: str) -> list[tuple[str, str, str]]:
    """select 본문 → [(an_column, op_column, source_expr), ...]."""
    out = []
    for raw in split_top_level_commas(select_body):
        item = raw.strip()
        if not item:
            continue
        m = AS_TAIL_RE.search(item)
        if not m:
            continue  # 타깃 컬럼 없는 항목은 스킵
        target = m.group(1).strip()
        lhs = item[: m.start()].strip()
        if target.upper() in BOILERPLATE_TARGETS:
            continue
        if lhs.lower().startswith("current_timestamp"):
            continue
        # 운영계 컬럼 best-effort
        op_col, src_expr = "", ""
        if SINGLE_IDENT_RE.match(lhs):
            op_col = lhs
        else:
            cm = CAST_ONE_RE.match(lhs)
            if cm:
                op_col = cm.group(1)
            else:
                src_expr = lhs  # CASE / 다중인자 / 상수 등은 식만 보존
        out.append((target, op_col, src_expr))
    return out


def parse_file(path: Path) -> tuple[list[dict], str]:
    """반환: (행 리스트, 스킵사유). 파싱 성공 시 사유는 ''.

    컴포넌트 = ttp_workflow 폴더명(논리 컴포넌트, 카탈로그 역할설명과 매칭).
    테이블   = SQL 헤더의 Y. SQL 스키마 접두사(kod/POR 등 DB 스키마)는 컴포넌트로 쓰지 않는다.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    # 선두 refresh 줄 제거 (.gitlab-ci.yml의 sed '/^refresh/d'와 동일)
    lines = [ln for ln in text.splitlines() if not ln.strip().lower().startswith("refresh")]
    text = "\n".join(lines)

    hm = HEADER_RE.search(text)
    if not hm:
        return [], "헤더 미매칭"
    schema, table = hm.group(1), hm.group(2)
    comp = path.parent.name  # 폴더명 = 논리 컴포넌트

    # 타깃이 staging(temp)면 분석계 적재가 아님 → 스킵
    if schema.lower() == "temp":
        return [], "staging(temp) 타깃"

    after = text[hm.end():]
    # CTE(with ... as) / 집계 쿼리는 컬럼 1:1 추출이 불가 → 정직하게 스킵+보고
    if re.match(r"(?is)\s*with\b", after):
        return [], "CTE/집계(with)"

    sm = re.search(r"(?is)\bselect\b", after)
    if not sm:
        return [], "select 없음"
    body_start = sm.end()
    fm = FROM_TEMP_RE.search(after, body_start)
    body = after[body_start: fm.start()] if fm else after[body_start:]
    body = body.rstrip().rstrip(";")

    cols = parse_columns(body)
    if not cols:
        return [], "컬럼 0개(select */집계 등)"

    rows = []
    for an_col, op_col, src in cols:
        rows.append({
            "an_component": comp, "an_table": table, "an_column": an_col,
            "op_component": comp, "op_table": table, "op_column": op_col,
            "source_expr": src,
        })
    return rows, ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttp-root", default=str(BASE_DIR.parent / "ttp_workflow"),
                    help="ttp_workflow 루트(읽기 전용 입력)")
    args = ap.parse_args()

    root = Path(args.ttp_root)
    files = sorted(p for p in root.rglob("*.sql") if ".git" not in p.parts)
    all_rows, parsed = [], 0
    skipped: dict[str, list[str]] = {}
    for p in files:
        rows, reason = parse_file(p)
        if rows:
            parsed += 1
            all_rows.extend(rows)
        else:
            skipped.setdefault(reason, []).append(p.name)

    out = DATA_DIR / "an_schema.csv"
    write_csv(out, OUT_FIELDS, all_rows)

    tables = {(r["an_component"], r["an_table"]) for r in all_rows}
    comps = {r["an_component"] for r in all_rows}
    n_skip = sum(len(v) for v in skipped.values())
    print(f"[parse_ttp_sql] SQL {len(files)}개 중 {parsed}개 파싱 / 스킵 {n_skip}개")
    print(f"  → 컴포넌트 {len(comps)} · 테이블 {len(tables)} · 컬럼 {len(all_rows)}  ({out})")
    for reason, names in sorted(skipped.items(), key=lambda kv: -len(kv[1])):
        head = ", ".join(names[:6]) + (" ..." if len(names) > 6 else "")
        print(f"  스킵[{reason}] {len(names)}개: {head}")


if __name__ == "__main__":
    main()
