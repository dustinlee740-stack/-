"""구문/의미 비교 공유 헬퍼

LogicalPlan 두 개를 비교할 때 양쪽 엔진(의미 비교 analyzer, 구문 비교 comparator)이
**같은 흡수 로직**을 쓰도록 순수 헬퍼를 한곳에 모은다. 두 엔진이 별도 구현으로 갈라져
결과가 어긋나는(drift) 것을 방지한다.

- 집합 비교(한정자 무시 포함)
- 파라미터(플레이스홀더) 흡수
- A측 표시명 역번역(분석명 → 원본 운영명)
- 검색 가능한 영문 앵커 추출
- 조인 엣지 앵커-무관 그룹핑
- 원본 ON 절 텍스트 조회
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp
from sqlglot.tokens import TokenType

from query_diff.models import JoinEdge, _TABLE_REF_RE, _edge_table_set

# 절 경계가 되는 depth-0 토큰들(버전별 차이 안전하게 수집).
_CLAUSE_BOUND_TYPES = {
    t
    for t in (
        getattr(TokenType, _n, None)
        for _n in (
            "FROM", "WHERE", "GROUP_BY", "HAVING", "ORDER_BY", "LIMIT",
            "OFFSET", "QUALIFY", "WINDOW", "UNION", "EXCEPT", "INTERSECT", "SEMICOLON",
        )
    )
    if t is not None
}


# --- 집합 비교 ---

def _diff_sets(
    a: list[str], b: list[str]
) -> tuple[bool, list[str], list[str], list[str]]:
    """두 문자열 집합을 비교하여 (matched, only_a, only_b, shared) 반환."""
    sa, sb = set(a), set(b)
    only_a = sorted(sa - sb)
    only_b = sorted(sb - sa)
    shared = sorted(sa & sb)
    matched = not only_a and not only_b
    return matched, only_a, only_b, shared


def _bare(s: str) -> str:
    """단순 `table.col` 한정자를 떼고 컬럼명만 반환. 표현식(공백/괄호)은 보존."""
    if " " in s or "(" in s:
        return s
    return s.rsplit(".", 1)[-1]


def _diff_sets_by_column(
    a: list[str], b: list[str]
) -> tuple[bool, list[str], list[str], list[str]]:
    """테이블 한정자를 무시하고 컬럼명 기준으로 비교.

    2단계 집계 CTE에서 group/projection 키가 `txn.`/`grp.` 한정자로 달라 보이는
    noise를 제거한다. 표시는 원본 문자열을 유지한다.
    """
    ma: dict[str, str] = {}
    for x in a:
        ma.setdefault(_bare(x), x)
    mb: dict[str, str] = {}
    for x in b:
        mb.setdefault(_bare(x), x)
    only_a = sorted(ma[k] for k in ma if k not in mb)
    only_b = sorted(mb[k] for k in mb if k not in ma)
    shared = sorted(ma[k] for k in ma if k in mb)
    return (not only_a and not only_b), only_a, only_b, shared


# --- 파라미터(플레이스홀더) 흡수 ---

_LIT_RE = re.compile(r"'[^']*'|\b\d+(?:\.\d+)?\b")
_INLIST_RE = re.compile(r"\(\?(?:, \?)*\)")


def _shape(s: str) -> str:
    """리터럴·플레이스홀더를 `?`로, IN 목록을 `(?)`로 정규화한 형태."""
    s = _LIT_RE.sub("?", s)
    s = _INLIST_RE.sub("(?)", s)
    return s


def _has_placeholder(s: str) -> bool:
    return "__PLACEHOLDER__" in s or "${" in s


def _is_datelike(lit: str) -> bool:
    """리터럴이 **유효한 날짜값**(YYYYMMDD·YYYYMM·YYYY-MM-DD)인지. 따옴표는 무시.

    날짜 조건의 경계값은 보통 조회 기간 파라미터다(예: `rqs_dt <= 20250731`). 코드값
    (`'A0000'`)·일반 숫자(`1000`)·큰 정수(`20000000`=MM 00 무효)는 날짜로 보지 않아
    '값만 다른 항목' 흡수 대상에서 자연히 제외된다(과흡수 방지)."""
    s = lit.strip().strip("'").strip('"')
    m = re.fullmatch(r"(\d{4})-?(\d{2})-?(\d{2})", s)        # YYYYMMDD / YYYY-MM-DD
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return 1900 <= y <= 2099 and 1 <= mo <= 12 and 1 <= d <= 31
    m = re.fullmatch(r"(\d{4})-?(\d{2})", s)                 # YYYYMM / YYYY-MM
    if m:
        y, mo = int(m[1]), int(m[2])
        return 1900 <= y <= 2099 and 1 <= mo <= 12
    return False


def _diff_lits_all_datelike(x: str, y: str) -> bool:
    """shape 가 같은 두 술어에서 **다른 리터럴이 모두 날짜값**이면 True.

    같은 컬럼·연산자에 날짜 경계값만 다른 경우(조회 기간 파라미터)를 흡수 후보로 본다."""
    lx, ly = _LIT_RE.findall(x), _LIT_RE.findall(y)
    if len(lx) != len(ly):
        return False
    diffs = [(a, b) for a, b in zip(lx, ly) if a != b]
    return bool(diffs) and all(_is_datelike(a) and _is_datelike(b) for a, b in diffs)


def _absorb_parameterized(
    only_a: list[str], only_b: list[str]
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """형태(shape)는 같고 **파라미터(값)** 때문에만 다른 쌍을 흡수.

    흡수 대상: ①템플릿 변수(`>= ${start}`)·IN 목록(`IN (${bnf_id})`) ②같은 컬럼·연산자에
    **날짜 경계값만** 다른 경우(`rqs_dt <= 20250731` vs `<= 20241231` — 조회 기간 파라미터).
    날짜가 아닌 리터럴 차이(`status='A'` vs `'B'`, `amt>=1000` vs `2000`)는 **진짜 차이**라
    흡수하지 않는다(과흡수 방지). 반환: (남은 A전용, 남은 B전용, 흡수된 (a,b) 쌍 목록).
    """
    rem_a = list(only_a)
    used_b: set[int] = set()
    absorbed: list[tuple[str, str]] = []
    for x in list(rem_a):
        sx = _shape(x)
        for j, y in enumerate(only_b):
            if j in used_b:
                continue
            if _shape(y) == sx and (
                _has_placeholder(x) or _has_placeholder(y) or _diff_lits_all_datelike(x, y)
            ):
                used_b.add(j)
                absorbed.append((x, y))
                rem_a.remove(x)
                break
    rem_b = [y for j, y in enumerate(only_b) if j not in used_b]
    return rem_a, rem_b, absorbed


# --- 한정자(qualifier) 노이즈 흡수 ---

def _bare_pred_key(pred: str) -> str | None:
    """정규 술어에서 `table.col` 한정자만 떼어낸 매칭 키(**값은 보존**). 파싱 실패 시 None.

    `⟨YM:…⟩` 토큰 등 sqlglot 비파싱 술어는 None → 한정자 흡수 대상에서 제외."""
    if "⟨" in pred:
        return None
    try:
        node = sqlglot.parse_one(pred)
    except Exception:
        return None
    for col in node.find_all(exp.Column):
        col.set("table", None)
        col.set("db", None)
        col.set("catalog", None)
    return node.sql()


def _is_qualified(pred: str) -> bool:
    """술어에 `table.col` 한정 컬럼 참조가 있으면 True."""
    return bool(_COLREF_RE.search(pred))


def _absorb_qualifier_noise(
    only_a: list[str], only_b: list[str]
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """**한정자만 다른** 술어 흡수(예: `cdm.old_par IS NOT NULL` ↔ 맨컬럼 `old_par IS NOT NULL`).

    다중테이블 스코프라 한쪽이 컬럼을 한정 못 했을 뿐 동일 조건인 경우를 노이즈로 흡수한다.
    값 보존(다른 값이면 키 불일치)하고, **한쪽 이상이 비한정**일 때만 흡수(둘 다 한정이면 서로
    다른 테이블일 수 있어 제외 — 거짓흡수 방지)."""
    rem_a = list(only_a)
    used_b: set[int] = set()
    absorbed: list[tuple[str, str]] = []
    for x in list(rem_a):
        kx = _bare_pred_key(x)
        if kx is None:
            continue
        for j, y in enumerate(only_b):
            if j in used_b:
                continue
            if _bare_pred_key(y) == kx and not (_is_qualified(x) and _is_qualified(y)):
                used_b.add(j)
                absorbed.append((x, y))
                rem_a.remove(x)
                break
    rem_b = [y for j, y in enumerate(only_b) if j not in used_b]
    return rem_a, rem_b, absorbed


# --- 날짜 범위(원시 ↔ 일추출) 흡수: 제한적 판정 ---

# 날짜범위를 동치로 흡수했을 때의 제한적 판정 주의블록(의미·구문 두 화면 공용).
_DATE_RANGE_CAVEAT = (
    "날짜 범위 동치 간주 — 경계 방식이 다름\n"
    "A : 원시 타임스탬프 범위(>, <) — 컬럼값 직접 비교\n"
    "B : 일 추출(from_timestamp 등) + BETWEEN(>=, <=) + 템플릿 파라미터\n"
    "※ 경계 포함성(< vs <=)·일↔초 절단·파라미터 실제 값에 따라 결과가 다를 수 있음\n"
    "→ 동일 기간 산출 여부 확인 필요"
)

_BOUND_RE = re.compile(r"^(?P<lhs>.+?)\s*(?P<op><=|>=|<|>)\s*(?P<rhs>.+)$")
_YM_LHS_RE = re.compile(r"^⟨YM:(?P<col>.+?):(?P<gran>\w+)⟩$")


def _range_bound(pred: str) -> tuple[str, str, bool, bool] | None:
    """경계 술어를 (base_col_key, kind['lower'|'upper'], ym, placeholder) 로 분류. 아니면 None.

    LHS 가 `⟨YM:col:gran⟩` 면 base=col·ym=True. base 는 한정자 제거(마지막 세그먼트)로 키화."""
    m = _BOUND_RE.match(pred)
    if not m:
        return None
    lhs = m.group("lhs").strip()
    mym = _YM_LHS_RE.match(lhs)
    base = mym.group("col") if mym else lhs
    base_key = base.rsplit(".", 1)[-1].lower()
    kind = "lower" if m.group("op") in (">", ">=") else "upper"
    return base_key, kind, bool(mym), _has_placeholder(m.group("rhs"))


def _absorb_date_range(
    only_a: list[str], only_b: list[str]
) -> tuple[list[str], list[str], bool]:
    """같은 컬럼의 **하한+상한 범위**가 양쪽에 있고 **날짜맥락 신호**(YM 추출/플레이스홀더)가 있으면
    흡수(원시 타임스탬프 ↔ 일추출 BETWEEN 의 비대칭). 반환: (남은A, 남은B, caveat 발생 여부).

    동일컬럼·동일연산·datelike 범위는 `_absorb_parameterized` 가 선흡수하므로, 본 패스는 컬럼식/
    연산자가 어긋난 비대칭 케이스만 처리한다. 신호 없는 임의 숫자범위는 미흡수(거짓흡수 방지)."""
    def _by_col(items: list[str]) -> dict[str, dict]:
        d: dict[str, dict] = {}
        for p in items:
            rb = _range_bound(p)
            if rb is None:
                continue
            base, kind, ym, ph = rb
            e = d.setdefault(base, {"lower": [], "upper": [], "ym": False, "ph": False})
            e[kind].append(p)
            e["ym"] |= ym
            e["ph"] |= ph
        return d

    da, db = _by_col(only_a), _by_col(only_b)
    absorbed_a: set[str] = set()
    absorbed_b: set[str] = set()
    caveat = False
    for col in set(da) & set(db):
        ea, eb = da[col], db[col]
        if ea["lower"] and ea["upper"] and eb["lower"] and eb["upper"]:
            if ea["ym"] or eb["ym"] or ea["ph"] or eb["ph"]:   # 날짜맥락 신호 필요
                absorbed_a.update(ea["lower"] + ea["upper"])
                absorbed_b.update(eb["lower"] + eb["upper"])
                caveat = True
    rem_a = [p for p in only_a if p not in absorbed_a]
    rem_b = [p for p in only_b if p not in absorbed_b]
    return rem_a, rem_b, caveat


# --- 연-월(날짜추출) 관용구 캐비엣: 실제 추출식·입도 동적 생성 ---

_GRAN_LABEL = {"YEAR": "연(YYYY)", "MONTH": "연-월(YYYYMM)", "DAY": "연-월-일(YYYYMMDD)"}
_SUBSTR_RE = re.compile(r"\bSUBSTR(?:ING)?\b", re.IGNORECASE)


def _ym_expr(col_bare, raw_maps):
    """raw 맵 목록(list[_RawSrc])의 col_map 에서 컬럼의 첫 원문식 반환(없으면 None)."""
    for m in raw_maps:
        if m is not None:
            units = m.col_map.get(col_bare)
            if units:
                return units[0]
    return None


def _year_month_detail(tokens, raw_a, raw_b, rename=None):
    """매칭된 `⟨YM:col:gran⟩` 토큰 → **실제 A/B 추출식·정확한 입도** 캐비엣. 반환 (caveat, a식, b식).

    토큰은 추출 방식(substr↔포맷)을 잃으므로 원문식 텍스트로 substr 여부 판별(substr 경고는 그때만).
    A측 raw 맵은 op 명 키라 토큰의 분석명을 rename(an→op)으로 역참조 후 조회(실패 시 분석명 폴백)."""
    toks = [t for t in tokens if _YM_LHS_RE.match(t)]
    if not toks:
        return "", "", ""
    rename = rename or {}
    ab_lines: list[str] = []
    a_snips: list[str] = []
    b_snips: list[str] = []
    substr_used = False
    gran_label = "날짜"
    for tok in toks:
        m = _YM_LHS_RE.match(tok)
        col_an = m.group("col").rsplit(".", 1)[-1].lower()
        col_op = rename.get(col_an, col_an)
        a_expr = _ym_expr(col_op, raw_a) or _ym_expr(col_an, raw_a)
        b_expr = _ym_expr(col_an, raw_b)
        if (a_expr and _SUBSTR_RE.search(a_expr)) or (b_expr and _SUBSTR_RE.search(b_expr)):
            substr_used = True
        gran_label = _GRAN_LABEL.get(m.group("gran"), "날짜")
        a_disp = _upper_disp(a_expr) if a_expr else "(원문 미확인)"
        b_disp = _upper_disp(b_expr) if b_expr else "(원문 미확인)"
        a_snips.append(a_disp)
        b_snips.append(b_disp)
        ab_lines.append(f"A : {a_disp}")
        ab_lines.append(f"B : {b_disp}")
    msg = [f"{gran_label} 추출을 동치로 간주 — 추출 방식이 다를 수 있음", *ab_lines]
    if substr_used:
        msg.append(
            "※ substr(위치 추출)은 컬럼 문자열 표현에 의존 — 구분자(예: '2025/05/01')가 있으면 결과가 달라질 수 있음"
        )
    msg.append("→ 동일 버킷 산출 여부(운영 DB 실제 포맷·타입) 검토 필요")
    return "\n".join(msg), ", ".join(a_snips), ", ".join(b_snips)


# --- A측 표시명 역번역 ---

_IDENT_RE = re.compile(r"[A-Za-z0-9_가-힣]+")


def _detranslate(s: str, rename: dict[str, str]) -> str:
    """분석명 토큰을 원본 운영명으로 되돌린다(표시 전용). 단어 경계 기준 치환."""
    if not s or not rename:
        return s
    return _IDENT_RE.sub(lambda m: rename.get(m.group(0), m.group(0)), s)


def _da(oa: list[str], rename: dict[str, str] | None) -> list[str]:
    """A측 목록만 원본 운영명으로 역변환(B측은 손대지 않음)."""
    return [_detranslate(x, rename) for x in oa] if rename else oa


# --- 검색 가능한 영문 앵커 ---

_COLREF_RE = re.compile(r"[A-Za-z_][\w]*\.[A-Za-z_][\w]*")


def _ref_cols(preds: list[str]) -> list[str]:
    """술어 문자열들에서 `table.col` 토큰만 추출(쿼리에서 검색 가능한 앵커)."""
    cols: set[str] = set()
    for p in preds:
        cols.update(_COLREF_RE.findall(p))
    return sorted(cols)


def _bare_cols(items: list[str]) -> list[str]:
    """`alias.col`/`table.col` 에서 컬럼명만 추출(중복 제거). CTE 별칭 접두사 제거용."""
    out: list[str] = []
    for x in items:
        c = x.rsplit(".", 1)[-1] if ("." in x and " " not in x and "(" not in x) else x
        if c not in out:
            out.append(c)
    return out


# --- 원본 ON 절 텍스트 ---

def _raw_on_map(tree: exp.Expression) -> dict[str, str]:
    """조인의 (오른쪽 테이블명 소문자) → 원본 ON 절 텍스트. 사용자 검색용."""
    m: dict[str, str] = {}
    for j in tree.find_all(exp.Join):
        on = j.args.get("on")
        if on is None:
            continue
        name = getattr(j.this, "name", "") or ""
        if name:
            m.setdefault(name.lower(), on.sql())
    return m


def _lookup_raw_on(raw_map: dict[str, str], tables: frozenset[str]) -> str:
    """테이블 집합 중 하나로 원본 ON 텍스트 조회(길면 축약)."""
    for t in sorted(tables):
        r = raw_map.get(t)
        if r:
            return (r[:200] + "…") if len(r) > 200 else r
    return ""


# --- 원본 WHERE/HAVING 술어 텍스트 (확인 필요 정보를 원문 그대로 노출) ---

def _split_and(cond: exp.Expression) -> list[exp.Expression]:
    """AND/괄호를 분해해 단위 술어 목록 반환(OR·단일은 그대로 한 단위)."""
    if isinstance(cond, exp.And):
        return _split_and(cond.this) + _split_and(cond.expression)
    if isinstance(cond, exp.Paren):
        return _split_and(cond.this)
    return [cond]


# 따옴표 구간(문자열 '…'·인용 식별자 "…"/`…`) — 대문자 변환에서 보존(케이스 민감 리터럴).
_QUOTE_SPAN_RE = re.compile(r"""'(?:[^']|'')*'|"[^"]*"|`[^`]*`""")


