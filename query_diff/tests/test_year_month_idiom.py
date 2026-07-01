"""연-월(YYYYMM) 추출 관용구 흡수 검증.

오뱅 출금 통계 페어에서 A(Oracle) `substr(created_at,0,6)` 와 B(Hive)
`from_timestamp(sys_cre_dttm,'yyyyMM')` 는 컬럼 타입(TIMESTAMP↔DATE)이 달라 추출 방식이
다르지만 같은 연-월을 뽑는다. 이를 하나의 `⟨YM:col:gran⟩` 토큰으로 모아 GROUP BY·SELECT 가
거짓 차이(✗)로 뜨지 않게 하되, substr 의 문자열 포맷 의존성 때문에 **제한적 판정**(✓ 아님)으로
표기한다.
"""

from __future__ import annotations

import sqlglot

from query_diff.models import Dialect, DimensionName, QueryInput, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff import compare_structures
from query_diff.semantic_diff.analyzer import _ym_token_col
from query_diff.structure_diff.normalizer import YEAR_MONTH_MARK, _canonical_expr
from query_diff.structure_diff.schema_mapping import OpAnMap, load_op_an_map
from query_diff.validation_service import validate_query_input


def _canon(expr: str, dialect: str) -> str:
    return _canonical_expr(sqlglot.parse_one(expr, dialect=dialect), {})


def _qi(sql: str, dialect: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=dialect)
    validate_query_input(q)
    assert q.is_valid, f"검증 실패: {q.validation_error}"
    return q


# --- 단위: 관용구 정규화 ---------------------------------------------------

def test_year_month_idioms_collapse_to_same_token():
    """substr(0|1,6)·to_char·from_timestamp·date_format·from_unixtime 모두 같은 월 토큰."""
    month = "⟨YM:x.c:MONTH⟩"
    assert _canon("substr(x.c,0,6)", "oracle") == month
    assert _canon("substr(x.c,1,6)", "hive") == month
    assert _canon("to_char(x.c,'YYYYMM')", "oracle") == month
    assert _canon("from_timestamp(x.c,'yyyyMM')", "hive") == month
    assert _canon("date_format(x.c,'yyyyMM')", "hive") == month
    assert _canon("from_unixtime(x.c,'yyyyMM')", "hive") == month
    assert YEAR_MONTH_MARK in month


def test_granularity_is_distinguished():
    """연/월/일 입도가 다르면 토큰이 달라 매칭되지 않는다."""
    assert _canon("substr(x.c,0,4)", "oracle") == "⟨YM:x.c:YEAR⟩"
    assert _canon("substr(x.c,0,8)", "oracle") == "⟨YM:x.c:DAY⟩"
    assert _canon("to_char(x.c,'YYYY')", "oracle") == "⟨YM:x.c:YEAR⟩"
    assert _canon("to_char(x.c,'YYYYMMDD')", "oracle") == "⟨YM:x.c:DAY⟩"
    assert _canon("substr(x.c,0,4)", "oracle") != _canon("substr(x.c,0,6)", "oracle")


def test_non_date_prefixes_not_absorbed():
    """날짜 폭(4/6/8)이 아니거나 시간 성분이 있으면 흡수하지 않는다."""
    # 길이 5 → 날짜 prefix 아님
    assert YEAR_MONTH_MARK not in _canon("substr(x.c,0,5)", "oracle")
    # 시간 성분 포함 마스크 → 연-월 절단 아님(기존 CAST_STR 언랩으로 떨어짐)
    assert YEAR_MONTH_MARK not in _canon("to_char(x.c,'YYYYMMDDHH24MISS')", "oracle")
    # 포맷 없는 to_char(타입 캐스트) → 컬럼으로 언랩(기존 동작 유지)
    assert YEAR_MONTH_MARK not in _canon("to_char(x.id)", "oracle")


# --- 통합: 오뱅 출금 통계 페어 ---------------------------------------------

A_SQL = r"""
select substr(ow.created_at,0,6) 년월,
       '오뱅' PG,
       ow.req_client_bank_code 은행코드,
       count(1) 총건수,
       sum(decode(ow.api_rsp_code,'A0000',1,0)) 성공건수,
       sum(decode(ow.api_rsp_code,'A0000',0,1)) 실패건수
from cs.tb_pg_ob_withdraw ow
where ow.created_at between to_date('20250501','yyyymmdd') and to_date('20260601','yyyymmdd')
group by substr(ow.created_at,0,6), ow.req_client_bank_code
order by substr(ow.created_at,0,6), ow.req_client_bank_code
"""

B_SQL = r"""
SELECT from_timestamp(ow.sys_cre_dttm, 'yyyyMM') AS `년월`,
       '오뱅' AS `PG`,
       ow.trmsr_bank_cd AS `은행코드`,
       count(1) AS `총건수`,
       sum(CASE WHEN ow.api_rsp_cd = 'A0000' THEN 1 ELSE 0 END) AS `성공건수`,
       sum(CASE WHEN ow.api_rsp_cd = 'A0000' THEN 0 ELSE 1 END) AS `실패건수`
FROM cs.tb_pg_ob_withdraw ow
WHERE ow.sys_cre_dttm BETWEEN to_timestamp('20250501', 'yyyyMMdd') AND to_timestamp('20260601', 'yyyyMMdd')
GROUP BY from_timestamp(ow.sys_cre_dttm, 'yyyyMM'), ow.trmsr_bank_cd
ORDER BY from_timestamp(ow.sys_cre_dttm, 'yyyyMM'), ow.trmsr_bank_cd
"""


