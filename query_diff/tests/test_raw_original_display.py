"""차이 표기 시 확인 필요 정보를 **원문 쿼리 그대로** 노출하는지 검증.

정규화형(`tb_api_history.rqs_dt <= 20250731`, `STR_TO_DATE`)이 아니라 사용자가 쓴 원문
(`tah.request_dt >= to_date(...)`, 원본 별칭·함수명)을 그대로 보여줘 쿼리에서 바로 찾게 한다.
JOIN 의 '원본 ON' 노출과 같은 맥락.
"""

from __future__ import annotations

from query_diff.models import Dialect, DimensionName
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.semantic_diff.plan_compare import _raw_predicate_map
from query_diff.semantic_diff.optimizer import normalize_query
from query_diff.structure_diff.schema_mapping import load_op_an_map


def test_raw_predicate_map_keeps_alias_and_func():
    """raw 맵은 원본 소스 리터럴(별칭·함수명 원형) 보존 — STR_TO_DATE 아닌 to_date."""
    sql = "SELECT x FROM t tah WHERE tah.request_dt >= to_date('20250201','yyyymmdd')"
    m = _raw_predicate_map(sql, "oracle")
    raws = m.col_map.get("request_dt")
    assert raws and "to_date" in raws[0].lower()         # 함수명 원형(STR_TO_DATE 아님)
    assert "tah." in raws[0].lower()                     # 원본 별칭 보존


def test_aggregate_keeps_alias_and_source_order():
    """집계 차이는 한글 출력명칭 유지 + 원문 순서 유지(COUNT(*) 가 맨 앞 아님)."""
    A = ("SELECT count(case when tah.http_status='200' then 1 end) 성공건수 "
         "FROM tgs.tb_api_history tah")
    B = ("SELECT sum(case when tah.http_rsp_st_dv_cd='200' then 1 else 0 end) 성공건수, "
         "sum(case when tah.http_rsp_st_dv_cd!='200' then 1 else 0 end) 실패건수, "
         "count (*) 총건수 FROM tgs.tb_api_history tah")
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    ag = next(d for d in r.dimensions if d.dimension == DimensionName.AGGREGATES)
    # 한글 별칭 노출
    assert any("성공건수" in x for x in ag.only_in_b)
    assert any("총건수" in x for x in ag.only_in_b)
    # 원문 순서: 성공건수 → 실패건수 → 총건수 (count(*) 마지막)
    joined = " || ".join(ag.only_in_b)
    assert joined.index("성공건수") < joined.index("실패건수") < joined.index("총건수")
    # count(*) 는 컬럼 없지만 정규형 매칭으로 원문(별칭 포함) 노출
    assert any("COUNT (*)" in x and "총건수" in x for x in ag.only_in_b)


def test_group_by_shows_original_expr_not_internal_token():
    """GROUP BY 차이는 비교용 내부 토큰(⟨YM:…⟩) 대신 **원문 식**·대문자로(리터럴 간격까지) 노출."""
    # A=일(substr 1,8) vs B=월(from_timestamp yyyyMM) — 입도가 달라 실제 grain 차이(✗).
    # (일↔원본 컬럼 같은 함수종속·grain 흡수 케이스는 test_groupkey_grain 에서 별도 검증)
    A = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY substr(tah.request_dt,0,8)"
    B = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY from_timestamp(tah.rqs_dt,'yyyyMM')"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    gk = next(d for d in r.dimensions if d.dimension == DimensionName.GROUP_KEYS)
    blob = " | ".join(gk.only_in_a + gk.only_in_b)
    assert "⟨" not in blob and "YM:" not in blob and "KEEP_" not in blob  # 내부 토큰 미노출
    assert "SUBSTR(TAH.REQUEST_DT,0,8)" in blob                            # 원문 리터럴·대문자
    assert "FROM_TIMESTAMP(TAH.RQS_DT,'yyyyMM')" in blob                   # 함수·간격 보존
    assert "'yyyyMM'" in blob                                              # 따옴표 안 리터럴 보존


