"""SQL 검증 서비스 — sqlglot 기반 파싱 및 구조 분석"""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp

from query_diff.models import (
    Dialect,
    QueryInput,
    QueryStructure,
    ValidationResult,
)

# sqlglot dialect 매핑
_DIALECT_MAP: dict[Dialect, str] = {
    Dialect.ORACLE: "oracle",
    Dialect.HIVE: "hive",
    Dialect.MYSQL: "mysql",
    Dialect.POSTGRES: "postgres",
}

# 방언 자동 감지 시도 순서
_DIALECT_FALLBACKS: list[Dialect] = [
    Dialect.ORACLE,
    Dialect.HIVE,
    Dialect.MYSQL,
    Dialect.POSTGRES,
]

# 방언 계열 매핑 (Hive SQL에 Oracle 제안 방지)
_DIALECT_FAMILY: dict[Dialect, set[Dialect]] = {
    Dialect.ORACLE: {Dialect.MYSQL, Dialect.POSTGRES},
    Dialect.HIVE: set(),
    Dialect.MYSQL: {Dialect.ORACLE, Dialect.POSTGRES},
    Dialect.POSTGRES: {Dialect.ORACLE, Dialect.MYSQL},
}

# --- SQL 전처리 ---

# 템플릿 변수 패턴: ${name=default} 또는 ${name}
_TEMPLATE_VAR_RE = re.compile(r"\$\{(\w+)(?:=([^}]*))?\}")

# en-dash/em-dash가 주석 마커로 잘못 쓰인 경우 (Word/Confluence 자동교정으로 '--'이 '–'로 변환됨)
# 공백으로 시작하거나 뒤에 공백이 오는 패턴만 수정 (문자열 내부 등 오탐 방지)
_WRONG_DASH_COMMENT_RE = re.compile(r"(^|\s)[–—](\s)", re.MULTILINE)

# 깨진 Oracle 힌트 (Word 등에서 '*'이 제거된 경우): /+full(it)/
_BROKEN_HINT_RE = re.compile(r"/\+[^/\n]*/")


def _preprocess_sql(sql: str) -> str:
    """sqlglot 파싱 전 전처리:
    1) en-dash/em-dash 주석 마커를 표준 '--'로 복구
    2) 깨진 Oracle 힌트 제거
    3) 템플릿 변수를 기본값 또는 플레이스홀더로 치환
    """
    # 1) 잘못된 대시 주석 복구
    sql = _WRONG_DASH_COMMENT_RE.sub(r"\1--\2", sql)

    # 2) 깨진 힌트 제거 (힌트는 optimizer 지시어라 구조 비교에 영향 없음)
    sql = _BROKEN_HINT_RE.sub(" ", sql)

    def _replace_var(m: re.Match) -> str:
        # 문자열 리터럴 내부인지 판단 — 앞쪽 작은따옴표 개수가 홀수면 리터럴 안.
        # 단일 글자 룩백(sql[start-1])은 `'%${V}%'`처럼 변수가 리터럴 **중간**에 있으면 오판하므로
        # 전체 앞부분 따옴표 패리티로 본다(이스케이프 ''는 2개로 세어져 패리티 보존).
        start = m.start()
        in_quotes = sql[:start].count("'") % 2 == 1
        default = m.group(2)
        if default is not None:
            stripped = default.strip()
            if stripped.isdigit():
                return stripped
            if in_quotes:
                return stripped  # 외부 따옴표가 있으므로 추가하지 않음
            return f"'{stripped}'"
        # 기본값 없음 — 외부 따옴표 문맥이면 따옴표를 덧붙이지 않아 이중화('') 방지
        return "__PLACEHOLDER__" if in_quotes else "'__PLACEHOLDER__'"

    return _TEMPLATE_VAR_RE.sub(_replace_var, sql)


# Oracle 바인드 파라미터 `:name`·`:1` (따옴표 밖). 앞이 단어문자/콜론이면 제외 —
# 시간형 `'12:34:56'`(따옴표 안이라 아래 in_quotes 로 걸러짐)·Postgres 캐스트 `x::text` 오손 방지.
_ORACLE_BIND_RE = re.compile(r"(?<![\w:]):(\w+)")


def _bind_value(raw: str, in_quotes: bool) -> str:
    """바인드 대입값 포맷 — 제공값의 바깥 따옴표 1겹을 벗기고 문맥별로 재인용.

    따옴표 안(`'${x}'`·리터럴 문맥)이면 bare 삽입, 밖이면 숫자는 bare·문자열은 `'…'`.
    → 사용자가 `'KMN…'`/`KMN…` 어느 쪽으로 입력해도 정상 SQL 이 된다.
    """
    v = str(raw).strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        v = v[1:-1]
    if v.lstrip("-").isdigit():
        return v
    return v if in_quotes else f"'{v}'"


