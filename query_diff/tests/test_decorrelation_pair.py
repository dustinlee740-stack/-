"""상관 스칼라 서브쿼리(A) ↔ LEFT JOIN 최신1건(B) 디코릴레이션 인식 검증.

Oracle은 SELECT 절 상관 스칼라 서브쿼리로 per-key 최신 status 를 구하고, Hive는 상관 서브쿼리가
안 돼 LEFT JOIN + ROW_NUMBER()=1 로 우회한다. 같은 베이스 테이블(contract)에 대한 이 구조 차이는
JOIN/조건/집계/출력 4개 차원에 거짓 ✗를 내는데, 디코릴레이션으로 인식해 제한적 판정으로 흡수한다.
단 simple_nm(→bzmn_nm)↔mc_nm 같은 진짜 차이는 그대로 노출한다.
"""

from __future__ import annotations

from query_diff.models import Dialect, DimensionName, QueryInput, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.semantic_diff.decorrelation import detect_decorrelation
from query_diff.structure_diff import compare_structures
from query_diff.structure_diff.schema_mapping import load_op_an_map
from query_diff.validation_service import validate_query_input

A_SQL = r"""
select
    a.aq_type as 매입사코드,
    a.mct_mng_no as 매입사가맹점ID,
    a.simple_nm as 매입사가맹점명,
    a.sales_cd as 매출코드,
    '' as 지사상가맹점여부,
    NVL((select DECODE(MAX(B.status) KEEP(DENSE_RANK FIRST ORDER BY B.reg_dt DESC), 'APPROVAL', 'Y', 'N')
         from bizd.contract B where biz_number = A.biz_license_no group by biz_number), 'N') as status
from ias.tb_all_merchant a
where 1=1 and a.aq_type = 'KB' and a.biz_license_no = '6422000175'
"""

B_SQL = r"""
SELECT
    a.acqr_dv_cd AS `매입사코드`,
    a.mc_id AS `매입사가맹점ID`,
    a.MC_NM AS `매입사가맹점명`,
    a.sl_cd AS `매출코드`,
    '' AS `지사상가맹점여부`,
    CASE WHEN c.prcs_st_cd = 'APPROVAL' THEN 'Y' ELSE 'N' END AS `status`
FROM ias.tb_all_merchant a
LEFT JOIN (
    SELECT bzno, prcs_st_cd FROM (
        SELECT bzno, prcs_st_cd, ROW_NUMBER() OVER (PARTITION BY bzno ORDER BY apl_dttm DESC) AS rn
        FROM bid.contract) t
    WHERE t.rn = 1) c ON c.bzno = a.bzno
WHERE 1 = 1 AND a.acqr_dv_cd = 'KB' AND a.bzno = '6422000175'
"""


def _qi(sql: str, dialect: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=dialect)
    validate_query_input(q)
    assert q.is_valid, f"검증 실패: {q.validation_error}"
    return q


def _dim(diff, name):
    return next(d for d in diff.dimensions if d.dimension == name)


def test_detect_decorrelation_positive_and_negative():
    """양쪽(상관 서브쿼리 + LEFT JOIN 최신1건, 같은 T) 동시일 때만 인식."""
    ta, _ = normalize_query(A_SQL, "oracle")
    tb, _ = normalize_query(B_SQL, "hive")
    info = detect_decorrelation(ta, tb)
    assert info is not None and info.table == "contract"
    assert info.a.value_col == "status" and info.b.value_col == "prcs_st_cd"
    assert info.a.order_col == "reg_dt" and info.b.order_col == "apl_dttm"

    # 일반 조인 페어는 인식 안 함
    n1, _ = normalize_query("select x.a from t1 x join t2 y on x.id = y.id", "oracle")
    n2, _ = normalize_query("select x.a from t1 x join t2 y on x.id = y.id", "hive")
    assert detect_decorrelation(n1, n2) is None


def test_decorrelation_pair_semantic_limited():
    """디코릴레이션 4개 거짓 ✗ 소거 + JOIN_GRAPH 제한적 판정, simple_nm↔mc_nm 진짜 차이는 잔존."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())

    jg = _dim(diff, DimensionName.JOIN_GRAPH)
    assert jg.matched is True and jg.limited is True
    assert "디코릴레이션" in jg.explanation
    assert "동률" in jg.caveat and "reg_dt" in jg.caveat and "apl_dttm" in jg.caveat

    # 디코릴레이션으로 흡수된 핵심 차원들은 매칭
    for name in (DimensionName.BASE_TABLES, DimensionName.PREDICATES, DimensionName.AGGREGATES):
        assert _dim(diff, name).matched is True
    # contract 는 절제되어 base_tables 에서 빠짐
    assert "contract" not in diff.plan_a.base_tables
    assert "contract" not in diff.plan_b.base_tables

    # 진짜 차이(사업자명 vs 가맹점명)는 그대로 노출
    pj = _dim(diff, DimensionName.PROJECTIONS)
    assert pj.matched is False
    assert any("simple_nm" in c.lower() for c in pj.only_in_a)  # 표시는 대문자 원문
    assert any("mc_nm" in c.lower() for c in pj.only_in_b)

    # verdict LIMITED + 문제 요약에 디코릴레이션 제한적 판정
    assert diff.verdict is SemanticVerdict.LIMITED
    assert any("디코릴레이션" in i for i in diff.issues)


def test_decorrelation_pair_structure_warns():
    """구조 비교도 동일하게 DECORRELATION_SOFT_MATCH WARNING(두 화면 일치)."""
    a, b = _qi(A_SQL, Dialect.ORACLE), _qi(B_SQL, Dialect.HIVE)
    diff = compare_structures(a, b, op_an=load_op_an_map())
    dc = [f for f in diff.findings if f.rule_id == "DECORRELATION_SOFT_MATCH"]
    assert dc and dc[0].severity.value == "WARNING"
    # 디코릴레이션 조인은 절제되어 조인 미스매치 CRITICAL 이 없어야 함
    assert not any(f.rule_id.startswith("JOIN_") for f in diff.findings)