def test_function_spelling_not_swapped():
    """A=substring(Oracle)·B=substr(Hive) — 방언 재렌더 스왑 없이 **각자 쓴 철자** 그대로."""
    A = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY substring(tah.request_dt,1,8)"
    B = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY substr(tah.rqs_dt,1,6)"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    gk = next(d for d in r.dimensions if d.dimension == DimensionName.GROUP_KEYS)
    a_blob = " | ".join(gk.only_in_a)
    b_blob = " | ".join(gk.only_in_b)
    assert "SUBSTRING(" in a_blob and "SUBSTR(" not in a_blob.replace("SUBSTRING", "")  # A=substring
    assert "SUBSTR(" in b_blob and "SUBSTRING(" not in b_blob                            # B=substr


def test_no_internal_tokens_anywhere_in_diff():
    """어떤 차원 차이에도 ⟨…⟩ 내부 토큰이 노출되지 않는다(원문 그대로 원칙)."""
    A = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY substr(tah.request_dt,0,6)"
    B = "SELECT 1 FROM tgs.tb_api_history tah GROUP BY to_char(tah.rqs_dt,'YYYYMMDD')"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    for d in r.dimensions:
        for s in d.only_in_a + d.only_in_b:
            assert "⟨" not in s and "⟩" not in s, (d.dimension, s)
    for i in r.issues:
        assert "⟨" not in i, i


def test_structure_findings_show_original_literal():
    """구문 비교(structure_diff) finding snippet 도 원문 리터럴·대문자·별칭·토큰 미노출(의미 비교와 동일)."""
    from query_diff.models import QueryInput
    from query_diff.structure_diff import compare_structures
    from query_diff.validation_service import validate_query_input

    def _qi(sql, d):
        q = QueryInput(sql_raw=sql, dialect=d)
        validate_query_input(q)
        return q

    A = "SELECT count(case when tah.http_status='200' then 1 end) 성공건수 FROM tgs.tb_api_history tah"
    B = ("SELECT sum(case when tah.http_rsp_st_dv_cd='200' then 1 else 0 end) 성공건수, "
         "count (*) 총건수 FROM tgs.tb_api_history tah")
    diff = compare_structures(_qi(A, Dialect.ORACLE), _qi(B, Dialect.HIVE), op_an=load_op_an_map())
    blob = " || ".join(f"{f.a_snippet} ; {f.b_snippet}" for f in diff.findings)
    assert "⟨" not in blob                              # 내부 토큰 미노출
    assert "성공건수" in blob                            # 한글 별칭 유지
    assert "COUNT (*)" in blob and "총건수" in blob      # count(*) 원문(공백)+별칭
    assert "SUM(" in blob                               # 원문 함수


def test_predicate_diff_shows_resolved_natural_grammar():
    """술어 차이는 **해소명 + 자연문법(`컬럼 op 값`·`!=`) + 원문 WHERE 순서**로 노출.

    canonical 정렬형(`값 = 컬럼`·`<>`·알파벳 정렬)이 아니라 사람이 원 쿼리와 대조하기 쉬운 형태.
    (GROUP BY/집계의 '원문 식' 표시와 달리 술어는 해소명을 유지 — 사용자 확정.)"""
    A = ("SELECT tah.x FROM tgs.tb_api_history tah "
         "WHERE tah.request_dt >= to_date('20250201','yyyymmdd') AND tah.api_rsp_code = 'A0000'")
    B = "SELECT tah.x FROM tgs.tb_api_history tah WHERE tah.rqs_url_hsh_val = 'Z9'"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=load_op_an_map())
    pred = next(d for d in r.dimensions if d.dimension == DimensionName.PREDICATES)
    assert pred.matched is False
    up = (" | ".join(pred.only_in_a)).upper()
    # 자연문법: 컬럼이 연산자 왼쪽(canonical 의 `값 = 컬럼` 정렬형 아님)
    assert "API_RSP_CODE = 'A0000'" in up and "'A0000' = " not in up
    # 원문 WHERE 순서 보존: request_dt(>=) → api_rsp_code(=)
    assert up.index("REQUEST_DT") < up.index("API_RSP_CODE")
    # 해소명 유지(원본 별칭 tah 아님)
    assert "TAH." not in up
