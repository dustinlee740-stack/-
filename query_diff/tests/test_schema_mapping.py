"""op→an 스키마 매핑(No.3) 적용 테스트.

운영(Oracle, op 물리명) 쿼리를 분석(Hive, an 물리명) 네임스페이스로 번역해
구조/의미 비교가 동치로 수렴하는지 검증한다. 매핑 데이터는 op_an_map.json.
"""

from __future__ import annotations

import pytest

from query_diff.models import Dialect, QueryInput, Severity
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff import compare_structures
from query_diff.structure_diff.normalizer import extract_canonical
from query_diff.structure_diff.schema_mapping import load_op_an_map
from query_diff.validation_service import validate_query_input


def _qi(sql: str, dialect: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=dialect)
    validate_query_input(q)
    assert q.is_valid, f"검증 실패: {q.validation_error}"
    return q


@pytest.fixture(scope="module")
def op_an():
    return load_op_an_map()


# 운영(A) vs 분석(B) — 동일 구조, 이름만 op↔an
A_SQL = (
    "SELECT t.tr_merchant_id, SUM(t.tr_amt) AS amt "
    "FROM ias_transaction t "
    "WHERE t.response_code = '00' AND t.mti = '0100' "
    "GROUP BY t.tr_merchant_id"
)
B_SQL = (
    "SELECT t.stlm_mc_id, SUM(t.bala_use_amt) AS amt "
    "FROM ias_transaction t "
    "WHERE t.apv_rs_rsp_cd = '00' AND t.mti_cd = '0100' "
    "GROUP BY t.stlm_mc_id"
)


# --- OpAnMap 단위 ---

@pytest.mark.parametrize("op_table,op_col,expected", [
    ("IAS_TRANSACTION", "TR_MERCHANT_ID", "STLM_MC_ID"),
    ("IAS_TRANSACTION", "DISCOUNT_AMT", "DC_AMT"),
    ("IAS_TRANSACTION", "APPROVAL_DATE", "APV_DT"),
    ("IAS_TRANSACTION", "RESPONSE_CODE", "APV_RS_RSP_CD"),
    ("IAS_TRANSACTION", "TR_AMT", "BALA_USE_AMT"),
])
def test_translate_column_known(op_an, op_table, op_col, expected):
    assert op_an.translate_column(op_table, op_col) == expected


def test_translate_column_identity_fallback(op_an):
    # 매핑에 없는 컬럼은 원본 보존(비파괴)
    assert op_an.translate_column("IAS_TRANSACTION", "NO_SUCH_COL") == "NO_SUCH_COL"


def test_translate_table_identity(op_an):
    # IAS_TRANSACTION 은 운영=분석 동명
    assert op_an.translate_table("IAS_TRANSACTION") == "IAS_TRANSACTION"


# --- AST 번역으로 절 수렴 ---

def test_translation_reconciles_clauses(op_an):
    ca = extract_canonical(A_SQL, "oracle", op_an=op_an)
    cb = extract_canonical(B_SQL, "hive")
    assert set(ca.where_predicates) == set(cb.where_predicates)
    assert set(ca.group_by) == set(cb.group_by)
    aggs_a = [(p.agg_function, p.agg_arg) for p in ca.projections if p.is_aggregate]
    aggs_b = [(p.agg_function, p.agg_arg) for p in cb.projections if p.is_aggregate]
    assert aggs_a == aggs_b


# --- 구조 비교 ---

def test_structure_diff_without_mapping_has_findings():
    a, b = _qi(A_SQL, Dialect.ORACLE), _qi(B_SQL, Dialect.HIVE)
    diff = compare_structures(a, b)  # 매핑 미적용
    assert diff.findings, "매핑 없이는 컬럼 차이가 검출되어야 한다"


def test_structure_diff_with_mapping_reconciles(op_an):
    a, b = _qi(A_SQL, Dialect.ORACLE), _qi(B_SQL, Dialect.HIVE)
    diff = compare_structures(a, b, op_an=op_an)
    criticals = [f for f in diff.findings if f.severity == Severity.CRITICAL]
    assert not criticals, f"매핑 적용 후 CRITICAL 차이가 없어야 한다: {[f.rule_id for f in criticals]}"
    assert not diff.findings, f"매핑 적용 후 차이가 없어야 한다: {[f.rule_id for f in diff.findings]}"


# --- 의미 비교 ---

def test_semantic_divergent_without_mapping():
    from query_diff.models import SemanticVerdict
    d = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE)
    assert d.verdict == SemanticVerdict.DIVERGENT


def test_semantic_equivalent_with_mapping(op_an):
    from query_diff.models import SemanticVerdict
    d = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=op_an)
    assert d.verdict == SemanticVerdict.EQUIVALENT


def test_numeric_string_quote_absorbed():
    """Oracle 숫자 따옴표('99999999') ≡ Hive 숫자(99999999) — 엔진 차이 흡수."""
    from query_diff.models import SemanticVerdict
    a = "SELECT MIN(CASE WHEN t.tr_type_cd IN ('1') THEN t.apv_dt ELSE '99999999' END) FROM ias.ias_transaction t"
    b = "SELECT MIN(CASE WHEN t.tr_type_cd IN ('1') THEN t.apv_dt ELSE 99999999 END) FROM ias.ias_transaction t"
    d = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
    assert d.verdict == SemanticVerdict.EQUIVALENT, [
        (x.dimension.value, x.only_in_a, x.only_in_b) for x in d.dimensions if not x.matched
    ]
