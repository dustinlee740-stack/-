"""[DEPRECATED — Hue/sync_hue_comments.py로 대체] Kudu 웹UI → data/column_comments.csv.

Kudu는 LOCATION/외부 테이블 정보가 없어 커버리지에 구멍이 있다. 현재 정식 소스는 Hue(Hive
Metastore)이며 `sync_hue_comments.py`를 사용한다. 이 파일은 오프라인 시드/정렬 검증용으로만 유지.
출력 스키마는 Hue 캐시와 동일(col_seq 포함)하여 상호 호환된다.

원설명: Kudu 웹UI(/tables) → data/column_comments.csv (분석계 컬럼 한글 설명 캐시).

소스: Kudu 마스터 웹UI의 테이블 상세(`/table?id=<uuid>`) Schema 표의 **Comment 열**.
분석계 적재 시 설정된 한글 설명이며(예: afc_tr_no → "제휴사거래번호"), 인증 없이 HTTP로 읽는다.
표준 라이브러리(urllib)만 사용 — 외부 드라이버 불필요.

실행:
    python sync_column_comments.py                 # 증분: 전체 재스캔 후 변경/추가 컬럼만 캐시 upsert
    python sync_column_comments.py --full          # 전체 재작성(캐시 초기화)
    python sync_column_comments.py --table CS_MCPM # 이름에 부분문자열 매칭되는 테이블만 재수집
    python sync_column_comments.py --base-url http://10.150.150.71:8051

캐시 data/column_comments.csv 를 (schema, table, column) 키로 관리한다.
매일 받을 필요 없음 — 최초 1회 + 컬럼 추가/수정 시 (필요하면 --table로 해당 테이블만) 재실행.
"""
from __future__ import annotations

import argparse
import html as htmllib
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import DATA_DIR, read_csv, write_csv, norm

CACHE = DATA_DIR / "column_comments.csv"
CACHE_FIELDS = ["schema", "table", "column", "comment", "col_seq", "table_comment"]
DEFAULT_BASE = "http://10.150.150.71:8051"

# /tables 데이터 행: <td>impala::SCHEMA.TABLE</td><td><a href="/table?id=UUID">
ROW_RE = re.compile(
    r'<td>\s*(?:impala::)?([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)\s*</td>\s*'
    r'<td>\s*<a href="/table\?id=([a-f0-9]+)"', re.S)
TABLE_RE = re.compile(r"<table.*?</table>", re.S)
TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S)
TBL_COMMENT_RE = re.compile(r"Comment:[ \t]*([^<\n]*)")


def fetch(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "migration-dashboard-sync"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def cell_text(c: str) -> str:
    return htmllib.unescape(re.sub(r"<[^>]*>", "", c)).strip().strip("`")


def list_tables(base: str) -> list[tuple[str, str, str]]:
    """(schema, table, uuid) 목록."""
    h = fetch(base + "/tables")
    return [(m.group(1), m.group(2), m.group(3)) for m in ROW_RE.finditer(h)]


def parse_detail(h: str) -> tuple[str, list[tuple[str, str]]]:
    """(테이블 Comment, [(column, comment), ...])."""
    tc = TBL_COMMENT_RE.search(re.sub(r"<[^>]*>", "", h))
    table_comment = htmllib.unescape(tc.group(1)).strip() if tc else ""
    cols = []
    for tbl in TABLE_RE.findall(h):
        if "Encoding" not in tbl or "Comment" not in tbl:
            continue  # Schema 표만(Column|ID|Type|Encoding|...|Comment|...)
        rows = TR_RE.findall(tbl)
        for r in rows[1:]:  # 헤더 제외
            cells = [cell_text(c) for c in CELL_RE.findall(r)]
            if len(cells) >= 8 and cells[0]:
                cols.append((cells[0], cells[7]))  # Column, Comment
        break
    return table_comment, cols


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=DEFAULT_BASE)
    ap.add_argument("--full", action="store_true", help="전체 재작성(캐시 초기화)")
    ap.add_argument("--table", default="", help="이름에 이 부분문자열이 포함된 테이블만 재수집")
    args = ap.parse_args()

    tables = list_tables(args.base_url)
    if not tables:
        raise SystemExit(f"테이블 목록을 못 읽음 — {args.base_url}/tables 확인")
    if args.table:
        sub = args.table.upper()
        scan = [t for t in tables if sub in (t[0] + "." + t[1]).upper()]
        print(f"[sync] --table '{args.table}' 매칭 {len(scan)}/{len(tables)} 테이블만 재수집")
    else:
        scan = tables

    def work(t):
        schema, table, uuid = t
        try:
            tc, cols = parse_detail(fetch(args.base_url + "/table?id=" + uuid))
            return schema, table, uuid, tc, cols
        except Exception as e:
            print(f"  ! {schema}.{table} 실패: {e}")
            return schema, table, uuid, "", []

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(work, scan))

    # 기존 캐시 로드(--full이면 무시)
    existing = {} if args.full else {
        (norm(r["schema"]), norm(r["table"]), norm(r["column"])): r for r in read_csv(CACHE)
    }
    scanned_tbl_keys = {(norm(s), norm(t)) for s, t, _u in scan}

    removed = 0
    new_keys = set()
    added = updated = unchanged = 0
    merged = {} if args.full else dict(existing)

    for schema, table, uuid, tc, cols in results:
        for seq, (col, comment) in enumerate(cols, 1):  # col_seq = 상세 페이지 노출 순서
            key = (norm(schema), norm(table), norm(col))
            new_keys.add(key)
            row = {"schema": schema, "table": table, "column": col,
                   "comment": comment, "col_seq": seq, "table_comment": tc}
            prev = existing.get(key)
            if prev is None:
                added += 1
            elif (prev.get("comment") or "") != comment or str(prev.get("col_seq") or "") != str(seq):
                updated += 1
            else:
                unchanged += 1
            merged[key] = row

    # 스캔된 테이블인데 이번에 안 나온 컬럼 = 제거됨
    for k in list(merged):
        if (k[0], k[1]) in scanned_tbl_keys and k not in new_keys:
            del merged[k]
            removed += 1

    rows = sorted(merged.values(),
                  key=lambda r: (r["schema"], r["table"], int(r.get("col_seq") or 0)))
    write_csv(CACHE, CACHE_FIELDS, rows)
    mode = "전체" if args.full else ("부분(--table)" if args.table else "증분")
    print(f"[sync_column_comments/Kudu] {mode}: 스캔 {len(scan)}테이블 · added {added} · updated {updated} "
          f"· unchanged {unchanged} · removed {removed} · 캐시 총 {len(rows)}행 → {CACHE}")


if __name__ == "__main__":
    main()
