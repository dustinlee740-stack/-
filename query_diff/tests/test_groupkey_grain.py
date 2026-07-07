"""GROUP BY grain 흡수 — 함수종속 상위날짜키(년월⊂년월일)·substr↔원본 컬럼을 엔진이 결정적으로
제한적(⚠) 판정으로 흡수하는지 검증. AI 판단 의존(✗/✓/⚠ 흔들림) 제거.

동일 컬럼명(dt·url)을 써서 op_an 없이도 흡수 로직만 격리 검증한다.
"""
from __future__ import annotations

from query_diff.models import Dialect, DimensionName
from query_diff.semantic_diff import compare_semantic

O, H = Dialect.ORACLE, Dialect.HIVE


def _gk(a, b):
    d = compare_semantic(a, O, b, H)
    return next(x for x in d.dimensions if x.dimension == DimensionName.GROUP_KEYS)


def test_api_pattern_substr_day_vs_raw_and_redundant_month():
    """A `substr(dt,1,8)[일],url` vs B `substr(dt,1,6)[월],dt[원본],url` → 함수종속 월 제거 +
    일↔원본 흡수 → matched + limited(⚠) + caveat(포맷 확인)."""
    gk = _gk(
        "select url, substr(dt,1,8) ymd, count(1) c from t group by substr(dt,1,8), url",
        "select substr(dt,1,6) ym, dt ymd, url, count(*) c from t group by 1,2,3",
    )
    assert gk.matched is True
    assert gk.limited is True
    assert "포맷" in gk.caveat or "함수종속" in gk.caveat, gk.caveat


def test_day_vs_month_both_substr_is_real_diff():
    """둘 다 substr(원본 없음)이고 입도가 일 vs 월이면 진짜 grain 차이 → matched=False(✗)."""
    gk = _gk(
        "select url, substr(dt,1,8) x, count(1) c from t group by substr(dt,1,8), url",
        "select url, substr(dt,1,6) x, count(1) c from t group by substr(dt,1,6), url",
    )
    assert gk.matched is False


def test_extra_nondate_key_is_real_diff():
    """B에 비-날짜 추가 그룹키(region)면 grain 이 실제로 달라짐 → matched=False(✗)."""
    gk = _gk(
        "select dt, url, count(1) c from t group by dt, url",
        "select dt, url, region, count(1) c from t group by dt, url, region",
    )
    assert gk.matched is False


def test_redundant_month_dropped_day_matches():
    """B가 월(substr)+일(substr) 둘 다 GROUP BY, A는 일만 → 월은 일에 함수종속이라 제거되고
    일=일 로 matched(원본↔substr 흡수 아님 → grain_soft 없음; 공유 YM 소프트 규칙만 적용)."""
    gk = _gk(
        "select url, substr(dt,1,8) d, count(1) c from t group by substr(dt,1,8), url",
        "select substr(dt,1,6) m, substr(dt,1,8) d, url, count(*) c from t group by 1,2,3",
    )
    assert gk.matched is True
