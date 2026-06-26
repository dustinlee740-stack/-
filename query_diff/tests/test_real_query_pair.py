"""실제 운영(단층 SELECT) ↔ 분석(집계 CTE 분해) 쿼리쌍 비교 테스트.

데이터로는 동일 결과가 확인된 쌍이나, 운영상 불일치 사유를 사람이 2차 판단해야 한다.
도구의 역할은 스키마명·작성 스타일(CTE) 차이를 흡수하고 **진짜 차이만 드러내는** 것.

이 테스트는 meta3 권위 매핑 + 전 스코프(CTE 관통) 추출 적용 후:
- base_tables 가 일치(CTE를 꿰뚫어 같은 원천 집합으로 정렬)하고
- 진짜 차이(af_prcr_cd IS NULL vs '', 가맹점명 BZMN_NM vs MC_NM)가 드러나는지 검증한다.
"""

from __future__ import annotations

import pytest

from query_diff.models import Dialect, DimensionName, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff.schema_mapping import load_op_an_map

A_SQL = """
select /*+full(it)*/
it.approval_date,
ksd.dcnt_id 혜택ID,
max(kpg.grp_name) 가맹점그룹명,
it.tr_merchant_id 가맹점id,
max(am.simple_nm) 가맹점명,
sum(it.org_amt) 원결제금액,
sum(ibt.discount_amt) 할인금액,
sum(it.tr_amt) 승인금액
from ias.ias_transaction it
inner join ias.ias_benefit_tran ibt on it.nr_number = ibt.nr_number and ibt.discount_sub_type='01' and ibt.coupon_id is null
inner join (select dcnt_seq, sd.dcnt_id, grp_id from KODASP.service_discount sd where dcnt_id in ('36823','36822')) ksd on ibt.discount_seq = ksd.dcnt_seq
left outer join kodasp.dcnt_group_mapping kdqm on kdqm.dcnt_seq = ksd.dcnt_seq and kdqm.channel =
 CASE WHEN it.acquirer_merchant_type IS NULL THEN 'KM' WHEN it.acquirer_merchant_type = '0' THEN 'BC' ELSE '-' END
left outer join KODASP.player_group kpg on kpg.grp_id = kdqm.group_id
left outer join ias.tb_all_merchant am on am.mct_mng_no = to_char(it.tr_merchant_id) and am.aq_merchant_type = case when it.acquirer_merchant_type is null then 'NULL' else to_char(it.acquirer_merchant_type) end
where 1=1
and it.approval_date >= 20260515 and it.approval_date <= 20260517
and it.reversal_status is null
and it.processing_code = '000000' and it.mti='0100' and it.response_code='00'
group by ksd.dcnt_id, it.tr_merchant_id, it.approval_date
"""

B_SQL = """
with txn as (
select it.apv_dt, ksd.DC_BNF_SNO2, ksd.DC_BNF_SNO, it.STLM_MC_ID, it.ACQR_CD,
sum(it.GM_TR_AMT) as 원결제금액, sum(ibt.DC_AMT) as 할인금액, sum(it.BALA_USE_AMT) as 승인금액
from ias.ias_transaction it
inner join ias.ias_benefit_tran ibt on it.nr_no = ibt.nr_no and ibt.SUB_DC_BNF_CD='01' and ibt.CPN_ID=''
inner join (select DC_BNF_SNO, DC_BNF_SNO2 from kod.service_discount where DC_BNF_SNO2 in (${bnf_id})) ksd on ibt.DC_BNF_SNO = ksd.DC_BNF_SNO
where it.apv_dt between ${start_day} and ${end_day}
and it.AF_PRCR_CD = '' and it.PCS_CD = '000000' and it.mti_cd='0100' and it.APV_RS_RSP_CD='00'
group by it.apv_dt, ksd.DC_BNF_SNO2, ksd.DC_BNF_SNO, it.STLM_MC_ID, it.ACQR_CD
),
grp as (
select kdqm.DC_BNF_SNO, max(kpg.GRP_NM) as GRP_NM
from kod.dcnt_group_mapping kdqm
left join kod.player_group kpg on kpg.GRP_ID = kdqm.BZTP_GRP_ID
group by kdqm.DC_BNF_SNO
)
select t.apv_dt, t.DC_BNF_SNO2 as 혜택ID, g.GRP_NM as 가맹점그룹명, t.STLM_MC_ID as 가맹점id, max(am.MC_NM) as 가맹점명,
sum(t.원결제금액) as 원결제금액, sum(t.할인금액) as 할인금액, sum(t.승인금액) as 승인금액
from txn t
left join grp g on g.DC_BNF_SNO = t.DC_BNF_SNO
left join ias.tb_all_merchant am on am.MC_ID = t.STLM_MC_ID and am.ACQR_CD = case when t.ACQR_CD = '' then 'NULL' else t.ACQR_CD end
group by t.apv_dt, t.DC_BNF_SNO2, g.GRP_NM, t.STLM_MC_ID
"""


@pytest.fixture(scope="module")
def diff():
    op_an = load_op_an_map()
    return compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=op_an)


def _dim(diff, name):
    return next(d for d in diff.dimensions if d.dimension == name)


