"""ODS 집계 테이블 원천 귀속 — "목적 동일 + 대사 필요 지점" 리포트 검증.

게이트: `QD_ODS_DIR` 에 `ODS_<T>.sql` 정의가 있을 때만 발동. 미설정/비-ODS/모호 → 현행(사이드이펙트 0).
테스트는 외부 경로(D:\\da\\ttp_workflow)에 의존하지 않도록 임시 폴더에 최소 정의 파일을 만들어 검증한다.
"""
from __future__ import annotations

import pytest

from query_diff.models import Dialect, DimensionName, QueryInput, SemanticVerdict
from query_diff.semantic_diff.analyzer import compare_semantic
from query_diff.structure_diff import compare_structures
from query_diff.validation_service import validate_query_input

# 최소 ODS 정의: 스파인=ias.ias_transaction(행-레벨, 집계 아님). **옆다리 GROUP BY lookup** 포함
# (bnf 유사) — 스파인 경로 밖이라 '집계 단위 차이(입도)'로 오탐하면 안 됨.
_MY_ODS = """upsert into table ods.my_ods
select a.par_no, a.amt, b.tot
from (select * from ias.ias_transaction where mti_cd != '0120' and apv_rs_rsp_cd in ('00','-1')) a
left join (select k, sum(x) tot from dim.z group by k) b on a.k = b.k
inner join dim.service s on a.svc_id = s.svc_id
"""

# 스파인 자체를 GROUP BY 로 묶는 ODS → 집계 입도(원장보다 굵음)
_AGG_ODS = """upsert into table ods.agg_ods
select a.mbr_id, sum(a.amt) tot from ias.ias_transaction a group by a.mbr_id
"""

# 다중 원천 ODS(UNION): ias_transaction + other.tbl → A(ias만)와 완전 귀속 불가
_MULTI_ODS = """upsert into table ods.multi_ods
select a.k from ias.ias_transaction a
union all
select b.k from other.tbl b
"""

# NULL→0 치환 ODS: 최상위 select 에 nvl(x,0)·coalesce(y,0) 적용. 0 아닌 기본값/비-리터럴/비-0 은 제외.
_NVL_ODS = """upsert into table ods.nvl_ods
select a.par_no,
       nvl(a.gm_tr_amt, 0) as gm_tr_amt,
       coalesce(a.dc_amt, 0),
       nvl(a.other_amt, 1) as other_amt,
       nvl(a.txt, 'x') as txt,
       nvl(a.chained, b.v) as chained,
       a.plain
from ias.ias_transaction a
left join dim.z b on a.k = b.k
"""


@pytest.fixture()
def ods_dir(tmp_path, monkeypatch):
    (tmp_path / "ODS_MY_ODS.sql").write_text(_MY_ODS, encoding="utf-8")
    (tmp_path / "ODS_AGG_ODS.sql").write_text(_AGG_ODS, encoding="utf-8")
    (tmp_path / "ODS_MULTI_ODS.sql").write_text(_MULTI_ODS, encoding="utf-8")
    (tmp_path / "ODS_NVL_ODS.sql").write_text(_NVL_ODS, encoding="utf-8")
    monkeypatch.setenv("QD_ODS_DIR", str(tmp_path))
    return tmp_path


def _qi(sql: str, d: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=d)
    validate_query_input(q)
    return q


def _bt(diff):
    return next(d for d in diff.dimensions if d.dimension == DimensionName.BASE_TABLES)


def test_ods_reconcile_spine_to_source(ods_dir):
    """B가 ODS 집계(my_ods, 스파인=ias_transaction)를 읽고 A가 원천을 읽으면 base_tables 동일(제한적)+대사 caveat."""
    A = "select par_no from ias.ias_transaction"
    B = "select par_no from ods.my_ods"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None)
    bt = _bt(r)
    assert bt.matched is True and bt.limited is True
    assert "MY_ODS → IAS_TRANSACTION" in bt.caveat        # 원천 귀속 경로
    assert "대사 필요" in bt.caveat
    # 구문 비교도 CRITICAL 아닌 소프트매치
    diff = compare_structures(_qi(A, Dialect.ORACLE), _qi(B, Dialect.HIVE), op_an=None)
    assert not any(f.rule_id == "TABLE_IDENTITY_MISMATCH" for f in diff.findings)
    assert any(f.rule_id == "ODS_LINEAGE_SOFT_MATCH" for f in diff.findings)


