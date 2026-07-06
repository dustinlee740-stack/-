"""조인 그래프 라벨이 CTE 경계를 존중해 '실제 조인 쌍'으로 표기되는지 검증.

배경: 조인 라벨이 ON 참조 테이블 집합(패스스루 해소 후)을 나열해
`ADDRESS_INFO↔CARD_DELIVERY↔IAS_TRANSACTION` 처럼 나오면 (1) CTE명과 그 내부 스파인이
서로 조인된 것처럼, (2) CARD_DELIVERY 와 IAS_TRANSACTION 이 직접 조인된 것처럼 잘못 보인다.

실제 구조: `CARD_DELIVERY ⋈ SERVICE`→ADDRESS_INFO(CTE), 그 `ADDRESS_INFO ⋈ IAS_TRANSACTION`.
라벨은 각 조인의 등치 키가 잇는 두 엔티티를 쿼리에 쓰인 이름 그대로(다중테이블 CTE는 CTE명 유지)
보여줘야 한다. 매칭(페어링)은 여전히 해소된 테이블집합 기준 — 표시만 CTE 경계를 존중한다.
"""

from __future__ import annotations

from query_diff.models import Dialect, DimensionName
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff.schema_mapping import load_op_an_map

A_SQL = """
WITH ADDRESS_INFO AS (
    SELECT /*+ FULL(CD) */
        CD.USER_ID, CD.ADDRESS_BASE,
        ROW_NUMBER() OVER (PARTITION BY CD.USER_ID ORDER BY CD.CREATED_AT DESC) AS RN
    FROM CAMS.CARD_DELIVERY CD
    INNER JOIN KODASP.SERVICE KS ON KS.SVC_ID = CD.SVC_ID AND KS.OWNER_KA = '410128830093700'
    WHERE CD.STATUS != 'CANCEL'
),
TRANSACTION_DATA AS (
    SELECT IT.USER_ID, IT.APPROVAL_DATE AS DAY,
        CASE WHEN AI.ADDRESS_BASE LIKE '%X%' THEN 'A' ELSE 'B' END AS CBS,
        IT.TR_AMT, IT.ORG_AMT
    FROM ADDRESS_INFO AI
    INNER JOIN IAS.IAS_TRANSACTION IT ON AI.USER_ID = IT.USER_ID AND AI.RN = 1
    WHERE IT.ASP_ID = '000140000000000' AND IT.OWNER_KA = '410128830093700'
      AND IT.MTI != '0120' AND IT.RESPONSE_CODE IN ('00', '-1') AND IT.PROCESSING_CODE = '000000'
)
SELECT SUBSTR(DAY,0,6) YM, CBS, SUM(TR_AMT) T1, SUM(ORG_AMT) T2,
       COUNT(1) C1, COUNT(DISTINCT USER_ID) C2
FROM TRANSACTION_DATA GROUP BY SUBSTR(DAY,0,6), CBS ORDER BY SUBSTR(DAY,0,6), CBS
"""

B_SQL = """
WITH ADDRESS_INFO AS (
  SELECT CD.CRD_APL_MBR_ID MBR_ID, CD.CRD_DLV_BSC_ADDR,
    ROW_NUMBER() OVER (PARTITION BY CD.CRD_APL_MBR_ID ORDER BY CD.SYS_CRE_DTTM DESC) AS RN
  FROM CAM.CARD_DELIVERY CD
  INNER JOIN KOD.SERVICE KS ON KS.SVC_ID = CD.SVC_ID AND KS.REP_KA_ID = '410128830093700'
  WHERE CD.CRD_DLV_ST_CD != 'CANCEL'
)
select substr(cast(apv_dt as string), 1, 6) YM,
  CASE WHEN AI.CRD_DLV_BSC_ADDR LIKE '%X%' THEN 'A' ELSE 'B' END AS CBS,
  count(distinct case when a.stlm_chrg_apv_cd = 'SA' then a.mbr_id end) c1,
  sum(case when a.stlm_chrg_apv_cd = 'SA' then tot_amt end) s1
from ods.chrg_stlm_bydt_agg a
inner join ADDRESS_INFO AI on a.mbr_id = AI.mbr_id AND AI.RN = 1
  AND a.apv_dt between 20230101 and 20241205
  AND a.stlm_chrg_apv_cd in ('SA', 'SC')
  AND A.OWR_KA_ID = '410128830093700'
group by 1, 2 order by 1, 2
"""


def _jg(diff):
    return next(d for d in diff.dimensions if d.dimension == DimensionName.JOIN_GRAPH)