def _upper_disp(s: str) -> str:
    """따옴표 **밖**만 대문자(식별자·함수·키워드 통일). 문자열/인용식별자 리터럴은 원형 보존.

    A(Oracle)는 파싱 시 대문자 폴딩, B(Hive)는 소문자라 케이스가 어긋난다 → 표시를 모두
    대문자로 통일. 단 포맷마스크(`'yyyymmdd'`)·코드값(`'A0000'`) 등 따옴표 안은 바꾸지 않는다."""
    out: list[str] = []
    last = 0
    for m in _QUOTE_SPAN_RE.finditer(s):
        out.append(s[last:m.start()].upper())
        out.append(m.group(0))
        last = m.end()
    out.append(s[last:].upper())
    return "".join(out)


# --- 토큰 기반 리터럴 절 추출 (재렌더 정규화 회피 — 사용자가 쓴 그대로) ---

def _clause_unit_texts(sql: str, dialect: str, start_type, sep_type) -> list[str]:
    """원본 SQL 의 depth-0 절(start_type)을 **리터럴 단위** 텍스트로 슬라이스.

    토크나이저 위치(.start/.end)로 원문 그대로 잘라 `.sql()` 재렌더(방언별 SUBSTR↔SUBSTRING 스왑,
    to_date→STR_TO_DATE 등)를 피한다. 다음 depth-0 절 토큰 전까지 모아 sep_type 으로 분할.
    WHERE 의 AND 는 `BETWEEN … AND …` 의 AND 를 소비해 범위조건을 한 단위로 보존."""
    try:
        toks = sqlglot.tokenize(sql, dialect=dialect or None)
    except Exception:
        return []
    depth = 0
    si = None
    for i, t in enumerate(toks):
        if t.token_type == TokenType.L_PAREN:
            depth += 1
        elif t.token_type == TokenType.R_PAREN:
            depth -= 1
        elif depth == 0 and t.token_type == start_type:
            si = i + 1
            break
    if si is None:
        return []
    units: list[list] = []
    cur: list = []
    depth = 0
    between = 0
    for t in toks[si:]:
        tt = t.token_type
        if tt == TokenType.L_PAREN:
            depth += 1
            cur.append(t)
        elif tt == TokenType.R_PAREN:
            depth -= 1
            cur.append(t)
        elif depth == 0 and tt in _CLAUSE_BOUND_TYPES:
            break
        elif depth == 0 and tt == TokenType.BETWEEN:
            between += 1
            cur.append(t)
        elif depth == 0 and tt == sep_type:
            if sep_type == TokenType.AND and between > 0:
                between -= 1            # BETWEEN 내부 AND — 분리하지 않음
                cur.append(t)
            elif cur:
                units.append(cur)
                cur = []
        else:
            cur.append(t)
    if cur:
        units.append(cur)
    return [sql[u[0].start:u[-1].end + 1].strip() for u in units if u]