def test_ods_multi_source_not_reconciled(ods_dir):
    """다중 원천 ODS(UNION: ias_transaction+other.tbl)는 A(ias만)와 완전 귀속 불가 → 차이 유지 + 정보 caveat."""
    A = "select k from ias.ias_transaction"
    B = "select k from ods.multi_ods"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None)
    bt = _bt(r)
    assert bt.matched is False                    # 완전 귀속 안 됨(정직)
    assert bt.caveat and "ODS 집계" in bt.caveat   # 리니지 정보는 제공


def test_non_ods_table_unaffected(ods_dir):
    """정의 없는(비-ODS) 테이블 차이는 현행 그대로 ✗ (게이트 통과 못 함)."""
    r = compare_semantic("select x from t1", Dialect.ORACLE,
                         "select x from t2", Dialect.HIVE, op_an=None)
    bt = _bt(r)
    assert bt.matched is False and bt.limited is False and not bt.caveat


def test_inert_without_config(monkeypatch):
    """QD_ODS_DIR 미설정 → 기능 완전 비활성(ODS 테이블이어도 현행 ✗). 사이드이펙트 0."""
    monkeypatch.delenv("QD_ODS_DIR", raising=False)
    r = compare_semantic("select par_no from ias.ias_transaction", Dialect.ORACLE,
                         "select par_no from ods.my_ods", Dialect.HIVE, op_an=None)
    bt = _bt(r)
    assert bt.matched is False and bt.limited is False and not bt.caveat


def test_side_lookup_group_not_flagged_as_grain(ods_dir):
    """옆다리 LEFT JOIN lookup 의 GROUP BY 는 스파인 입도를 바꾸지 않음 → aggregated=False, '집계 단위 차이' 미표기."""
    from query_diff.semantic_diff.ods_lineage import resolve_ods_lineage
    lin = resolve_ods_lineage("my_ods")
    assert lin is not None and lin.spine == frozenset({"ias_transaction"})
    assert lin.aggregated is False                        # bnf 유사 옆다리 집계 오탐 안 함
    A = "select par_no from ias.ias_transaction"
    B = "select par_no from ods.my_ods"
    bt = _bt(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None))
    assert "집계 단위 차이" not in bt.caveat


def test_spine_group_flagged_as_grain(ods_dir):
    """스파인 자체를 GROUP BY 로 묶는 ODS → aggregated=True + '집계 단위 차이' 안내."""
    from query_diff.semantic_diff.ods_lineage import resolve_ods_lineage
    lin = resolve_ods_lineage("agg_ods")
    assert lin is not None and lin.aggregated is True
    A = "select mbr_id from ias.ias_transaction"
    B = "select mbr_id from ods.agg_ods"
    bt = _bt(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None))
    assert bt.matched is True and "집계 단위 차이" in bt.caveat


def test_null_default_cols_extraction(ods_dir):
    """최상위 select 의 nvl/coalesce(...,0) 출력 컬럼만 결정적 추출 — 0 아닌/비-리터럴 기본값 제외.

    - `nvl(a.gm_tr_amt, 0) as gm_tr_amt` → alias 'gm_tr_amt'
    - `coalesce(a.dc_amt, 0)` (alias 없음) → 내부 컬럼 'dc_amt'
    - `nvl(a.other_amt, 1)`(0 아님)·`nvl(a.txt, 'x')`(비수치)·`nvl(a.chained, b.v)`(비리터럴)·`a.plain`(nvl 없음) → 제외
    """
    from query_diff.semantic_diff.ods_lineage import resolve_ods_lineage
    lin = resolve_ods_lineage("nvl_ods")
    assert lin is not None
    assert lin.null_default_cols == ["gm_tr_amt", "dc_amt"]


