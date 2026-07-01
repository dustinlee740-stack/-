"""예치금/충전상(RC) 잔액 집계 쿼리쌍(운영 vs 분석) 조인 그래프 관통 검증.

운영(A, Oracle)은 `contract`에 `recharger` 직접 조인 + 예치금/거래 집계를 **인라인
서브쿼리**(`c`, `d`)로 붙인다. 분석(B, Hive)도 같은 구조지만 표준화된 분석명
(`ptn_id`/`rc_id`/`dpsts_rc_id`)과 중첩 서브쿼리(`c`는 윈도우 서브쿼리 `t` 위)로 쓰였다.

회귀 핀: 조인 키가 **서브쿼리(파생 테이블) 출력 컬럼**이라도 meta3 매핑이 관통돼야 한다.
  - A의 `c.player_id`/`d.deposit_mct_id` 는 원천 `recharge_deposit.player_id`/
    `ias_transaction.deposit_mct_id` 로 평탄화된 뒤 분석명(`rc_id`/`dpsts_rc_id`)으로 번역돼
    B와 같은 조인으로 식별된다(과거엔 미번역 → 오탐 ✗).
  - 즉 JOIN_GRAPH 가 일치(only_in_a == only_in_b == []) 해야 한다.
"""

from __future__ import annotations

from query_diff.models import Dialect, DimensionName, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff.schema_mapping import load_op_an_map

A_SQL = r'''
select
    a.player_id as 파트너코드,
    decode(b.RCGR_TYPE, '01', '일반충전상', '02', '대표충전상', '03', '하위충전상', RCGR_TYPE) as 충전상분류,
    a.name as "파트너명",
    NVL(c.total_deposit_amt, 0) as 총예치금액,
    (NVL(c.total_deposit_amt, 0) - d.rc_amt + d.cancel_rc_amt) as 예치금잔액,
    c.deposit_time as 이체일시,
    a.reg_date as 가입일,
    c.update_date as 업데이트일시
from kodasp.contract a
inner join kodasp.recharger b on b.player_id = a.player_id and b.role_cd = a.role_cd
left join (
    select
        player_id,
        min(total_deposit_amt) KEEP(DENSE_RANK FIRST ORDER BY deposit_time DESC) as total_deposit_amt,
        max(deposit_time) as deposit_time,
        max(update_date) as update_date
    from kodasp.RECHARGE_DEPOSIT
    where deposit_time <= to_date('20260615', 'yyyyMMdd')
    group by player_id
) c on c.player_id = a.player_id
left join (
    select /*+full(it)*/
        it.DEPOSIT_MCT_ID as DEPOSIT_MCT_ID,
        nvl(sum(case when it.PROCESSING_CODE in (210000, 213900, 403908, 213908, 243908, 244308, 243900, 214000) then
                case when it.PROCESSING_CODE = '213908' then it.ORG_AMT else it.TR_AMT end else 0 end), 0) as rc_amt,
        nvl(sum(case when it.PROCESSING_CODE in (010839, 020839) then it.TR_AMT else 0 end), 0) as cancel_rc_amt
    from ias.IAS_TRANSACTION it
    where it.ASP_ID = '953365000000000'
        and it.APPROVAL_DATE <= 20260615
        and it.PROCESSING_CODE in (210000, 213900, 403908, 213908, 243908, 244308, 243900, 214000, 010839, 020839)
        and it.RESPONSE_CODE = '00'
        and it.MTI = '0100'
        and (it.REVERSAL_DATE is null or it.REVERSAL_DATE >= TO_DATE('20260615', 'YYYYMMDD'))
    group by it.DEPOSIT_MCT_ID
) d on d.DEPOSIT_MCT_ID = a.player_id
where a.role_cd = 'RC'
'''