def _frag_cols(unit: str, dialect: str) -> set[str]:
    """리터럴 단위를 재파싱해 컬럼명(lower) 추출(키잉 전용 — 렌더 아님)."""
    try:
        node = sqlglot.parse_one(unit, dialect=dialect or None)
    except Exception:
        return set()
    return {c.name.lower() for c in node.find_all(exp.Column) if c.name}


def _strip_alias_text(unit: str, dialect: str) -> str:
    """SELECT 단위의 **출력 별칭**(`… 요청API`/`AS x`)을 제거 — 표시는 식만."""
    try:
        node = sqlglot.parse_one(unit, dialect=dialect or None)
    except Exception:
        return unit
    if isinstance(node, exp.Alias) and node.alias:
        pat = re.compile(
            r"""\s+(?:AS\s+)?[`"\[]?""" + re.escape(node.alias) + r"""[`"\]]?\s*$""",
            re.IGNORECASE,
        )
        return pat.sub("", unit).strip() or unit
    return unit


@dataclass
class _RawSrc:
    """원문 절 단위 색인(표시용) — 별칭 포함. 비교(canonical)와 별개.

    col_map: 컬럼 → [원문 단위(별칭 포함)]; norm_map: 정규형 → 원문 단위(컬럼 없는 집계용);
    order: 원문 단위 → 소스 절 내 순서 인덱스(원문 순서 보존)."""
    col_map: dict[str, list[str]] = field(default_factory=dict)
    norm_map: dict[str, str] = field(default_factory=dict)
    order: dict[str, int] = field(default_factory=dict)


