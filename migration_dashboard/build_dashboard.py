"""data/*.csv → dashboard.html (단독 실행).

- 운영계/분석계/사유/컴포넌트 CSV를 읽어 원본 행을 HTML에 JSON으로 임베드한다.
- 집계·렌더링은 템플릿의 JS(computeModel)가 수행한다 → 임베드 데이터와 드래그앤드롭 CSV가 동일 경로.
- 이 스크립트는 동일 규칙으로 reconcile 지표를 재계산해 stdout에 출력한다(1차 진실 = Python, 교차검증).
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

from common import (BASE_DIR, DATA_DIR, read_csv, norm, truthy_pii,
                    EXCLUDING_REASONS, REASON_LABELS,
                    ST_MIGRATED, ST_NOT_MIGRATED, ST_EXCLUDED, ST_AN_DERIVED, ST_AN_ORPHAN,
                    badge_for, rate_for, BADGE_NA)

TEMPLATE = BASE_DIR / "template" / "dashboard.html.tmpl"
OUTPUT = BASE_DIR / "dashboard.html"


def build_comment_index(comments):
    """Kudu column_comments → {(분석계 table, column): comment}. JS와 동일 규칙."""
    exact = {}
    for r in comments:
        t, c = norm(r.get("table")), norm(r.get("column"))
        cmt = (r.get("comment") or "").strip()
        if t and c and cmt:
            exact[(t, c)] = cmt
    return exact


def lookup_desc(exact, an_table, an_column, fallback):
    """분석계 (table,column)로 Hue 설명 룩업 → ("Hue") 없으면 fallback("기존"). (값, 출처)."""
    if an_table and an_column and (norm(an_table), norm(an_column)) in exact:
        return exact[(norm(an_table), norm(an_column))], "Hue"
    return (fallback or ""), "기존"


def compute_model(op, an, reasons, comps, comments=None):
    """JS computeModel과 동일 규칙. reconcile 검증용으로 트리+합계를 반환."""
    cmt_exact = build_comment_index(comments or [])
    migrated_keys = {}
    for r in an:
        oc, ot, ocol = norm(r.get("op_component")), norm(r.get("op_table")), norm(r.get("op_column"))
        if ocol:
            migrated_keys.setdefault((oc, ot, ocol),
                                     {"at": r.get("an_table", ""), "ac": r.get("an_column", "")})

    col_reason, tbl_reason = {}, {}
    for r in reasons:
        c, t, col = norm(r.get("component")), norm(r.get("table")), norm(r.get("column"))
        code = (r.get("reason_code") or "").strip()
        note = r.get("reason_note") or ""
        if col:
            col_reason[(c, t, col)] = (code, note)
        else:
            tbl_reason[(c, t)] = (code, note)

    op_keys = {(norm(r["component"]), norm(r["table"]), norm(r["column"])) for r in op}

    # 컴포넌트 역할
    roles = {}
    for r in comps:
        roles[norm(r.get("Name"))] = r

    # 트리: comp -> table -> {op_cols, an_only}
    tree: dict = {}

    def node(comp):
        return tree.setdefault(comp, {"tables": {}})

    def tnode(comp, table):
        return node(comp)["tables"].setdefault(table, {"cols": []})

    # 운영계 컬럼
    for r in op:
        c, t, col = norm(r["component"]), norm(r["table"]), norm(r["column"])
        key = (c, t, col)
        is_pii = truthy_pii(r.get("is_pii"))
        m = migrated_keys.get(key)
        if m is not None:
            _, desc_src = lookup_desc(cmt_exact, m["at"], m["ac"], r.get("column_desc"))
            tnode(c, t)["cols"].append({"status": ST_MIGRATED, "pii": is_pii, "descSrc": desc_src})
        else:
            # 미이관 컬럼은 분석계에 없으므로 Kudu 설명 없음 → 기존(op_schema) 유지
            reason = col_reason.get(key) or tbl_reason.get((c, t))
            auto = False
            if not reason and is_pii:
                reason, auto = ("PII_EXCLUDED", ""), True
            code = reason[0] if reason else None
            excluded = code in EXCLUDING_REASONS
            status = ST_EXCLUDED if excluded else ST_NOT_MIGRATED
            tnode(c, t)["cols"].append({"status": status, "pii": is_pii,
                                        "code": code, "auto": auto, "descSrc": "기존"})

    # 분석계 전용
    for r in an:
        oc, ot, ocol = norm(r.get("op_component")), norm(r.get("op_table")), norm(r.get("op_column"))
        if ocol and (oc, ot, ocol) in op_keys:
            continue  # 이관됨(이미 op쪽에서 계산)
        c, t = norm(r.get("an_component")), norm(r.get("an_table"))
        derived = (not ocol) or bool((r.get("source_expr") or "").strip())
        status = ST_AN_DERIVED if derived else ST_AN_ORPHAN
        tnode(c, t)["cols"].append({"status": status, "pii": False})

    # 집계
    totals = {"op_total": 0, "migrated": 0, "notmig": 0, "excluded": 0,
              "derived": 0, "orphan": 0, "pii_migrated": 0, "unassigned": 0,
              "desc_hue": 0, "desc_legacy": 0}
    for c, cn in tree.items():
        for t, tn in cn["tables"].items():
            for col in tn["cols"]:
                s = col["status"]
                if s in (ST_MIGRATED, ST_EXCLUDED, ST_NOT_MIGRATED):
                    if col.get("descSrc") == "Hue": totals["desc_hue"] += 1
                    else: totals["desc_legacy"] += 1
                if s == ST_MIGRATED:
                    totals["op_total"] += 1; totals["migrated"] += 1
                    if col["pii"]:
                        totals["pii_migrated"] += 1
                elif s == ST_EXCLUDED:
                    totals["op_total"] += 1; totals["excluded"] += 1
                elif s == ST_NOT_MIGRATED:
                    totals["op_total"] += 1; totals["notmig"] += 1
                    if col.get("code") is None:
                        totals["unassigned"] += 1
                elif s == ST_AN_DERIVED:
                    totals["derived"] += 1
                elif s == ST_AN_ORPHAN:
                    totals["orphan"] += 1
    return tree, totals


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.date.today().isoformat(),
                    help="대시보드 기준 일자(기본: 오늘). 결정론 검증 시 고정값 전달")
    args = ap.parse_args()

    op = read_csv(DATA_DIR / "op_schema.csv")
    an = read_csv(DATA_DIR / "an_schema.csv")
    reasons = read_csv(DATA_DIR / "reasons.csv")
    comps = read_csv(DATA_DIR / "components.csv")
    comments = read_csv(DATA_DIR / "column_comments.csv")  # Kudu 컬럼 설명 캐시(없으면 빈 리스트)
    for name, rows in [("op_schema", op), ("an_schema", an), ("components", comps)]:
        if not rows:
            raise SystemExit(f"data/{name}.csv 없음 또는 비어있음 — 생성 단계를 먼저 실행하세요")

    tree, totals = compute_model(op, an, reasons, comps, comments)

    # --- reconcile (Python = 1차 진실) ---
    an_tables = {(r.get("an_component"), r.get("an_table")) for r in an}
    op_tables = {(r["component"], r["table"]) for r in op}
    denom = totals["op_total"] - totals["excluded"]
    overall_rate = rate_for(totals["migrated"], denom)
    sum_check = totals["migrated"] + totals["notmig"] + totals["excluded"]
    print("[build_dashboard] reconcile")
    print(f"  운영계: 컬럼 {totals['op_total']} · 테이블 {len(op_tables)} · 컴포넌트 {len({c for c,_ in op_tables})}")
    print(f"  분석계: 테이블 {len(an_tables)} · 컬럼행 {len(an)}")
    print(f"  이관 {totals['migrated']} / 미이관 {totals['notmig']} / 제외 {totals['excluded']} "
          f"→ 합 {sum_check} (운영계 컬럼수와 일치? {sum_check == totals['op_total']})")
    print(f"  분석계전용(파생 {totals['derived']} / 운영계미등재 {totals['orphan']})")
    print(f"  전체 이관율 = {totals['migrated']}/{denom} = {overall_rate}%")
    print(f"  사유미지정(미이관 중 사유없음) {totals['unassigned']} · PII 이관됨(경고) {totals['pii_migrated']}")
    print(f"  컬럼 설명(Hue): Hue매칭 {totals['desc_hue']} · 기존(샘플) {totals['desc_legacy']} "
          f"(커버리지 {rate_for(totals['desc_hue'], totals['op_total'])}% / 캐시 {len(comments)}행)")

    # --- 임베드 (원본 행 + 메타) ---
    payload = {
        "date": args.date,
        "op": op, "an": an, "reasons": reasons, "components": comps, "comments": comments,
        "reasonLabels": REASON_LABELS,
        "excludingReasons": sorted(EXCLUDING_REASONS),
    }
    data_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    tmpl = TEMPLATE.read_text(encoding="utf-8")
    html = tmpl.replace("/*__DATA__*/", data_json)
    OUTPUT.write_text(html, encoding="utf-8")
    size_kb = round(OUTPUT.stat().st_size / 1024)
    print(f"  → {OUTPUT}  ({size_kb} KB)")


if __name__ == "__main__":
    main()