B_SQL = r'''
select
    a.ptn_id as 파트너코드,
    case b.rc_mc_rep_dv_cd
        when '01' then '일반충전상'
        when '02' then '대표충전상'
        when '03' then '하위충전상'
        else b.rc_mc_rep_dv_cd
    end as 충전상분류,
    a.ptn_nm as 파트너명,
    coalesce(c.total_deposit_amt, 0) as 총예치금액,
    (coalesce(c.total_deposit_amt, 0) - d.rc_amt + d.cancel_rc_amt) as 예치금잔액,
    c.deposit_time as 이체일시,
    a.sys_cre_dttm as 가입일,
    c.update_date as 업데이트일시
from kod.contract a
inner join kod.recharger b
    on b.rc_id = a.ptn_id
   and b.rc_role_cd = a.role_cd
left join (
    select
        rc_id,
        max(dpsi_dttm)                                  as deposit_time,
        max(sys_upd_dttm)                               as update_date,
        min(case when rn = 1 then acum_dpsts_bala end)  as total_deposit_amt
    from (
        select
            rc_id,
            acum_dpsts_bala,
            dpsi_dttm,
            sys_upd_dttm,
            dense_rank() over (partition by rc_id order by dpsi_dttm desc) as rn
        from kod.recharge_deposit
        where dpsi_dttm <= to_timestamp('${base_dt=20260615}', 'yyyyMMdd')
    ) t
    group by rc_id
) c on c.rc_id = a.ptn_id
left join (
    select
        it.dpsts_rc_id as dpsts_rc_id,
        coalesce(sum(case when it.pcs_cd in ('210000','213900','403908','213908','243908','244308','243900','214000') then
                case when it.pcs_cd = '213908' then it.gm_tr_amt else it.bala_use_amt end else 0 end), 0) as rc_amt,
        coalesce(sum(case when it.pcs_cd in ('010839','020839') then it.bala_use_amt else 0 end), 0) as cancel_rc_amt
    from ias.ias_transaction it
    where it.asp_id = '953365000000000'
        and it.apv_dt <= ${base_dt=20260615}
        and it.pcs_cd in ('210000','213900','403908','213908','243908','244308','243900','214000','010839','020839')
        and it.apv_rs_rsp_cd = '00'
        and it.mti_cd = '0100'
        and (it.af_prcs_dtl_dttm is null or it.af_prcs_dtl_dttm >= to_timestamp('${base_dt=20260615}', 'yyyyMMdd'))
    group by it.dpsts_rc_id
) d on d.dpsts_rc_id = a.ptn_id
where a.role_cd = 'RC'
'''


def _jg(diff):
    return next(d for d in diff.dimensions if d.dimension == DimensionName.JOIN_GRAPH)


def test_join_graph_matches_through_subqueries():
    """서브쿼리(파생 테이블) 출력 조인키가 매핑 관통돼 JOIN_GRAPH 가 일치한다."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    jg = _jg(diff)
    assert jg.matched, f"JOIN_GRAPH 불일치: A만={jg.only_in_a} B만={jg.only_in_b}"
    assert jg.only_in_a == [] and jg.only_in_b == []


def test_no_false_positive_op_an_column_noise():
    """과거 오탐 신호(미번역 운영명 vs 분석명)가 조인 그래프에 남지 않는다."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    jg = _jg(diff)
    blob = (jg.explanation + " " + " ".join(jg.only_in_a + jg.only_in_b)).lower()
    # 같은 조인을 다르게 보이게 했던 컬럼 쌍이 더는 차이로 노출되지 않는다.
    assert "deposit_mct_id" not in blob
    assert "dpsts_rc_id" not in blob


def test_base_tables_reconciled():
    """원천 베이스 테이블 집합이 양쪽 동일하게 정렬된다(서브쿼리 관통)."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    bt = next(d for d in diff.dimensions if d.dimension == DimensionName.BASE_TABLES)
    assert bt.matched, f"base tables 불일치: A만={bt.only_in_a} B만={bt.only_in_b}"
    assert {"contract", "recharger", "recharge_deposit", "ias_transaction"} <= set(diff.plan_a.base_tables)


def test_predicates_absorbed_date_funcs_and_qualification():
    """필터(WHERE/HAVING) 흡수: ① 날짜 파싱 함수(Oracle to_date→STR_TO_DATE,
    Hive to_timestamp→Anonymous)를 값 인자로 언랩, ② 옵티마이저 폴백(decode 미한정
    기본값 RCGR_TYPE)으로 미한정된 deposit_time 을 단일 테이블 스코프로 회복 한정
    → A·B 술어가 일치한다(과거엔 두 술어가 오탐으로 남았음)."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    pred = next(d for d in diff.dimensions if d.dimension == DimensionName.PREDICATES)
    assert pred.matched, f"PREDICATES 불일치: A만={pred.only_in_a} B만={pred.only_in_b}"
    assert pred.only_in_a == [] and pred.only_in_b == []
    # 날짜 파싱 함수 정규화 노이즈가 canonical 술어에 잔존하지 않는다.
    blob = " ".join(diff.plan_a.all_predicates).upper()
    assert "STR_TO_DATE" not in blob
    assert "ANONYMOUS" not in blob


