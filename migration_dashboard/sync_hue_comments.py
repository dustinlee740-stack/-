"""Hue(Hive Metastore) → data/column_comments.csv (전 테이블 컬럼 설명 + Hue 노출 순서).

Kudu는 LOCATION/외부 테이블 정보가 없어 커버리지에 구멍이 있다. Hue가 읽는 Hive Metastore는
Kudu 관리 + LOCATION/외부 테이블의 컬럼 Comment를 모두 보유하고, 컬럼 순서(ordinal)도 제공한다.

🔒 안전(필수): Hue의 **메타데이터 읽기 API(autocomplete)만** 호출한다(승인된 예외).
- SPA를 로드하지 않으므로 get_config/create_notebook/jobs 등 다른 POST는 발생하지 않는다.
- 호출 직전 URL이 autocomplete 엔드포인트인지 검증한다(assert_safe_autocomplete).
- 쿼리 실행/Sample/Invalidate/새로고침/가져오기/삭제는 절대 호출하지 않는다.

autocomplete 응답:
  ""            → {"databases":[...]}
  "<db>"        → {"tables_meta":[{name},...]} 또는 {"tables":[...]}
  "<db>/<tbl>"  → {"comment": <테이블설명>, "extended_columns":[{name,comment,type,...}], ...}
                  extended_columns 순서 = Hue 노출 순서 → col_seq.

실행:
    # hue_config.md에 HUE_URL + (쿠키 HUE_SESSIONID/HUE_CSRFTOKEN 권장) 또는 (id/pw → hue_login.py 먼저)
    python sync_hue_comments.py            # 증분(전체 Hive 열거 후 변경/추가만 upsert)
    python sync_hue_comments.py --full     # 전체 재작성
    python sync_hue_comments.py --table CS_MCPM_CHRG   # 이름 부분일치 테이블만

기본은 data/an_schema.csv의 테이블명 집합에 해당하는 Hive 테이블만 컬럼을 가져온다(대시보드 대상).
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlparse, parse_qs, quote

from common import DATA_DIR, read_csv, write_csv, norm
from hue_common import load_config, AUTH_STATE, AUTOCOMPLETE_PREFIX, assert_safe_autocomplete

CACHE = DATA_DIR / "column_comments.csv"
CACHE_FIELDS = ["schema", "table", "column", "comment", "col_seq", "table_comment"]


def needed_tables() -> set:
    """대시보드 대상 = an_schema.csv의 테이블명(정규화) 집합."""
    an = read_csv(DATA_DIR / "an_schema.csv")
    return {norm(r.get("an_table")) for r in an if r.get("an_table", "").strip()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--table", default="")
    args = ap.parse_args()

    cfg = load_config()
    raw = (cfg.get("HUE_URL", "") or "").strip()
    if not raw:
        raise SystemExit("HUE_URL 미설정 — hue_config.md를 채워주세요.")
    pu = urlparse(raw)
    base = f"{pu.scheme}://{pu.netloc}"
    src = (parse_qs(pu.query).get("source_type", ["hive"]) or ["hive"])[0]

    sid = cfg.get("HUE_SESSIONID", "")
    if not sid and not AUTH_STATE.exists():
        raise SystemExit("인증 없음 — hue_config.md에 HUE_SESSIONID 입력 또는 `python hue_login.py` 먼저 실행")

    want = needed_tables()
    tfilter = args.table.upper()

    from playwright.sync_api import sync_playwright
    rows_out = {}          # (schema, table) -> [(col, comment, seq)]
    table_comments = {}    # (schema, table) -> table comment
    calls = 0

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx_args = {"ignore_https_errors": True}
        if not sid and AUTH_STATE.exists():
            ctx_args["storage_state"] = str(AUTH_STATE)
        ctx = b.new_context(**ctx_args)
        if sid:
            host = pu.hostname
            cookies = [{"name": "sessionid", "value": sid, "domain": host, "path": "/"}]
            csrf_cfg = cfg.get("HUE_CSRFTOKEN", "")
            if csrf_cfg:
                cookies.append({"name": "csrftoken", "value": csrf_cfg, "domain": host, "path": "/"})
            ctx.add_cookies(cookies)

        csrf = next((c["value"] for c in ctx.cookies() if c["name"] == "csrftoken"), "")
        api = ctx.request
        hdr = {"X-CSRFToken": csrf, "X-Requested-With": "XMLHttpRequest", "Referer": base + "/hue/editor/"}

        def ac(path: str):
            """autocomplete 호출(메타데이터 읽기 전용). path 예: '', 'CS', 'CS/CS_MCPM_CHRG'."""
            nonlocal calls
            url = base + AUTOCOMPLETE_PREFIX + ("/" + path if path else "")
            assert_safe_autocomplete(base, url)  # 🔒 autocomplete 외 차단
            calls += 1
            r = api.post(url, headers=hdr, form={"snippet": json.dumps({"type": src})}, timeout=20000)
            if r.status != 200:
                return {}
            try:
                return json.loads(r.text())
            except Exception:
                return {}

        # 1) 데이터베이스 목록
        dbs = ac("").get("databases", []) or []
        print(f"[sync_hue] base={base} source_type={src} · DB {len(dbs)}개")

        # 2) DB별 테이블 목록 → 대상(want)과 교집합만 컬럼 수집
        for di, db in enumerate(sorted(dbs), 1):
            meta = ac(quote(db))
            tlist = meta.get("tables_meta") or meta.get("tables") or []
            names = [(t.get("name") if isinstance(t, dict) else t) for t in tlist]
            for tname in names:
                if not tname:
                    continue
                if want and norm(tname) not in want:
                    continue
                if tfilter and tfilter not in (db + "." + tname).upper():
                    continue
                # 3) 컬럼 메타데이터
                d = ac(quote(db) + "/" + quote(tname))
                ec = d.get("extended_columns") or []
                cols = []
                for seq, c in enumerate(ec, 1):
                    nm = (c.get("name") or "").strip()
                    if nm:
                        cols.append((nm, (c.get("comment") or "").strip(), seq))
                if cols:
                    rows_out[(db, tname)] = cols
                    table_comments[(db, tname)] = (d.get("comment") or "").strip()
            if di % 10 == 0:
                print(f"  ... DB {di}/{len(dbs)} 처리, 누적 테이블 {len(rows_out)}")
        b.close()

    print(f"  autocomplete 호출 {calls}건(전부 메타데이터 읽기) · 수집 테이블 {len(rows_out)}")

    # 캐시 병합(증분)
    existing = {} if args.full else {
        (norm(r["schema"]), norm(r["table"]), norm(r["column"])): r for r in read_csv(CACHE)
    }
    scanned_tbl = {(norm(s), norm(t)) for (s, t) in rows_out}
    merged = {} if args.full else dict(existing)
    new_keys = set()
    added = updated = unchanged = removed = 0
    for (schema, table), cols in rows_out.items():
        for col, comment, seq in cols:
            key = (norm(schema), norm(table), norm(col))
            new_keys.add(key)
            row = {"schema": schema, "table": table, "column": col, "comment": comment,
                   "col_seq": seq, "table_comment": table_comments.get((schema, table), "")}
            prev = existing.get(key)
            if prev is None:
                added += 1
            elif (prev.get("comment") or "") != comment or str(prev.get("col_seq") or "") != str(seq):
                updated += 1
            else:
                unchanged += 1
            merged[key] = row
    for k in list(merged):
        if (k[0], k[1]) in scanned_tbl and k not in new_keys:
            del merged[k]
            removed += 1

    rows = sorted(merged.values(), key=lambda r: (r["schema"], r["table"], int(r.get("col_seq") or 0)))
    write_csv(CACHE, CACHE_FIELDS, rows)
    mode = "전체" if args.full else ("부분(--table)" if args.table else "증분")
    print(f"[sync_hue_comments] {mode}: 수집 {len(rows_out)}테이블 · added {added} · updated {updated} "
          f"· unchanged {unchanged} · removed {removed} · 캐시 총 {len(rows)}행 → {CACHE}")


if __name__ == "__main__":
    main()