_WS_RE = re.compile(r"\s+")


def _norm_sig(s: str) -> str:
    """컬럼 없는 집계(`count(*)`/`count(1)`) 매칭용 정규형 — 대문자·공백 제거."""
    return _WS_RE.sub("", s).upper()


def _build_rawsrc(units: list[str], dialect: str) -> _RawSrc:
    """원문 단위 목록(별칭 포함, **소스 순서대로**)을 컬럼·정규형·순서 색인으로.

    키잉·정규형은 내부적으로 별칭을 떼고(`_strip_alias_text`) 식만 사용 — 표시는 별칭 포함 원문."""
    src = _RawSrc()
    for i, full in enumerate(units):
        src.order.setdefault(full, i)
        expr = _strip_alias_text(full, dialect)
        for c in _frag_cols(expr, dialect):
            lst = src.col_map.setdefault(c, [])
            if full not in lst:
                lst.append(full)
        src.norm_map.setdefault(_norm_sig(expr), full)
    return src


def _prep(sql: str) -> str:
    """파싱과 동일한 전처리(템플릿 변수 등) 후 세미콜론 제거 — 위치 정합."""
    from query_diff.validation_service import _preprocess_sql

    return _preprocess_sql(sql.rstrip().rstrip(";"))


def _raw_predicate_map(sql: str, dialect: str = "") -> _RawSrc:
    """원본 WHERE/HAVING 술어 **리터럴** 색인(`tah.request_dt BETWEEN … AND …` 보존)."""
    s = _prep(sql)
    units = (
        _clause_unit_texts(s, dialect, TokenType.WHERE, TokenType.AND)
        + _clause_unit_texts(s, dialect, TokenType.HAVING, TokenType.AND)
    )
    return _build_rawsrc(units, dialect)