def test_projections_decode_case_normalized():
    """비집계 출력 흡수: Oracle DECODE 와 Hive CASE WHEN 이 같은 코드→라벨 매핑이면
    동일한 검색형 CASE canonical 로 정규화돼 일치한다. bare decode 기본값(RCGR_TYPE)도
    동명 한정 형제(b.RCGR_TYPE)로 회복돼 양쪽 ELSE 가 같아진다."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    proj = next(d for d in diff.dimensions if d.dimension == DimensionName.PROJECTIONS)
    assert proj.matched, f"PROJECTIONS 불일치: A만={proj.only_in_a} B만={proj.only_in_b}"
    assert proj.only_in_a == [] and proj.only_in_b == []
    # DECODE/CASE 가 함수 호출형(DECODE_CASE/CASE(...))이 아니라 검색형 CASE 로 정규화됨.
    blob = " ".join(diff.plan_a.projections).upper()
    assert "DECODE_CASE" not in blob


def test_aggregates_positional_idiom_soft_matched():
    """집계 흡수: Oracle KEEP(DENSE_RANK FIRST) 와 Hive 윈도우+CASE(rn=1) '최신 1건' 집계를
    동치 간주(✗ 아님)하되 '정렬·파티션 확인 권장' 소프트 노트를 남긴다. 모든 차원이 일치하므로
    verdict 는 DIVERGENT 가 아니다(윈도우 정규화 제한으로 LIMITED)."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())
    agg = next(d for d in diff.dimensions if d.dimension == DimensionName.AGGREGATES)
    assert agg.matched, f"AGGREGATES 불일치: A만={agg.only_in_a} B만={agg.only_in_b}"
    # 헤드라인은 간결, 주의는 구조화 caveat 으로 분리.
    assert "집계식" in agg.explanation and "모두 동일" in agg.explanation
    # caveat 은 진짜 잔여(정렬 키 NULL)를 구조화로 안내(동률은 안전).
    assert "NULL" in agg.caveat and "Oracle" in agg.caveat and "Hive" in agg.caveat and "검토" in agg.caveat
    assert diff.verdict != SemanticVerdict.DIVERGENT
    # 소프트 동치는 ✓ 통과가 아니라 '제한적 판정'으로 표기돼야 한다.
    assert agg.limited is True
    # 완전 일치 차원은 제한적 판정이 아니다.
    bt = next(d for d in diff.dimensions if d.dimension == DimensionName.BASE_TABLES)
    assert bt.matched and bt.limited is False


def test_positional_agg_partition_mismatch_is_hard_diff():
    """가드: B 윈도우가 GROUP BY 와 다른 키로 파티션하면 '그룹별 최신'이 아니므로
    동치 간주하지 않고 하드 차이로 남는다(정렬·집계·값이 같아도)."""
    a = "select g, min(v) keep (dense_rank first order by t desc) m from tbl group by g"
    b = ("select g, min(case when rn=1 then v end) m from "
         "(select g, g2, v, t, dense_rank() over (partition by g2 order by t desc) rn from tbl) x "
         "group by g")
    diff = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
    agg = next(d for d in diff.dimensions if d.dimension == DimensionName.AGGREGATES)
    assert not agg.matched, "파티션이 GROUP BY 와 다른데 동치로 잘못 매칭됨"


def test_positional_agg_rank_function_mismatch_is_hard_diff():
    """가드: row_number(동률 중 1행)는 dense_rank(동률 모두)와 동률 시 결과가 달라
    KEEP(DENSE_RANK)와 동치로 매칭되면 안 된다."""
    a = "select g, min(v) keep (dense_rank first order by t desc) m from tbl group by g"
    b = ("select g, min(case when rn=1 then v end) m from "
         "(select g, v, t, row_number() over (partition by g order by t desc) rn from tbl) x "
         "group by g")
    diff = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
    agg = next(d for d in diff.dimensions if d.dimension == DimensionName.AGGREGATES)
    assert not agg.matched, "row_number 가 dense_rank(KEEP)와 동치로 잘못 매칭됨"


def test_keep_aggregate_not_confused_with_plain_min():
    """충실 표현 가드: `MIN(x) KEEP(최신순)` 은 plain `MIN(x)` 와 매칭되면 안 된다.
    (KEEP 을 통째로 버리던 잠복 결함 = 거짓 음성 방지)"""
    a = "select g, min(v) keep (dense_rank first order by t desc) m from tbl group by g"
    b = "select g, min(v) m from tbl group by g"
    diff = compare_semantic(a, Dialect.ORACLE, b, Dialect.HIVE)
    agg = next(d for d in diff.dimensions if d.dimension == DimensionName.AGGREGATES)
    assert not agg.matched, "KEEP 집계가 plain MIN 과 잘못 일치(충실 표현 실패)"
