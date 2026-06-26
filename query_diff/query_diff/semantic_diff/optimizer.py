"""정규화 파이프라인

sqlglot 옵티마이저를 적용해 A(FROM 조인)와 B(WITH CTE)처럼 표기만 다른 쿼리를
같은 AST로 수렴시킨다. 정규화 불가 구문(윈도우, UNION 등)은 limitations로 보고.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.optimizer import optimize
from sqlglot.optimizer.eliminate_ctes import eliminate_ctes
from sqlglot.optimizer.merge_subqueries import merge_subqueries
from sqlglot.optimizer.qualify import qualify

from query_diff.validation_service import _preprocess_sql


def _detect_limitations(tree: exp.Expression) -> list[str]:
    """정규화하기 어려운 구문을 탐지해 사람이 읽을 수 있는 사유 목록 반환"""
    lims: list[str] = []

    if tree.find(exp.Window):
        lims.append(
            "윈도우 함수(OVER)가 포함되어 있어 정규화 제한이 있습니다. 함수 자체는 원형 그대로 비교됩니다."
        )
    if tree.find(exp.Union) or tree.find(exp.Except) or tree.find(exp.Intersect):
        lims.append(
            "UNION/EXCEPT/INTERSECT 집합 연산은 정규화되지 않습니다. 첫 번째 SELECT 기준으로만 비교됩니다."
        )
    if tree.find(exp.Cube) or tree.find(exp.Rollup):
        lims.append("ROLLUP/CUBE는 GROUP BY 키 비교에서 단순 키로 취급됩니다.")

    # 상관 서브쿼리 검출: 서브쿼리 내부에서 외부 테이블 alias를 참조하는지 (간이 판정)
    for subq in tree.find_all(exp.Subquery):
        # 서브쿼리 내부 Column 중 서브쿼리 내부에 정의된 alias가 아닌 것이 있으면 상관 가능성
        inner_tables = {
            (t.alias_or_name or "").lower()
            for t in subq.find_all(exp.Table)
        }
        for col in subq.find_all(exp.Column):
            if col.table and col.table.lower() not in inner_tables and inner_tables:
                lims.append(
                    "상관 서브쿼리(외부 컬럼을 참조하는 서브쿼리)가 감지되어 정규화가 제한될 수 있습니다."
                )
                break
        else:
            continue
        break

    return lims


def normalize_query(sql: str, dialect: str) -> tuple[exp.Expression, list[str]]:
    """SQL을 정규화된 AST와 제한사항 리스트로 반환.

    실패하더라도 원형 AST를 반환하여 부분 비교가 가능하도록 함.
    """
    preprocessed = _preprocess_sql(sql.rstrip().rstrip(";"))

    try:
        tree = sqlglot.parse_one(preprocessed, dialect=dialect)
    except sqlglot.errors.ParseError as e:
        raise ValueError(f"SQL 파싱 실패: {e}") from e

    if tree is None:
        raise ValueError("파싱 결과가 비어 있습니다.")

    limitations = _detect_limitations(tree)

    try:
        optimized = optimize(
            tree,
            dialect=dialect,
            rules=[qualify, eliminate_ctes, merge_subqueries],
            schema=None,
        )
        return optimized, limitations
    except Exception as e:  # 옵티마이저 실패 시 원형 반환
        limitations.append(
            f"옵티마이저 정규화 실패 — 원형 AST로 비교를 진행합니다. (사유: {str(e)[:120]})"
        )
        return tree, limitations