def test_base_tables_reconciled_through_cte(diff):
    """집계 CTE를 꿰뚫어 양쪽이 같은 원천 테이블 집합으로 정렬된다."""
    bt = _dim(diff, DimensionName.BASE_TABLES)
    assert bt.matched, f"base tables 불일치: A만={bt.only_in_a} B만={bt.only_in_b}"
    # 원천 테이블이 실제로 추출됐는지(빈 매칭이 아님)
    plan_tables = set(diff.plan_a.base_tables)
    assert {"ias_transaction", "ias_benefit_tran", "service_discount",
            "dcnt_group_mapping", "player_group", "tb_all_merchant"} <= plan_tables


def test_schema_names_translated_no_op_name_noise(diff):
    """운영 물리명(tr_merchant_id 등)이 분석명으로 번역돼 노이즈로 남지 않는다."""
    blob = " | ".join(diff.plan_a.all_predicates + [a for _, a in diff.plan_a.aggregates])
    assert "tr_merchant_id" not in blob
    assert "response_code" not in blob
    # 분석명으로 치환됨
    assert "apv_rs_rsp_cd" in blob


def test_null_equals_empty_absorbed(diff):
    """NULL ≡ '' 는 엔진 차이로 동치 — af_prcr_cd 차이가 흡수돼 PREDICATES 일치."""
    pred = _dim(diff, DimensionName.PREDICATES)
    assert pred.matched, f"NULL≡'' 흡수 후 술어 차이 없어야 함: A={pred.only_in_a} B={pred.only_in_b}"


def test_real_difference_merchant_name_column_surfaced(diff):
    """진짜 차이: 가맹점명 컬럼이 A=simple_nm vs B=mc_nm. A측은 원본 운영명으로 표시."""
    agg = _dim(diff, DimensionName.AGGREGATES)
    a_blob = " | ".join(agg.only_in_a).lower()
    b_blob = " | ".join(agg.only_in_b).lower()
    # 표시 역변환: 분석명(bzmn_nm)이 아니라 사용자가 쓴 원본 운영명(simple_nm)
    assert "simple_nm" in a_blob
    assert "bzmn_nm" not in a_blob
    assert "mc_nm" in b_blob


def test_join_style_and_spine_absorbed_only_channel_remains(diff):
    """JOIN vs WITH 스타일(앵커) + WITH-spine(txn CTE) + 타입코어션(to_char)을 모두 흡수하면
    player_group·가맹점 조인은 매칭돼 사라지고, **채널 CASE 필터(진짜 차이)** 만 남는다."""
    jg = _dim(diff, DimensionName.JOIN_GRAPH)
    blob = " || ".join(jg.only_in_a + jg.only_in_b)
    # 스타일/스파인으로만 달랐던 조인은 사라짐
    assert "player_group" not in blob, blob
    assert "tb_all_merchant" not in blob, blob  # 가맹점 조인 매칭됨(WITH-spine+cast 흡수)
    # 잔존 = 채널 CASE 필터(A에만), B측 조인 차이는 없음
    assert jg.only_in_b == [], jg.only_in_b
    # 같은 조인(dcnt_group_mapping↔service_discount)인데 A에만 채널 조건 — 술어 단위 표기
    assert len(jg.only_in_a) == 1, jg.only_in_a
    msg = jg.only_in_a[0]
    assert "A 쿼리에만" in msg                       # 조인 누락이 아니라 추가 조건 표기
    assert "channel" in msg                          # 원본 운영명(번역형 acqr_dv_cd 아님)
    assert "dcnt_group_mapping" in msg and "service_discount" in msg
    assert "CASE('-')" not in msg                    # 정규화 노이즈 미노출
    assert "원본 ON" in msg                          # 원본 ON 절 텍스트 동반(쿼리에서 검색 가능)


def test_b_side_display_not_corrupted(diff):
    """역변환은 A측에만 — B측 표시는 분석명 그대로(grp_nm), A측 운영명(grp_name)으로 오염 안 됨."""
    gk = _dim(diff, DimensionName.GROUP_KEYS)
    b_blob = " || ".join(gk.only_in_b)
    assert "grp_nm" in b_blob          # 분석명 유지
    assert "grp_name" not in b_blob    # A측 운영명으로 오염되지 않음


def test_overall_verdict_divergent(diff):
    """실차이가 있으므로 동치가 아님 — 사람이 2차 판단 대상."""
    assert diff.verdict == SemanticVerdict.DIVERGENT


def test_group_key_noise_suppressed(diff):
    """2단계 집계 CTE의 그룹키 noise(txn./grp. 한정자, 내부 키)가 제거되고
    실차이(B가 grp_nm으로 그룹)만 남는다."""
    gk = _dim(diff, DimensionName.GROUP_KEYS)
    assert gk.only_in_a == []
    # B-only 잔차는 grp_nm 한 종류뿐(컬럼명 기준)
    assert all("grp_nm" in x for x in gk.only_in_b), gk.only_in_b


def test_tautology_and_param_noise_suppressed(diff):
    """1=1 제거 + 날짜범위(BETWEEN/부등호) 템플릿 파라미터 차이 흡수 + NULL≡'' 흡수
    → PREDICATES 에 잔존 차이가 없다."""
    pred = _dim(diff, DimensionName.PREDICATES)
    blob = " | ".join(pred.only_in_a + pred.only_in_b)
    assert "1 = 1" not in blob
    assert "apv_dt" not in blob  # 날짜 범위는 파라미터 차이로 흡수됨
    assert pred.only_in_a == [] and pred.only_in_b == []
