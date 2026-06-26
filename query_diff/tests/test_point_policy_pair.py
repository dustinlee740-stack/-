"""캐시포인트 정책 집계 쿼리쌍(운영 vs 분석) 동치 검증.

운영(A)은 tbl_policy CTE + 인라인 집계 서브쿼리, 분석(B)은 tbl_policy/pt 두 CTE 로
작성됐지만 **같은 결과**다. meta3 매핑(contract/point_provider/card_point_policy/pnt_tran)
이 적용되면 JOIN·WHERE·집계가 모두 정렬돼 EQUIVALENT 로 판정돼야 한다.
특히 point_provider.provider_id 는 분석도 미변경(identity) 사용 — 1:N 모호성에서 identity 채택.
"""

from __future__ import annotations

from query_diff.models import Dialect, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff.schema_mapping import load_op_an_map

A_SQL = """
WITH tbl_policy AS (
  SELECT a.provider_id, b.name AS provider_nm, a.policy_id, c.name, c.display_name
  FROM kodasp.point_provider a
  INNER JOIN kodasp.contract b ON (b.player_id = a.provider_id AND b.role_Cd = 'KA')
  INNER JOIN kodasp.card_point_policy c ON (c.id = a.policy_id)
  WHERE c.asp_id IN ('000140000000000','000161000000000') and c.policy_type = '01' AND a.role_cd = 'KA'
)
SELECT pt.asp_id AS aspid, tp.provider_nm, tp.name, tp.display_name, pt.policy_id, pt.approval_day,
  pt.save_amt, pt.recovery_amt, pt.expired_amt
FROM (
  SELECT pt.asp_id, pt.policy_id, pt.approval_day,
    SUM(CASE WHEN pt.tran_type IN ('61','65','11','15','09','20','69','81') THEN 1 ELSE 0 END * pt.point_amt) AS save_amt,
    SUM(CASE WHEN pt.tran_type IN ('62','66','12','41','64') THEN 1 ELSE 0 END * pt.point_amt) AS recovery_amt,
    SUM(CASE WHEN pt.tran_type IN ('21','31') THEN 1 ELSE 0 END * pt.point_amt) AS expired_amt
  FROM kps.pnt_tran pt
  WHERE pt.asp_id IN ('000140000000000','000161000000000') and pt.policy_type = '01'
    and pt.approval_day between '20240101' and '20250101'
  GROUP BY pt.asp_id, pt.approval_day, pt.policy_id
) pt
INNER JOIN tbl_policy tp ON (tp.policy_id = pt.policy_id)
"""

B_SQL = """
with tbl_policy as (
  select a.provider_id, b.PTN_NM as provider_nm, a.PNT_PLCY_ID, c.CRD_PNT_PLCY_NM, c.AP_XPRSN_NM
  from kod.point_provider a
  inner join kod.contract b on b.PTN_ID = a.provider_id and b.role_cd = 'KA'
  inner join kod.card_point_policy c on c.CRD_PNT_PLCY_ID = a.PNT_PLCY_ID
  where 1=1 and c.asp_id in (${aspId}) and c.PNT_PLCY_TYPE_CD = '01' and a.PNT_BOWR_ROLE_CD = 'KA'
),
pt as (
  select asp_id, PNT_PLCY_ID, apv_dt,
    sum(case when PNT_TR_TYPE_CD in ('61','65','11','15','09','20','69','81') then 1 else 0 end * TR_AMT) as save_amt,
    sum(case when PNT_TR_TYPE_CD IN ('62','66','12','41','64') then 1 else 0 end * TR_AMT) as recovery_amt,
    sum(case when PNT_TR_TYPE_CD in ('21','31') then 1 else 0 end * TR_AMT) as expired_amt
  from kps.pnt_tran
  where 1=1 and asp_id in (${aspId}) and PNT_PLCY_TYPE_CD = '01' and APV_DT between ${start_day} and ${end_day}
  group by asp_id, apv_dt, PNT_PLCY_ID
)
select pt.asp_id aspid, tp.provider_nm, tp.CRD_PNT_PLCY_NM, tp.AP_XPRSN_NM, pt.PNT_PLCY_ID, pt.apv_dt,
  pt.save_amt, pt.recovery_amt, pt.expired_amt
from pt inner join tbl_policy tp on tp.PNT_PLCY_ID = pt.PNT_PLCY_ID
"""


def test_point_policy_pair_equivalent():
    """매핑 적용 시 운영↔분석이 EQUIVALENT(작성 스타일·파라미터 차이 흡수)."""
    d = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    assert d.verdict == SemanticVerdict.EQUIVALENT, [
        (dim.dimension.value, dim.only_in_a, dim.only_in_b)
        for dim in d.dimensions if not dim.matched
    ]