def _dim(diff, name):
    return next(d for d in diff.dimensions if d.dimension == name)


def test_token_parse_and_temporal_reliable():
    """토큰 col 파싱 + meta3 data_type 증거(양쪽 시간형) 판정."""
    assert _ym_token_col("⟨YM:tb_pg_ob_withdraw.sys_cre_dttm:MONTH⟩") == "tb_pg_ob_withdraw.sys_cre_dttm"
    assert _ym_token_col("SUBSTRING(x.c, 0, 5)") is None
    m = load_op_an_map()
    assert m.temporal_reliable("tb_pg_ob_withdraw.sys_cre_dttm") is True   # TIMESTAMP(6)↔DATE
    assert m.temporal_reliable("tb_pg_ob_withdraw.trmsr_bank_cd") is False  # VARCHAR
    assert m.temporal_reliable("nope.unknown") is False


def test_obank_pair_type_confirmed_equivalent():
    """양쪽 시간형(TIMESTAMP/DATE) 확정 → GROUP BY·SELECT 동일(✓), 제한적 아님."""
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=load_op_an_map())

    gk = _dim(diff, DimensionName.GROUP_KEYS)
    pj = _dim(diff, DimensionName.PROJECTIONS)
    for d in (gk, pj):
        assert d.matched is True
        assert d.limited is False         # 타입 증거로 동일 확정(제한적 아님)
        assert d.caveat == ""
        assert any(YEAR_MONTH_MARK in s for s in d.shared)
        assert "타입 검증" in d.explanation

    assert diff.verdict is SemanticVerdict.EQUIVALENT
    assert diff.issues == []


def test_year_month_soft_when_type_unknown():
    """타입 미상(temporal_keys 비움)이면 제한적 판정 + 캐비엇 유지(과추출 우선)."""
    base = load_op_an_map()
    # 캐시 인스턴스 변형 금지 → 타입 증거만 제거한 사본 구성
    op_an = OpAnMap(
        columns=base.columns,
        tables=base.tables,
        op_catalog=base.op_catalog,
        an_derived=base.an_derived,
        temporal_keys=set(),
    )
    diff = compare_semantic(A_SQL, Dialect.ORACLE, B_SQL, Dialect.HIVE, op_an=op_an)
    gk = _dim(diff, DimensionName.GROUP_KEYS)
    pj = _dim(diff, DimensionName.PROJECTIONS)
    for d in (gk, pj):
        assert d.matched is True
        assert d.limited is True
        cav = d.caveat.lower()
        assert "연-월" in d.caveat and "검토" in d.caveat        # MONTH 입도 라벨 + footer
        # 캐비엣은 **실제 A/B 추출식**(하드코딩 substr(첫 N자) 아님)
        assert "substr(ow.created_at" in cav
        assert "from_timestamp(ow.sys_cre_dttm" in cav
        assert "위치 추출" in d.caveat                          # A가 substr → 경고 포함
    assert diff.verdict is SemanticVerdict.LIMITED


def test_year_month_caveat_both_format_no_substr_warning():
    """양쪽 포맷 함수(to_char↔from_timestamp)·YEAR 입도 → 실제 식·정확한 입도, substr 경고 없음(사용자 지적)."""
    base = load_op_an_map()
    op_an = OpAnMap(
        columns=base.columns,
        tables=base.tables,
        op_catalog=base.op_catalog,
        an_derived=base.an_derived,
        temporal_keys=set(),
    )
    A = ("select to_char(cdm.created,'yyyy') 년도, count(1) c "
         "from cdm.view_shipping_try_at_a_glance cdm group by to_char(cdm.created,'yyyy')")
    B = ("select from_timestamp(cdm.CREATED,'yyyy') 년도, count(1) c "
         "from cdm.view_shipping_try_at_a_glance cdm group by from_timestamp(cdm.CREATED,'yyyy')")
    diff = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=op_an)
    gk = _dim(diff, DimensionName.GROUP_KEYS)
    assert gk.matched is True and gk.limited is True
    cav = gk.caveat
    assert "연(YYYY)" in cav                                    # 정확한 입도(연-월/YYYYMM 아님)
    assert "to_char(cdm.created" in cav.lower() and "from_timestamp(cdm.created" in cav.lower()
    assert "substr" not in cav.lower()                          # substr 안 썼으니 경고 없음
    assert "YYYYMM" not in cav


def test_obank_pair_structure_no_warning_when_type_confirmed():
    """구조 비교도 타입 확정이면 YEAR_MONTH_SOFT_MATCH WARNING 없음(동일 확정)."""
    a, b = _qi(A_SQL, Dialect.ORACLE), _qi(B_SQL, Dialect.HIVE)
    diff = compare_structures(a, b, op_an=load_op_an_map())
    assert not [f for f in diff.findings if f.rule_id == "YEAR_MONTH_SOFT_MATCH"]
    # GROUP BY/SELECT 가 관용구로 매칭됐으므로 미스매치 CRITICAL 도 없어야 함
    assert not any(f.rule_id == "GROUP_BY_COLUMN_MISMATCH" for f in diff.findings)