def test_join_label_respects_cte_boundary():
    """메인 조인 라벨이 CTE명↔조인테이블로 나오고, CTE 내부 스파인(CARD_DELIVERY)이나
    허위 직접조인(CARD_DELIVERY↔IAS_TRANSACTION)·3자 플랫이 노출되지 않는다."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    jg = _jg(diff)

    # 메인 조인 대상이 A(IAS_TRANSACTION) vs B(CHRG_STLM_BYDT_AGG) 로 다름 → 불일치
    assert not jg.matched, (jg.only_in_a, jg.only_in_b)

    a_blob = " || ".join(jg.only_in_a)
    b_blob = " || ".join(jg.only_in_b)
    blob = (a_blob + " || " + b_blob).upper()

    # 실제 조인 쌍: A 는 ADDRESS_INFO(CTE) ↔ IAS_TRANSACTION
    assert any("ADDRESS_INFO" in m and "IAS_TRANSACTION" in m for m in jg.only_in_a), jg.only_in_a
    # B 는 ADDRESS_INFO(CTE) ↔ CHRG_STLM_BYDT_AGG(ODS 일별집계)
    assert any("ADDRESS_INFO" in m and "CHRG_STLM_BYDT_AGG" in m for m in jg.only_in_b), jg.only_in_b

    # CTE 내부 스파인은 조인 상대가 아니다 — CARD_DELIVERY 가 메인 조인 라벨에 새지 않고,
    # CARD_DELIVERY ⋈ SERVICE 는 양쪽 일치로 흡수되어 차이 목록에 없다.
    assert "CARD_DELIVERY" not in blob, blob
    # 허위 직접 조인(사용자가 명시적으로 부정)·3자 플랫이 없어야 한다.
    assert "CARD_DELIVERY ↔ IAS_TRANSACTION".upper() not in blob
    assert "ADDRESS_INFO↔CARD_DELIVERY" not in blob
    assert "↔CARD_DELIVERY↔" not in blob


def test_join_pairing_still_holds_across_cte_and_flat():
    """표시 분리 이후에도 매칭(페어링)은 해소된 테이블집합 기준으로 유지된다:
    양쪽 ADDRESS_INFO 내부 조인(CARD_DELIVERY⋈SERVICE)은 동일로 흡수(차이 아님)."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    jg = _jg(diff)
    # 잔존 차이는 메인 조인(대상 테이블 상이) 뿐 — 각 측 1건.
    assert len(jg.only_in_a) == 1, jg.only_in_a
    assert len(jg.only_in_b) == 1, jg.only_in_b


def test_join_on_qualifier_noise_absorbed():
    """조인 ON 부가조건이 한정자만 다른 동일 null-체크일 때(qualify 폴백 노이즈) 흡수되어 매칭.

    회귀: `cdm.card_apply_no IS NOT NULL`(A, 한정) vs `card_apply_no IS NOT NULL`(B, 비한정)는
    NULL≡'' 흡수(_canonical_expr) 후에도 피연산자 한정자만 달라 남던 것 — WHERE(_compare_predicates)
    와 대칭으로 _compare_join_graph 에도 _absorb_qualifier_noise 를 적용해 동치로 처리한다.
    """
    from query_diff.models import JoinEdge, LogicalPlan
    from query_diff.semantic_diff.analyzer import _compare_join_graph

    equi = "ci.card_apply_no = cdm.card_apply_no"
    a = LogicalPlan(join_edges=[JoinEdge(
        left_table="cdm", right_table="ci", join_type="LEFT",
        on_predicates=[equi, "cdm.card_apply_no IS NOT NULL"])])
    b = LogicalPlan(join_edges=[JoinEdge(
        left_table="cdm", right_table="ci", join_type="LEFT",
        on_predicates=[equi, "card_apply_no IS NOT NULL"])])
    jg = _compare_join_graph(a, b)
    assert jg.matched, (jg.only_in_a, jg.only_in_b)


def test_both_sides_expose_raw_on():
    """A뿐 아니라 B 전용 조인도 원본 ON 절을 노출한다.

    회귀 방지: raw ON 은 조인 대상(right_table)명으로 keyed 인데, 조인 대상이 CTE(ADDRESS_INFO)면
    매칭용 해소 테이블집합에 그 이름이 없어 조회에 실패했었다(B만 ON 누락). 대표 엣지 right_table
    우선 조회로 복구."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    jg = _jg(diff)
    assert jg.only_in_a and all("원본 ON" in m for m in jg.only_in_a), jg.only_in_a
    assert jg.only_in_b and all("원본 ON" in m for m in jg.only_in_b), jg.only_in_b
    # B 조인 대상이 CTE(ADDRESS_INFO)여도 실제 ON 텍스트(MBR_ID 등)가 붙는다.
    assert any("MBR_ID" in m.upper() for m in jg.only_in_b), jg.only_in_b