def _raw_select_map(sql: str, dialect: str = "") -> _RawSrc:
    """원본 SELECT 식 **리터럴** 색인(**출력 별칭 포함**, 순서 보존) — projection·집계 표시용."""
    s = _prep(sql)
    units = _clause_unit_texts(s, dialect, TokenType.SELECT, TokenType.COMMA)
    return _build_rawsrc(units, dialect)


def _raw_group_map(sql: str, dialect: str = "") -> _RawSrc:
    """원본 GROUP BY 식 **리터럴** 색인. 위치참조(`group by 1,2,3`)는 해당 SELECT 식(별칭 포함)으로 해소."""
    s = _prep(sql)
    sel = _clause_unit_texts(s, dialect, TokenType.SELECT, TokenType.COMMA)
    out: list[str] = []
    for u in _clause_unit_texts(s, dialect, TokenType.GROUP_BY, TokenType.COMMA):
        k = u.strip()
        if k.isdigit() and 1 <= int(k) <= len(sel):
            out.append(sel[int(k) - 1])     # 위치참조 → SELECT 식(별칭 포함)
        else:
            out.append(u)
    return _build_rawsrc(out, dialect)


def _orig_text(canon_items: list[str], src: _RawSrc | None) -> list[str]:
    """canonical 차이 항목 → **원문 텍스트(별칭 포함·원문 순서·대문자 통일)**.

    ①차이 컬럼→col_map ②(컬럼 없는 집계)정규형→norm_map ③폴백(토큰이면 컬럼참조 — `⟨…⟩` 미노출).
    모은 단위를 소스 순서로 정렬 후 대문자화(한글 별칭·따옴표 안 리터럴은 보존)."""
    found: list[str] = []
    seen: set[str] = set()
    for it in canon_items:
        refs = _ref_cols([it])
        units: list[str] = []
        if src is not None:
            for c in (_bare(x) for x in refs):
                units += src.col_map.get(c, [])
            if not units:
                u = src.norm_map.get(_norm_sig(it))
                if u:
                    units = [u]
        if not units:
            units = refs if "⟨" in it else [it]
        for u in units:
            if u not in seen:
                seen.add(u)
                found.append(u)
    if src is not None:
        found.sort(key=lambda u: src.order.get(u, 1_000_000))
    return [_upper_disp(u) for u in found]


# --- 조인 엣지 앵커-무관 그룹핑 ---

def _edge_tables(e: JoinEdge) -> frozenset[str]:
    """엣지의 테이블 집합(앵커 무관). 조인 그래프는 등치 조인 키로 정의 — CASE/함수 값
    표현식 안의 테이블 참조는 제외(`models._edge_table_set`). ON 빈약하면 left/right 보강."""
    return frozenset(_edge_table_set(e.on_predicates, e.left_table, e.right_table))


def _group_edges(edges: list[JoinEdge]) -> dict[tuple, set[str]]:
    """(테이블집합, join_type) → ON predicate 합집합."""
    g: dict[tuple, set[str]] = {}
    for e in edges:
        key = (_edge_tables(e), e.join_type)
        g.setdefault(key, set()).update(e.on_predicates)
    return g
