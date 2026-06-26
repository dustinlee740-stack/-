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

from sqlglot import exp

from query_diff.models import JoinEdge, _TABLE_REF_RE


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


def _absorb_parameterized(
    only_a: list[str], only_b: list[str]
) -> tuple[list[str], list[str], list[tuple[str, str]]]:
    """형태(shape)는 같고 **템플릿 변수(플레이스홀더)** 때문에만 다른 쌍을 흡수.

    날짜 범위(`>= ${start}`)·IN 목록(`IN (${bnf_id})`) 처럼 파라미터로 값만 다른 항목을
    하드 diff에서 분리한다. 양쪽 다 리터럴인데 값이 다르면(진짜 차이) 흡수하지 않는다.
    반환: (남은 A전용, 남은 B전용, 흡수된 (a,b) 쌍 목록).
    """
    rem_a = list(only_a)
    used_b: set[int] = set()
    absorbed: list[tuple[str, str]] = []
    for x in list(rem_a):
        sx = _shape(x)
        for j, y in enumerate(only_b):
            if j in used_b:
                continue
            if _shape(y) == sx and (_has_placeholder(x) or _has_placeholder(y)):
                used_b.add(j)
                absorbed.append((x, y))
                rem_a.remove(x)
                break
    rem_b = [y for j, y in enumerate(only_b) if j not in used_b]
    return rem_a, rem_b, absorbed


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


# --- 조인 엣지 앵커-무관 그룹핑 ---

def _edge_tables(e: JoinEdge) -> frozenset[str]:
    """엣지가 ON 에서 참조하는 테이블 집합(앵커 무관). ON 빈약하면 left/right 보강."""
    ts: set[str] = set()
    for p in e.on_predicates:
        ts.update(_TABLE_REF_RE.findall(p))
    if len(ts) < 2:
        ts.update(t for t in (e.left_table, e.right_table) if t)
    return frozenset(ts)


def _group_edges(edges: list[JoinEdge]) -> dict[tuple, set[str]]:
    """(테이블집합, join_type) → ON predicate 합집합."""
    g: dict[tuple, set[str]] = {}
    for e in edges:
        key = (_edge_tables(e), e.join_type)
        g.setdefault(key, set()).update(e.on_predicates)
    return g