def test_null_default_cols_empty_for_plain_ods(ods_dir):
    """nvl/coalesce 없는 ODS 정의 → null_default_cols 빈 목록(오탐 없음)."""
    from query_diff.semantic_diff.ods_lineage import resolve_ods_lineage
    assert resolve_ods_lineage("my_ods").null_default_cols == []


def _pred(diff):
    return next(d for d in diff.dimensions if d.dimension == DimensionName.PREDICATES)


def test_ods_predicate_absorption(ods_dir):
    """Fix6: A의 WHERE 필터가 B(ods.my_ods) 적재 정의에 동일 존재 → PREDICATES 흡수(matched·비-limited),
    DIVERGENT 아님. my_ods 적재부: `... where mti_cd != '0120' and apv_rs_rsp_cd in ('00','-1')`."""
    A = "select par_no from ias.ias_transaction where mti_cd != '0120' and apv_rs_rsp_cd in ('00','-1')"
    B = "select par_no from ods.my_ods"
    r = compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None)
    pred = _pred(r)
    assert pred.matched is True and pred.limited is False   # 흡수 → ✓ (증분 위험은 BASE_TABLES 소관)
    assert not pred.only_in_a
    assert "흡수" in pred.caveat
    assert r.verdict != SemanticVerdict.DIVERGENT           # 확정 실차이 아님


def test_ods_predicate_absorption_partial(ods_dir):
    """Fix6 보수성: ODS 정의에 대응 없는 A 필터는 흡수 안 됨 → only_in_a 잔존(✗). mti_cd 만 흡수."""
    A = "select par_no from ias.ias_transaction where mti_cd != '0120' and extra_col = '9'"
    B = "select par_no from ods.my_ods"
    pred = _pred(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None))
    assert pred.matched is False                            # extra_col 미대응 → 잔존
    assert any("EXTRA_COL" in x.upper() for x in pred.only_in_a)
    assert not any("MTI_CD" in x.upper() for x in pred.only_in_a)  # mti_cd 는 흡수됨


def test_ods_predicate_absorption_inert_without_config(monkeypatch):
    """QD_ODS_DIR 미설정 → 흡수 무동작(비-ODS 현행). A 필터는 only_in_a 로 남음."""
    monkeypatch.delenv("QD_ODS_DIR", raising=False)
    A = "select par_no from ias.ias_transaction where mti_cd != '0120'"
    B = "select par_no from ods.my_ods"
    pred = _pred(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None))
    assert pred.matched is False and pred.only_in_a


def _proj(diff):
    return next(d for d in diff.dimensions if d.dimension == DimensionName.PROJECTIONS)


def test_ods_projection_nvl_flagged(ods_dir):
    """Fix8: select * 로 nvl ODS(nvl_ods: gm_tr_amt·dc_amt 가 nvl(...,0))를 읽으면 base PROJECTIONS 가
    limited=True + 결정적 컬럼 caveat. `/execute` 자체가 nvl 위험을 완전 표기(AI 무관)."""
    A = "select * from ias.ias_transaction"
    B = "select * from ods.nvl_ods"
    proj = _proj(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None))
    assert proj.matched is True and proj.limited is True
    assert "gm_tr_amt" in proj.caveat and "dc_amt" in proj.caveat
    assert "NULL→0" in proj.caveat


def test_ods_projection_no_nvl_clean(ods_dir):
    """Fix8 오탐 방지: nvl 없는 ODS(my_ods)를 읽으면 PROJECTIONS ✓(limited=False)."""
    A = "select * from ias.ias_transaction"
    B = "select * from ods.my_ods"
    assert _proj(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None)).limited is False


def test_ods_projection_nvl_inert_without_config(monkeypatch):
    """QD_ODS_DIR 미설정 → PROJECTIONS nvl 무동작(비-ODS 현행 ✓)."""
    monkeypatch.delenv("QD_ODS_DIR", raising=False)
    A = "select * from ias.ias_transaction"
    B = "select * from ods.nvl_ods"
    assert _proj(compare_semantic(A, Dialect.ORACLE, B, Dialect.HIVE, op_an=None)).limited is False