def _apply_binds(sql: str, binds: dict[str, str] | None) -> str:
    """제공된 바인드값을 SQL 에 **치환**한다(1차 비교를 값-인식으로).

    - Hue `${name}`/`${name=default}` **및** Oracle `:name` 지원.
    - **제공된 이름만** 치환하고 나머지는 원문 유지 → 엔진 `_preprocess_sql` 이 미제공 `${}`→
      placeholder, `:name`→구조 인식(라운드10/11)으로 폴백 처리.
    - 문자열 리터럴 안/밖은 앞부분 작은따옴표 패리티로 판단(`_preprocess_sql` 과 동일 방식).
    """
    binds = {str(k): str(v) for k, v in (binds or {}).items()}
    if not binds:
        return sql

    def _tmpl(m: re.Match) -> str:
        name = m.group(1)
        if name not in binds:
            return m.group(0)
        in_q = sql[: m.start()].count("'") % 2 == 1
        return _bind_value(binds[name], in_q)

    out = _TEMPLATE_VAR_RE.sub(_tmpl, sql)

    def _ora(m: re.Match) -> str:
        name = m.group(1)
        if name not in binds:
            return m.group(0)
        in_q = out[: m.start()].count("'") % 2 == 1
        return _bind_value(binds[name], in_q)

    return _ORACLE_BIND_RE.sub(_ora, out)


def _count_nodes(tree: exp.Expression, node_type: type) -> int:
    return len(list(tree.find_all(node_type)))


def _extract_structure(tree: exp.Expression) -> QueryStructure:
    """AST에서 절별 구조 요약 추출"""
    select_cols = 0
    from_tables = 0
    joins = 0
    where_conds = 0
    group_by_cols = 0
    having_conds = 0
    order_by_cols = 0
    subqueries = 0

    # SELECT 절
    for select in tree.find_all(exp.Select):
        select_cols += len(select.expressions)

    # FROM 절
    for from_ in tree.find_all(exp.From):
        from_tables += len(list(from_.find_all(exp.Table)))

    # JOIN
    joins = _count_nodes(tree, exp.Join)

    # WHERE 조건 수 (AND로 분리)
    for where in tree.find_all(exp.Where):
        conditions = list(where.find_all(exp.And))
        if conditions:
            where_conds += len(conditions) + 1
        else:
            where_conds += 1

    # GROUP BY
    for group in tree.find_all(exp.Group):
        group_by_cols += len(group.expressions)

    # HAVING
    having_conds = _count_nodes(tree, exp.Having)

    # ORDER BY
    for order in tree.find_all(exp.Order):
        order_by_cols += len(order.expressions)

    # 서브쿼리 (중첩 SELECT - 최상위 제외)
    all_selects = list(tree.find_all(exp.Select))
    subqueries = max(0, len(all_selects) - 1)

    return QueryStructure(
        select_columns=select_cols,
        from_tables=from_tables,
        joins=joins,
        where_conditions=where_conds,
        group_by_columns=group_by_cols,
        having_conditions=having_conds,
        order_by_columns=order_by_cols,
        subqueries=subqueries,
    )


def validate_sql(sql: str, dialect: Dialect) -> ValidationResult:
    """SQL을 파싱하고 구조를 분석하여 ValidationResult 반환"""
    dialect_str = _DIALECT_MAP[dialect]
    preprocessed = _preprocess_sql(sql)

    # 1차: 지정된 방언으로 파싱 시도
    try:
        parsed = sqlglot.parse(preprocessed, dialect=dialect_str)
        if not parsed or parsed[0] is None:
            return ValidationResult(
                is_valid=False,
                error_message="SQL이 비어 있거나 파싱할 수 없습니다.",
            )

        tree = parsed[0]
        structure = _extract_structure(tree)

        return ValidationResult(
            is_valid=True,
            dialect_detected=dialect_str,
            structure=structure,
        )

    except sqlglot.errors.ParseError as e:
        error_msg = str(e)

        # 2차: 같은 계열 방언만 제안 (Hive SQL에 Oracle 제안 방지)
        candidates = _DIALECT_FAMILY.get(dialect, set())

        for fallback in candidates:
            try:
                fb_str = _DIALECT_MAP[fallback]
                fb_parsed = sqlglot.parse(preprocessed, dialect=fb_str)
                if fb_parsed and fb_parsed[0] is not None:
                    return ValidationResult(
                        is_valid=False,
                        error_message=error_msg,
                        suggestion=f"dialect을 '{fb_str}'(으)로 변경하면 파싱 가능합니다.",
                    )
            except sqlglot.errors.ParseError:
                continue

        return ValidationResult(
            is_valid=False,
            error_message=error_msg,
        )


def validate_query_input(query: QueryInput) -> ValidationResult:
    """QueryInput 객체를 검증"""
    if not query.sql_raw or not query.sql_raw.strip():
        return ValidationResult(
            is_valid=False,
            error_message="SQL이 입력되지 않았습니다.",
        )

    result = validate_sql(query.sql_raw, query.dialect)

    # 검증 결과를 QueryInput에 반영
    query.is_valid = result.is_valid
    if result.is_valid:
        # 정규화된 SQL 저장 (전처리 후 파싱)
        try:
            preprocessed = _preprocess_sql(query.sql_raw)
            parsed = sqlglot.parse(preprocessed, dialect=_DIALECT_MAP[query.dialect])
            if parsed and parsed[0]:
                query.sql_normalized = parsed[0].sql(dialect=_DIALECT_MAP[query.dialect], pretty=True)
        except Exception:
            query.sql_normalized = query.sql_raw
        query.structure = result.structure
        query.validation_error = None
    else:
        query.validation_error = result.error_message

    return result
