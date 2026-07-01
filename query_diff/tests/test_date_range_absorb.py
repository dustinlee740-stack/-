"""날짜 범위 경계값 차이를 파라미터로 흡수하는지 검증.

A·B가 같은 컬럼(매핑 후 `rqs_dt`)을 같은 연산자로 거르지만 조회 기간(날짜 경계값)만 다른 경우
(`rqs_dt <= 20250731` vs `<= 20241231`)는 '값만 다른 항목'으로 흡수해 조회 조건이 일치로 판정돼야
한다. 단 코드 등치(`status='A'` vs `'B'`)·일반 숫자 범위(`amt>=1000` vs `2000`)는 진짜 차이로 남는다.
"""

from __future__ import annotations

from query_diff.models import Dialect, DimensionName, QueryInput, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.semantic_diff.plan_compare import (
    _absorb_date_range,
    _absorb_parameterized,
    _absorb_qualifier_noise,
    _is_datelike,
)
from query_diff.structure_diff import compare_structures
from query_diff.structure_diff.schema_mapping import load_op_an_map
from query_diff.validation_service import validate_query_input


def test_is_datelike():
    for v in ["20250731", "202507", "2025-07-31", "2025-07"]:
        assert _is_datelike(v) is True, v
    for v in ["20000000", "1000", "'A0000'", "99999999", "12", "abc"]:
        assert _is_datelike(v) is False, v


def test_absorb_date_range_but_keep_real_diffs():
    # 날짜 경계값만 다름 → 흡수
    ra, rb, ab = _absorb_parameterized(
        ["t.rqs_dt <= 20250731", "t.rqs_dt >= 20250201"],
        ["t.rqs_dt <= 20241231", "t.rqs_dt >= 20240701"],
    )
    assert ra == [] and rb == [] and len(ab) == 2

    # 코드 등치 차이 → 유지(진짜 차이)
    ra, rb, ab = _absorb_parameterized(["t.status = 'A0000'"], ["t.status = 'B1111'"])
    assert ra and rb and not ab

    # 일반 숫자 범위 → 유지(날짜 아님)
    ra, rb, ab = _absorb_parameterized(["t.amt >= 1000"], ["t.amt >= 2000"])
    assert ra and rb and not ab


def test_date_range_pair_predicates_match():
    """매핑 + 날짜 범위 흡수 → 조회 조건 일치, verdict EQUIVALENT."""
    A = "SELECT tah.x FROM tgs.tb_api_history tah WHERE tah.request_dt >= 20250201 AND tah.request_dt <= 20250731"
    B = "SELECT tah.x FROM tgs.tb_api_history tah WHERE tah.rqs_dt >= 20240701 AND tah.rqs_dt <= 20241231"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    pred = next(d for d in r.dimensions if d.dimension == DimensionName.PREDICATES)
    assert pred.matched is True
    assert "값만 다른 항목" in pred.explanation
    assert r.verdict is SemanticVerdict.EQUIVALENT


def test_absorb_qualifier_noise():
    """한정자만 다른 동일 술어(맨컬럼↔한정)는 흡수, 다른 테이블·다른 값은 보존."""
    # 부정형 NULL≡'' 가 IS NOT NULL 로 정규화된 뒤 한정자만 다른 케이스(에이전트가 미존재 확인)
    ra, rb, ab = _absorb_qualifier_noise(
        ["view_x.old_par IS NOT NULL"], ["old_par IS NOT NULL"]
    )
    assert ra == [] and rb == [] and len(ab) == 1
    # 둘 다 한정(서로 다른 테이블) → 흡수 안 함(거짓흡수 방지)
    ra, rb, ab = _absorb_qualifier_noise(["t1.x = 5"], ["t2.x = 5"])
    assert ra and rb and not ab
    # 값이 다르면 키 불일치 → 흡수 안 함
    ra, rb, ab = _absorb_qualifier_noise(["t.x = 5"], ["x = 6"])
    assert ra and rb and not ab


def test_absorb_date_range_asymmetric():
    """원시 컬럼 범위(strict) ↔ YM 일추출 BETWEEN(파라미터) 비대칭 → 흡수 + caveat. 신호 없으면 보존."""
    ra, rb, cav = _absorb_date_range(
        ["v.created > 20190101000000", "v.created < 20251001000000"],
        ["⟨YM:v.created:DAY⟩ >= '__PLACEHOLDER__'", "⟨YM:v.created:DAY⟩ <= '__PLACEHOLDER__'"],
    )
    assert ra == [] and rb == [] and cav is True
    # 날짜맥락 신호(YM/플레이스홀더) 없는 임의 숫자범위 → 미흡수(거짓흡수 방지)
    ra, rb, cav = _absorb_date_range(
        ["t.amt > 1000", "t.amt < 2000"], ["t.amt > 5", "t.amt < 9"]
    )
    assert ra and rb and cav is False


_RAW_TS_A = """select to_char(created,'yyyy') 년도, count(1) 건수
from cdm.view_shipping_try_at_a_glance cdm
inner join kodasp.service ks on ks.svc_id = cdm.product_id
where cdm.created > to_date('20190101000000','yyyymmddhh24miss')
and cdm.created < to_date('20251001000000','yyyymmddhh24miss')
and cdm.old_par is not null
group by to_char(cdm.created,'yyyy')"""

_RAW_TS_B = """select from_timestamp(cdm.CREATED, 'yyyy') 년도, count(1) 건수
from cdm.view_shipping_try_at_a_glance cdm
inner join kod.service ks on ks.svc_id = cdm.product_id
where from_timestamp(cdm.CREATED, 'yyyyMMdd') between '${start_day}' and '${end_day}'
and OLD_PAR != ''
group by from_timestamp(cdm.CREATED, 'yyyy')"""


def test_raw_ts_vs_day_extract_range_semantic_limited():
    """원시 타임스탬프 범위(A) ↔ 일추출 BETWEEN+파라미터(B) + old_par 한정자 차이 → PREDICATES 제한적 일치."""
    r = compare_semantic(_RAW_TS_A, Dialect.ORACLE, _RAW_TS_B, Dialect.HIVE, op_an=load_op_an_map())
    pred = next(d for d in r.dimensions if d.dimension == DimensionName.PREDICATES)
    assert pred.matched is True and pred.limited is True
    blob = " | ".join(pred.only_in_a + pred.only_in_b).lower()
    assert "created" not in blob and "old_par" not in blob   # 날짜범위·한정자 모두 흡수
    assert "경계" in pred.caveat and "원시" in pred.caveat
    assert r.verdict is SemanticVerdict.LIMITED


def test_raw_ts_vs_day_extract_range_structure_softmatch():
    """구문 비교도 동일 — DATE_RANGE_SOFT_MATCH WARNING, WHERE 잔차 finding 없음(두 화면 일치)."""
    def _qi(sql, d):
        q = QueryInput(sql_raw=sql, dialect=d)
        validate_query_input(q)
        return q

    diff = compare_structures(_qi(_RAW_TS_A, Dialect.ORACLE), _qi(_RAW_TS_B, Dialect.HIVE), op_an=load_op_an_map())
    assert any(f.rule_id == "DATE_RANGE_SOFT_MATCH" for f in diff.findings)
    assert not any(f.rule_id.startswith("WHERE_PREDICATE_ONLY") for f in diff.findings)
