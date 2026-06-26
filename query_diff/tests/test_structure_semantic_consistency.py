"""구문 비교 ↔ 의미 비교 일관성 회귀 테스트.

구문 비교(compare_structures)가 의미 비교(compare_semantic)와 **같은 정규화 프런트엔드**
(옵티마이저 → 번역 → CTE 관통 해소 → LogicalPlan)를 공유하므로, 두 비교의 결론이
항상 일관돼야 한다. 작성 스타일(WITH/JOIN/서브쿼리)·앵커·스키마명·파라미터 차이는 흡수되고
진짜 차이만 finding 으로 남는다.

- 캐시포인트 쿼리쌍: 의미=EQUIVALENT, 구문=진짜 차이(CRITICAL/WARNING) 없음(INFO 출력차만 허용).
- IAS 쿼리쌍: 의미=DIVERGENT, 구문=진짜 차이 3종(채널 CASE 조인 / simple_nm vs mc_nm / grp_nm).
"""

from __future__ import annotations

from query_diff.models import Dialect, QueryInput, SemanticVerdict, Severity
from query_diff.semantic_diff import compare_semantic
from query_diff.structure_diff import compare_structures
from query_diff.structure_diff.schema_mapping import load_op_an_map
from query_diff.validation_service import validate_query_input

from tests.test_point_policy_pair import A_SQL as CP_A, B_SQL as CP_B
from tests.test_real_query_pair import A_SQL as IAS_A, B_SQL as IAS_B


def _qi(sql: str, dialect: Dialect) -> QueryInput:
    q = QueryInput(sql_raw=sql, dialect=dialect)
    validate_query_input(q)
    assert q.is_valid, f"검증 실패: {q.validation_error}"
    return q


def test_cash_point_pair_structurally_equivalent():
    """캐시포인트: 의미=EQUIVALENT, 구문=진짜 차이 없음(스타일·파라미터 흡수)."""
    op_an = load_op_an_map()
    sem = compare_semantic(CP_A, Dialect.ORACLE, CP_B, Dialect.HIVE, op_an=op_an)
    assert sem.verdict == SemanticVerdict.EQUIVALENT

    d = compare_structures(_qi(CP_A, Dialect.ORACLE), _qi(CP_B, Dialect.HIVE), op_an=op_an)
    real = [f for f in d.findings if f.severity != Severity.INFO]
    assert not real, [(f.clause.value, f.rule_id, f.description) for f in real]
    assert d.fast_path_terminate is False


def test_ias_pair_structural_matches_semantic():
    """IAS: 의미=DIVERGENT, 구문=진짜 차이 3종이 그대로 finding 으로 노출."""
    op_an = load_op_an_map()
    sem = compare_semantic(IAS_A, Dialect.ORACLE, IAS_B, Dialect.HIVE, op_an=op_an)
    assert sem.verdict == SemanticVerdict.DIVERGENT

    d = compare_structures(_qi(IAS_A, Dialect.ORACLE), _qi(IAS_B, Dialect.HIVE), op_an=op_an)
    assert d.fast_path_terminate is True

    blob = "\n".join(
        f"{f.clause.value}|{f.rule_id}|{f.description}|{f.a_snippet}|{f.b_snippet}"
        for f in d.findings
    )
    # ① 채널 CASE 조인 (dcnt_group_mapping.channel)
    assert "channel" in blob and "JOIN_CONDITION_MISMATCH" in blob
    # ② 가맹점명 simple_nm(A) vs mc_nm(B) — MAX 인자 차이
    assert "simple_nm" in blob and "mc_nm" in blob
    # ③ grp_nm 그룹핑 차이
    assert "grp_nm" in blob and "GROUP_BY_COLUMN_MISMATCH" in blob


def test_ias_anchors_are_searchable_english():
    """차이 finding 의 앵커가 영문 식별자 + 원본 ON 텍스트로 표기돼 원본에서 찾을 수 있어야 한다."""
    op_an = load_op_an_map()
    d = compare_structures(_qi(IAS_A, Dialect.ORACLE), _qi(IAS_B, Dialect.HIVE), op_an=op_an)
    join = next(f for f in d.findings if f.rule_id == "JOIN_CONDITION_MISMATCH")
    # A측은 원본 운영 컬럼명으로 역번역되어 노출(분석명 dc_bnf_sno 등이 아니라 원본 ON 동반)
    assert "원본 ON" in join.a_snippet or "원본 ON" in join.b_snippet
