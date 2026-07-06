"""AST 정규화 및 CanonicalQuery 추출

Oracle/Hive 방언 차이를 흡수하여 절 단위로 비교 가능한 canonical form을 만든다.
- identifier: lower-case, 테이블 alias 해소
- 함수 동의어: NVL↔COALESCE, SUBSTR↔SUBSTRING, TRUNC↔DATE_TRUNC 등 표준화
- WHERE/HAVING: AND 분해 후 predicate 집합으로 보관 (순서 무관)
- 리터럴: 문자열/숫자 보존, 날짜 포맷은 원형 유지
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import sqlglot
from sqlglot import exp

# 순수 숫자 문자열(Oracle 의 따옴표 붙은 숫자) 판정 — 분석계 숫자 리터럴과 동치 흡수용
_NUM_STR_RE = re.compile(r"^-?\d+(\.\d+)?$")

from query_diff.structure_diff.schema_mapping import OpAnMap, translate_op_to_an
from query_diff.validation_service import _preprocess_sql

# 함수 동의어 — Oracle ↔ Hive/ANSI 표준으로 정규화
_FUNCTION_ALIASES: dict[str, str] = {
    "NVL": "COALESCE",
    "NVL2": "COALESCE",
    "IFNULL": "COALESCE",
    "SUBSTR": "SUBSTRING",
    "LENGTH": "LENGTH",
    "LEN": "LENGTH",
    "TO_CHAR": "CAST_STR",
    "TO_DATE": "CAST_DATE",
    # sqlglot이 방언별 날짜 파싱을 다른 노드로 전사한다(Oracle to_date→StrToDate,
    # Hive to_timestamp→Anonymous 'to_timestamp'). 모두 CAST_DATE로 모아 값 인자만 남긴다.
    "STR_TO_DATE": "CAST_DATE",
    "STR_TO_TIME": "CAST_DATE",
    "TO_TIMESTAMP": "CAST_DATE",
    "TS_OR_DS_TO_DATE": "CAST_DATE",
    "TS_OR_DS_TO_TIMESTAMP": "CAST_DATE",
    "TO_NUMBER": "CAST_NUM",
    "DATE_FORMAT": "CAST_STR",
    "UNIX_TIMESTAMP": "UNIX_TIMESTAMP",
    "SYSDATE": "CURRENT_TIMESTAMP",
    "CURRENT_DATE": "CURRENT_DATE",
    "CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",
}

# 타입 강제 코어션 함수 — 조인/비교에선 운영(to_char) vs 분석(무캐스트) 차이를 흡수하기 위해
# 내부 인자로 언랩한다(예: to_char(id) ≡ id).
_CAST_COERCIONS = {"CAST_STR", "CAST_DATE", "CAST_NUM"}

# --- 연-월(날짜 prefix) 추출 관용구 인식 ---
# A(Oracle) `substr(dt,0,6)` ↔ B(Hive) `from_timestamp(dt,'yyyyMM')` 처럼 컬럼 타입이 달라
# 추출 방식이 다른 같은 연-월(YYYYMM) 추출을 하나의 토큰으로 모은다. gran 을 토큰에 넣어
# 연/월/일 입도가 다르면 매칭되지 않게 한다. 토큰에 YEAR_MONTH_MARK 가 있으면 비교기가
# '제한적 판정'(소프트 동치)으로 표기한다 — substr 은 컬럼 문자열 표현에 의존하기 때문.
YEAR_MONTH_MARK = "⟨YM:"

# 마스크를 받아 날짜 포맷을 만드는 함수들(시간 성분 없는 순수 날짜 마스크일 때만 흡수).
_DATE_FORMAT_FUNCS = {
    "TO_CHAR", "DATE_FORMAT", "TIME_TO_STR",
    "FROM_TIMESTAMP", "FROM_UNIXTIME", "UNIX_TO_STR",
}
# 날짜 코어션 래퍼(예: hive date_format 의 this=TimeStrToTime(col)) — 벗겨 베이스 컬럼 도달.
_DATE_COERCION_NAMES = {
    "TIME_STR_TO_TIME", "STR_TO_TIME", "TS_OR_DS_TO_DATE",
    "TS_OR_DS_TO_TIMESTAMP", "CAST_DATE", "STR_TO_DATE", "TO_TIMESTAMP",
}
_DATE_WIDTH_GRAN = {4: "YEAR", 6: "MONTH", 8: "DAY"}


def _date_gran_from_mask(mask: str) -> str | None:
    """날짜 포맷 마스크 → 'YEAR'|'MONTH'|'DAY'|None.

    strftime(`%Y%m`)·Oracle(`YYYYMM`)·raw(`yyyyMM`) 모두 처리. **시간 성분(HH·MI·SS·%H…)이
    있으면 None**(연-월 절단이 아니므로 흡수하지 않음). 연도 성분이 없어도 None.
    """
    m = mask.strip().strip("'\"")
    if not m:
        return None
    if "%" in m:  # strftime
        comps = set(re.findall(r"%[A-Za-z]", m))
        if comps & {"%H", "%I", "%M", "%S", "%p", "%T", "%R", "%f"}:
            return None
        has_y = bool(comps & {"%Y", "%y"})
        has_mon = bool(comps & {"%m", "%b", "%B"})
        has_day = bool(comps & {"%d", "%e", "%j"})
    else:  # Oracle/raw 포맷 코드
        u = m.upper()
        if re.search(r"HH|MI|SS|FF|AM|PM", u):
            return None
        has_y = ("YYYY" in u) or ("YY" in u) or ("RR" in u)
        has_mon = ("MM" in u) or ("MON" in u)
        has_day = "DD" in u
    if not has_y:
        return None
    return "DAY" if has_day else ("MONTH" if has_mon else "YEAR")


def _func_real_name(node: exp.Func) -> str:
    """함수 실명(대문자). 익명 함수(hive from_timestamp 등)는 sql_name 이 ANONYMOUS 라 node.name 사용."""
    if isinstance(node, exp.Anonymous):
        return (node.name or "").upper()
    return (node.sql_name() or type(node).__name__).upper()


def _strip_date_coercion(node: exp.Expression) -> exp.Expression:
    """TimeStrToTime 등 날짜 코어션 래퍼를 `.this` 로 벗겨 베이스 컬럼/식에 도달."""
    for _ in range(5):
        if not isinstance(node, exp.Func):
            break
        inner = node.args.get("this")
        if _func_real_name(node) in _DATE_COERCION_NAMES and isinstance(inner, exp.Expression):
            node = inner
        else:
            break
    return node


def _recognize_date_trunc_idiom(
    node: exp.Func, alias_map: dict[str, str]
) -> str | None:
    """연-월(날짜 prefix) 추출 관용구면 `⟨YM:{col}:{gran}⟩` 토큰, 아니면 None.

    위치 기반: `substr(col, 0|1, {4,6,8})`(첫 N자). 포맷 기반: to_char/date_format/
    from_timestamp/from_unixtime(col, '…yyyyMM…'). 두 계열 모두 동일 토큰으로 모인다.
    """
    # 위치 기반 — substr(col, start, length)
    if isinstance(node, exp.Substring):
        start, length = node.args.get("start"), node.args.get("length")
        if (
            isinstance(start, exp.Literal) and not start.is_string
            and isinstance(length, exp.Literal) and not length.is_string
        ):
            try:
                s, ln = int(start.name), int(length.name)
            except ValueError:
                return None
            gran = _DATE_WIDTH_GRAN.get(ln)
            if s in (0, 1) and gran and isinstance(node.this, exp.Expression):
                return f"{YEAR_MONTH_MARK}{_canonical_expr(node.this, alias_map)}:{gran}⟩"
        return None

    # 포맷 기반 — (col, mask) 인자
    name = _func_real_name(node)
    if name not in _DATE_FORMAT_FUNCS:
        return None
    if isinstance(node, exp.Anonymous):
        exprs = list(node.expressions or [])
        col = exprs[0] if exprs else None
        mask = exprs[1] if len(exprs) >= 2 else None
    else:
        col = node.args.get("this")
        mask = node.args.get("format")
    if not (isinstance(col, exp.Expression) and isinstance(mask, exp.Literal) and mask.is_string):
        return None
    gran = _date_gran_from_mask(mask.name)
    if gran is None:
        return None
    base = _strip_date_coercion(col)
    return f"{YEAR_MONTH_MARK}{_canonical_expr(base, alias_map)}:{gran}⟩"


@dataclass(frozen=True)
class CanonicalTable:
    name: str           # 스키마 제외한 순수 테이블명 (lower)
    raw: str            # 원문 (오류 메시지용)


@dataclass(frozen=True)
class CanonicalJoin:
    join_type: str              # INNER, LEFT, RIGHT, FULL, CROSS
    right_table: str            # canonical name
    right_alias: str            # 원본 alias (구분용, 정규화는 lower-case)
    on_predicates: tuple[str, ...]  # sorted canonical predicate strings


@dataclass(frozen=True)
class CanonicalProjection:
    expression: str     # canonical string
    is_aggregate: bool
    agg_function: str = ""    # 집계 함수명 (정규화됨). 비집계는 빈 문자열
    agg_arg: str = ""         # 집계 인자 canonical string


@dataclass
class CanonicalQuery:
    dialect: str
    projections: list[CanonicalProjection] = field(default_factory=list)
    from_tables: list[CanonicalTable] = field(default_factory=list)
    joins: list[CanonicalJoin] = field(default_factory=list)
    where_predicates: list[str] = field(default_factory=list)   # AND-decomposed, sorted
    group_by: list[str] = field(default_factory=list)           # sorted canonical
    having_predicates: list[str] = field(default_factory=list)
    alias_to_table: dict[str, str] = field(default_factory=dict)


# --- 식별자/표현식 정규화 ---

def _strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "`"):
        return s[1:-1]
    return s


def _norm_ident(name: str) -> str:
    return _strip_quotes(name).lower()


def _split_schema(qualified: str) -> str:
    return _norm_ident(qualified.rsplit(".", 1)[-1])


def _normalize_function_name(name: str) -> str:
    up = name.upper()
    return _FUNCTION_ALIASES.get(up, up)


def _canonical_expr(node: exp.Expression | None, alias_map: dict[str, str]) -> str:
    """AST 노드를 dialect-neutral canonical 문자열로 변환.

    - 식별자 lower-case, 테이블 alias 해소
    - 함수명 동의어 정규화
    - 커뮤니터티브 연산자(=, <>, AND, OR)는 피연산자 정렬
    """
    if node is None:
        return ""

    if isinstance(node, exp.Column):
        table = ""
        if node.table:
            t = _norm_ident(node.table)
            table = alias_map.get(t, t)
        col = _norm_ident(node.name)
        return f"{table}.{col}" if table else col

    if isinstance(node, exp.Literal):
        if node.is_string:
            # 운영(Oracle)은 숫자에 따옴표 허용('99'), 분석(Hive/Impala)은 불가(99) — 같은 값.
            # 순수 숫자 문자열은 따옴표를 떼 숫자 리터럴과 동일 표기로 흡수.
            if _NUM_STR_RE.match(node.this):
                return node.this
            return f"'{node.this}'"
        return str(node.this)

    if isinstance(node, exp.Boolean):
        return "TRUE" if node.this else "FALSE"

    if isinstance(node, exp.Null):
        return "NULL"

    if isinstance(node, exp.Star):
        return "*"

    if isinstance(node, exp.Alias):
        return _canonical_expr(node.this, alias_map)

    if isinstance(node, exp.Cast):
        inner = _canonical_expr(node.this, alias_map)
        to = node.to.sql().upper() if node.to else ""
        return f"CAST({inner} AS {to})"

    if isinstance(node, (exp.EQ, exp.NEQ)):
        left = _canonical_expr(node.left, alias_map)
        right = _canonical_expr(node.right, alias_map)
        # NULL ≡ '' : 운영계(NULL) vs 분석계(빈문자열) 저장 엔진 차이를 동치로 흡수.
        # `col = ''` → `col IS NULL`, `col <> ''` → `col IS NOT NULL`.
        if left == "''" or right == "''":
            other = right if left == "''" else left
            return (
                f"{other} IS NULL"
                if isinstance(node, exp.EQ)
                else f"{other} IS NOT NULL"
            )
        op = "=" if isinstance(node, exp.EQ) else "<>"
        a, b = sorted([left, right])
        return f"{a} {op} {b}"

    if isinstance(node, (exp.GT, exp.LT, exp.GTE, exp.LTE)):
        # 방향 보존 (대칭 아님)
        op_map = {exp.GT: ">", exp.LT: "<", exp.GTE: ">=", exp.LTE: "<="}
        op = op_map[type(node)]
        return f"{_canonical_expr(node.left, alias_map)} {op} {_canonical_expr(node.right, alias_map)}"

    if isinstance(node, exp.Is):
        left = _canonical_expr(node.this, alias_map)
        right = _canonical_expr(node.expression, alias_map)
        return f"{left} IS {right}"

    if isinstance(node, exp.In):
        left = _canonical_expr(node.this, alias_map)
        items = [_canonical_expr(e, alias_map) for e in (node.expressions or [])]
        return f"{left} IN ({', '.join(sorted(items))})"

    if isinstance(node, exp.Between):
        expr = _canonical_expr(node.this, alias_map)
        low = _canonical_expr(node.args.get("low"), alias_map)
        high = _canonical_expr(node.args.get("high"), alias_map)
        return f"{expr} BETWEEN {low} AND {high}"

    if isinstance(node, exp.Like):
        left = _canonical_expr(node.this, alias_map)
        right = _canonical_expr(node.expression, alias_map)
        return f"{left} LIKE {right}"

    if isinstance(node, exp.And):
        parts = sorted([_canonical_expr(c, alias_map) for c in node.flatten()])
        return " AND ".join(parts)

    if isinstance(node, exp.Or):
        parts = sorted([_canonical_expr(c, alias_map) for c in node.flatten()])
        return "(" + " OR ".join(parts) + ")"

    if isinstance(node, exp.Not):
        inner = node.this
        # `col IS NOT NULL` (= NOT col IS NULL) 표준형
        if isinstance(inner, exp.Is) and isinstance(inner.expression, exp.Null):
            return f"{_canonical_expr(inner.this, alias_map)} IS NOT NULL"
        return f"NOT {_canonical_expr(node.this, alias_map)}"

    if isinstance(node, exp.Paren):
        return _canonical_expr(node.this, alias_map)

    # CASE/DECODE 정규화 — exp.Case·exp.DecodeCase 는 exp.Func 의 서브클래스이므로
    # 반드시 Func 분기보다 **앞에서** 처리해야 한다(아니면 Func 분기가 가로채 WHEN/THEN 손실).
    if isinstance(node, (exp.Case, exp.DecodeCase)):
        return _canonical_conditional(node, alias_map)

    # 연-월(날짜 prefix) 추출 관용구 — CAST 언랩(아래)보다 **앞**이어야 to_char 의 포맷
    # 마스크가 버려지지 않는다(substr↔from_timestamp↔to_char 를 한 토큰으로 모음).
    if isinstance(node, exp.Func):
        ym = _recognize_date_trunc_idiom(node, alias_map)
        if ym is not None:
            return ym

    if isinstance(node, exp.Func):
        # 익명 함수(예: hive to_timestamp)는 sql_name()이 'ANONYMOUS' 라 실제 이름을 잃는다.
        # 실명(node.name)으로 정규화해 동의어/언랩이 동작하게 한다.
        if isinstance(node, exp.Anonymous):
            fname = _normalize_function_name(node.name)
        else:
            fname = _normalize_function_name(node.sql_name() or type(node).__name__)
        # 타입 코어션(to_char/날짜 파싱 등)은 조인/비교에서 무시 — 값 인자로 언랩
        if fname in _CAST_COERCIONS:
            # 익명 함수는 인자가 expressions 에, 일반 노드는 this 에 있다.
            if isinstance(node, exp.Anonymous):
                inner = node.expressions[0] if node.expressions else None
            else:
                inner = node.args.get("this")
            if isinstance(inner, exp.Expression):
                return _canonical_expr(inner, alias_map)
        args = [_canonical_expr(a, alias_map) for a in node.args.values() if isinstance(a, exp.Expression)]
        # 가변 인자 (expressions 리스트)
        if "expressions" in node.args and isinstance(node.args["expressions"], list):
            args = [_canonical_expr(a, alias_map) for a in node.args["expressions"]]
        return f"{fname}({', '.join(args)})"

    if isinstance(node, exp.Distinct):
        parts = [_canonical_expr(e, alias_map) for e in (node.expressions or [])]
        return f"DISTINCT {', '.join(parts)}"

    if isinstance(node, (exp.Add, exp.Sub, exp.Mul, exp.Div)):
        op_map = {exp.Add: "+", exp.Sub: "-", exp.Mul: "*", exp.Div: "/"}
        op = op_map[type(node)]
        left = _canonical_expr(node.left, alias_map)
        right = _canonical_expr(node.right, alias_map)
        if isinstance(node, (exp.Add, exp.Mul)):
            a, b = sorted([left, right])
            return f"({a} {op} {b})"
        return f"({left} {op} {right})"

    # fallback: sqlglot 기본 SQL 직렬화 후 lower-case
    return node.sql().lower()


def _display_expr(node: exp.Expression | None, alias_map: dict[str, str]) -> str:
    """표시용 자연형 술어. 비교용 `_canonical_expr` 와 **같은 이름 해소·리터럴 정규화**를 쓰되,
    사람이 원 쿼리와 대조하기 쉽도록:
    - EQ/NEQ 피연산자를 **정렬하지 않고**(작성 순서 = `컬럼 op 값`), 연산자를 `=`/`!=` 로 표기
      (canonical 은 정렬 + `<>` 로 정규화 — 매칭 전용).
    NULL≡'' 흡수, IN 목록 정렬, GT/LT·IS·LIKE·컬럼·리터럴 등은 canonical 과 동일(위임).
    """
    if isinstance(node, (exp.EQ, exp.NEQ)):
        left = _canonical_expr(node.left, alias_map)
        right = _canonical_expr(node.right, alias_map)
        # NULL ≡ '' 는 canonical 과 동일 처리(운영 NULL ↔ 분석 빈문자열 동치).
        if left == "''" or right == "''":
            other = right if left == "''" else left
            return (
                f"{other} IS NULL"
                if isinstance(node, exp.EQ)
                else f"{other} IS NOT NULL"
            )
        op = "=" if isinstance(node, exp.EQ) else "!="
        return f"{left} {op} {right}"
    if isinstance(node, exp.Or):
        parts = [_display_expr(c, alias_map) for c in node.flatten()]
        return "(" + " OR ".join(parts) + ")"
    return _canonical_expr(node, alias_map)


def _canonical_conditional(
    node: exp.Expression, alias_map: dict[str, str]
) -> str:
    """DECODE / CASE(단순·검색형)를 단일 **검색형 CASE** canonical 로 정규화.

    `DECODE(op, v1,r1, v2,r2, …, d)` ≡ `CASE op WHEN v1 THEN r1 … ELSE d END`
    ≡ `CASE WHEN op=v1 THEN r1 … ELSE d END`. 작성 방언(DECODE vs CASE WHEN)이
    달라도 같은 조건→결과 매핑이면 같게 본다.

    - 조건의 `op = v` 는 기존 EQ 정규화를 재사용(exp.EQ 노드를 만들어 `_canonical_expr`
      호출 → NULL≡'' 흡수·피연산자 정렬 일관).
    - WHEN 순서는 **보존**(검색형 CASE 는 첫 일치 우선이라 순서가 의미를 가짐 → 정렬 금지).
    """
    whens: list[tuple[str, str]] = []
    default: exp.Expression | None = None

    if isinstance(node, exp.DecodeCase):
        exprs = list(node.expressions or [])
        if exprs:
            operand = exprs[0]
            rest = exprs[1:]
            i = 0
            while i + 1 < len(rest):
                cond = _canonical_expr(
                    exp.EQ(this=operand.copy(), expression=rest[i].copy()), alias_map
                )
                whens.append((cond, _canonical_expr(rest[i + 1], alias_map)))
                i += 2
            if i < len(rest):  # 인자가 홀수면 마지막은 default
                default = rest[i]
    else:  # exp.Case — 단순(this=피연산자) / 검색형(this=None)
        operand = node.args.get("this")
        for ifs in node.args.get("ifs", []) or []:
            if operand is not None:
                cond = _canonical_expr(
                    exp.EQ(this=operand.copy(), expression=ifs.this.copy()), alias_map
                )
            else:
                cond = _canonical_expr(ifs.this, alias_map)
            whens.append((cond, _canonical_expr(ifs.args.get("true"), alias_map)))
        default = node.args.get("default")

    parts = [f"WHEN {c} THEN {t}" for c, t in whens]
    if default is not None:
        parts.append(f"ELSE {_canonical_expr(default, alias_map)}")
    return "CASE " + " ".join(parts) + " END"


# --- 절별 추출 ---

_AGG_FUNCTIONS = {
    "SUM", "COUNT", "AVG", "MIN", "MAX", "STDDEV", "VARIANCE",
    "COLLECT_LIST", "COLLECT_SET", "APPROX_DISTINCT",
}


def _is_aggregate(node: exp.Expression) -> tuple[bool, str, str, dict[str, str]]:
    """집계 함수 여부 및 (함수명, 인자 canonical) 반환. alias_map은 호출 측에서 주입."""
    # 실제 추출은 extract_canonical에서 수행하므로 여기선 단순 판정
    for func in node.find_all(exp.Func):
        fname = _normalize_function_name(func.sql_name() or type(func).__name__)
        if fname in _AGG_FUNCTIONS:
            return True, fname, "", {}
    return False, "", "", {}


def _build_alias_map(tree: exp.Expression) -> dict[str, str]:
    """FROM/JOIN 절의 alias → 실제 테이블명 매핑. 전부 lower-case."""
    alias_map: dict[str, str] = {}
    for tbl in tree.find_all(exp.Table):
        table_name = _norm_ident(tbl.name)
        alias = tbl.alias_or_name
        if alias:
            alias_map[_norm_ident(alias)] = table_name
        alias_map[table_name] = table_name
    return alias_map


def _extract_projections(
    select: exp.Select, alias_map: dict[str, str]
) -> list[CanonicalProjection]:
    projections: list[CanonicalProjection] = []
    for proj in select.expressions:
        base = proj.this if isinstance(proj, exp.Alias) else proj
        expr_str = _canonical_expr(proj, alias_map)

        agg_func = ""
        agg_arg = ""
        is_agg = False
        for func in base.find_all(exp.Func):
            fname = _normalize_function_name(func.sql_name() or type(func).__name__)
            if fname in _AGG_FUNCTIONS:
                is_agg = True
                agg_func = fname
                # 첫 번째 expression 인자 canonical
                if "this" in func.args and isinstance(func.args["this"], exp.Expression):
                    agg_arg = _canonical_expr(func.args["this"], alias_map)
                elif "expressions" in func.args and func.args["expressions"]:
                    agg_arg = _canonical_expr(func.args["expressions"][0], alias_map)
                break

        projections.append(
            CanonicalProjection(
                expression=expr_str,
                is_aggregate=is_agg,
                agg_function=agg_func,
                agg_arg=agg_arg,
            )
        )
    return projections


def _extract_from_tables(select: exp.Select) -> list[CanonicalTable]:
    tables: list[CanonicalTable] = []
    from_clause = select.args.get("from_")
    if from_clause:
        for tbl in from_clause.find_all(exp.Table):
            tables.append(
                CanonicalTable(name=_norm_ident(tbl.name), raw=tbl.sql())
            )

    # 콤마 구분 FROM (FROM t1, t2)은 sqlglot이 ON 없는 Join으로 파싱한다.
    # 이 경우 JOIN이 아닌 추가 from 테이블로 간주한다.
    for join in select.args.get("joins", []) or []:
        if join.args.get("on") is None and not (join.args.get("side") or join.args.get("kind")):
            inner = join.this
            if isinstance(inner, exp.Table):
                tables.append(
                    CanonicalTable(name=_norm_ident(inner.name), raw=inner.sql())
                )

    return tables


def _extract_joins(
    select: exp.Select, alias_map: dict[str, str]
) -> list[CanonicalJoin]:
    joins: list[CanonicalJoin] = []
    for join in select.args.get("joins", []) or []:
        # ON 없고 side/kind도 없는 콤마-조인은 from_tables로 이미 처리했으므로 skip
        if join.args.get("on") is None and not (join.args.get("side") or join.args.get("kind")):
            continue
        # join_type 결정
        side = (join.args.get("side") or "").upper()
        kind = (join.args.get("kind") or "").upper()
        if "CROSS" in kind:
            jtype = "CROSS"
        elif side in ("LEFT", "RIGHT", "FULL"):
            jtype = side
        else:
            jtype = "INNER"

        right_tbl = ""
        right_alias = ""
        inner_tbl = join.this
        if isinstance(inner_tbl, exp.Table):
            right_tbl = _norm_ident(inner_tbl.name)
            alias_raw = inner_tbl.alias_or_name
            if alias_raw and _norm_ident(alias_raw) != right_tbl:
                right_alias = _norm_ident(alias_raw)

        on_expr = join.args.get("on")
        predicates: list[str] = []
        if on_expr is not None:
            # AND 분해
            for part in _split_and(on_expr):
                predicates.append(_canonical_expr(part, alias_map))

        joins.append(
            CanonicalJoin(
                join_type=jtype,
                right_table=right_tbl,
                right_alias=right_alias,
                on_predicates=tuple(sorted(predicates)),
            )
        )
    return joins


def _split_and(node: exp.Expression) -> list[exp.Expression]:
    """AND로 연결된 predicate를 개별 expression으로 분해.

    `x BETWEEN low AND high` 는 `x >= low` + `x <= high` 로 확장해, 작성 스타일이
    BETWEEN이든 부등호든 같은 형태로 비교되게 한다.
    """
    if isinstance(node, exp.And):
        left = _split_and(node.left)
        right = _split_and(node.right)
        return left + right
    if isinstance(node, exp.Paren):
        return _split_and(node.this)
    if isinstance(node, exp.Between):
        this = node.this
        low = node.args.get("low")
        high = node.args.get("high")
        if this is not None and low is not None and high is not None:
            return [
                exp.GTE(this=this.copy(), expression=low.copy()),
                exp.LTE(this=this.copy(), expression=high.copy()),
            ]
    return [node]


def _extract_where(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    where = select.args.get("where")
    if where is None:
        return []
    condition = where.this
    parts = [_canonical_expr(p, alias_map) for p in _split_and(condition)]
    return sorted(parts)


def _extract_group_by(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    group = select.args.get("group")
    if group is None:
        return []
    return sorted([_canonical_expr(e, alias_map) for e in group.expressions])


def _extract_having(
    select: exp.Select, alias_map: dict[str, str]
) -> list[str]:
    having = select.args.get("having")
    if having is None:
        return []
    return sorted([_canonical_expr(p, alias_map) for p in _split_and(having.this)])


def extract_canonical(
    sql: str, dialect: str, op_an: OpAnMap | None = None
) -> CanonicalQuery:
    """SQL 문자열을 파싱하여 CanonicalQuery로 변환.

    validation과 동일한 `_preprocess_sql`을 적용하여 템플릿 변수(`${...}`) 등으로
    인한 파싱 불일치를 방지한다.

    op_an 가 주어지면(운영 쿼리 측) 파싱 직후 운영→분석 식별자 번역을 적용해
    분석 네임스페이스로 정규화한다.
    """
    preprocessed = _preprocess_sql(sql.rstrip().rstrip(";"))
    parsed = sqlglot.parse(preprocessed, dialect=dialect)
    if not parsed or parsed[0] is None:
        raise ValueError("파싱 결과가 비어 있습니다.")
    tree = parsed[0]

    if op_an is not None:
        tree, _rename = translate_op_to_an(tree, op_an)

    # 최상위 SELECT 찾기
    top_select = tree if isinstance(tree, exp.Select) else tree.find(exp.Select)
    if top_select is None:
        raise ValueError("SELECT 문을 찾을 수 없습니다.")

    alias_map = _build_alias_map(top_select)

    return CanonicalQuery(
        dialect=dialect,
        projections=_extract_projections(top_select, alias_map),
        from_tables=_extract_from_tables(top_select),
        joins=_extract_joins(top_select, alias_map),
        where_predicates=_extract_where(top_select, alias_map),
        group_by=_extract_group_by(top_select, alias_map),
        having_predicates=_extract_having(top_select, alias_map),
        alias_to_table=alias_map,
    )
