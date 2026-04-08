"""쿼리 비교 모듈 테스트"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from query_diff.api import app
from query_diff.models import Dialect, DiffMetric, QueryInput
from query_diff.store import store
from query_diff.validation_service import validate_sql, validate_query_input, _preprocess_sql
from query_diff.wiki_service import (
    extract_sql_blocks_from_html,
    extract_sql_from_url,
    fetch_confluence_page,
    _validate_url_not_internal,
)


client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    """매 테스트 전 store 초기화 — 테스트 간 격리 보장"""
    store.clear()
    yield
    store.clear()


# --- 도메인 모델 테스트 ---

class TestDiffMetric:
    def test_diff_calculation(self):
        m = DiffMetric(metric_name="매출합계", value_a=Decimal("10000"), value_b=Decimal("9900"))
        assert m.diff_value == Decimal("100")
        assert m.diff_pct == Decimal("1.00")

    def test_zero_a(self):
        m = DiffMetric(metric_name="건수", value_a=Decimal("0"), value_b=Decimal("100"))
        assert m.diff_value == Decimal("-100")
        assert m.diff_pct == Decimal("0")

    def test_equal_values(self):
        m = DiffMetric(metric_name="건수", value_a=Decimal("500"), value_b=Decimal("500"))
        assert m.diff_value == Decimal("0")
        assert m.diff_pct == Decimal("0.00")


# --- SQL 검증 테스트 ---

class TestValidation:
    def test_valid_oracle_sql(self):
        sql = "SELECT emp_no, SUM(sal) FROM hr.employee WHERE status = 'A' GROUP BY emp_no"
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True
        assert result.structure is not None
        assert result.structure.select_columns == 2
        assert result.structure.group_by_columns == 1
        assert result.structure.where_conditions >= 1

    def test_valid_hive_sql(self):
        sql = "SELECT dept_code, COUNT(*) FROM dwh.dim_employee GROUP BY dept_code"
        result = validate_sql(sql, Dialect.HIVE)
        assert result.is_valid is True
        assert result.structure.select_columns == 2

    def test_join_detection(self):
        sql = """
        SELECT a.id, b.name
        FROM table_a a
        JOIN table_b b ON a.id = b.a_id
        LEFT JOIN table_c c ON a.id = c.a_id
        """
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True
        assert result.structure.joins == 2

    def test_empty_sql(self):
        result = validate_sql("", Dialect.ORACLE)
        assert result.is_valid is False

    def test_query_input_validation(self):
        qi = QueryInput(sql_raw="SELECT 1 FROM dual", dialect=Dialect.ORACLE)
        result = validate_query_input(qi)
        assert result.is_valid is True
        assert qi.is_valid is True
        assert qi.sql_normalized is not None

    def test_template_variable_preprocessing(self):
        """${name=default} 템플릿 변수가 기본값으로 치환되어 파싱 성공"""
        sql = "SELECT * FROM t WHERE id = '${aspId=000140000000000}' AND dt BETWEEN ${start=20260201} AND ${end=20260231}"
        result = validate_sql(sql, Dialect.HIVE)
        assert result.is_valid is True

    def test_preprocess_template_vars(self):
        assert _preprocess_sql("${start=20260201}") == "20260201"
        assert _preprocess_sql("'${aspId=ABC123}'") == "'ABC123'"
        assert _preprocess_sql("${noDefault}") == "'__PLACEHOLDER__'"

    def test_hive_korean_alias(self):
        """한글 alias를 따옴표 없이 사용한 HiveQL 파싱"""
        sql = """select
            year(so.apv_dtl_dttm) 연도,
            from_timestamp(so.apv_dtl_dttm, 'yyyyMM') 년월,
            so.asp_id ASP_ID,
            ka.ptn_nm KA명,
            sum(case when pcs_cd != '200800' then gm_tr_amt else 0 end) as 결제금액
            from ods.stlm_ods so
            inner join kod.contract ka on ka.ptn_id = so.ka_id
            where so.apv_dt between ${start=20260201} and ${end=20260231}
            group by 1, 2, 3, 4"""
        result = validate_sql(sql, Dialect.HIVE)
        assert result.is_valid is True
        assert result.structure.joins == 1
        assert result.structure.where_conditions >= 1

    def test_hive_no_oracle_suggestion(self):
        """Hive SQL 파싱 실패 시 Oracle 제안을 하지 않음"""
        sql = "SELECT INVALID SYNTAX @@@ FROM t"
        result = validate_sql(sql, Dialect.HIVE)
        assert result.is_valid is False
        # Hive 파싱 실패 시 Oracle을 제안하면 안 됨
        if result.suggestion:
            assert "oracle" not in result.suggestion.lower()


# --- Wiki 추출 테스트 ---

class TestWikiExtract:
    def test_extract_from_pre_code(self):
        html = """
        <div>
            <p>아래는 매출 쿼리입니다.</p>
            <pre><code class="language-sql">SELECT * FROM sales WHERE year = 2024</code></pre>
        </div>
        """
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 1
        assert "SELECT" in blocks[0].preview
        assert blocks[0].language == "sql"

    def test_extract_from_code_fence(self):
        html = """
        <div>
        ```sql
        SELECT emp_no FROM hr.employee
        ```
        </div>
        """
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) >= 1

    def test_no_sql_blocks(self):
        html = "<div><p>이 페이지에는 SQL이 없습니다.</p></div>"
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 0

    def test_multiple_blocks(self):
        html = """
        <pre><code>SELECT * FROM a</code></pre>
        <pre><code>SELECT * FROM b</code></pre>
        """
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 2
        assert blocks[0].index == 0
        assert blocks[1].index == 1


# --- API 테스트 ---

class TestAPI:
    def test_create_comparison(self):
        res = client.post("/api/comparisons?title=테스트")
        assert res.status_code == 200
        data = res.json()
        assert "id" in data
        assert data["status"] == "DRAFT"

    def test_full_workflow(self):
        # 1. 생성
        res = client.post("/api/comparisons?title=매출비교")
        req_id = res.json()["id"]

        # 2. A쿼리 입력
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "TEXT",
            "sql_raw": "SELECT emp_no, SUM(sal) FROM employee GROUP BY emp_no",
            "dialect": "oracle",
        })
        assert res.status_code == 200

        # 3. B쿼리 입력
        res = client.put(f"/api/comparisons/{req_id}/query-b", json={
            "source_type": "TEXT",
            "sql_raw": "SELECT employee_id, SUM(salary) FROM dim_employee GROUP BY employee_id",
            "dialect": "hive",
        })
        assert res.status_code == 200

        # 4. 차이 요약
        res = client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "급여합계", "value_a": 10000, "value_b": 9900}]
        })
        assert res.status_code == 200

        # 5. 검증
        res = client.post(f"/api/comparisons/{req_id}/validate")
        assert res.status_code == 200
        data = res.json()
        assert data["query_a"]["is_valid"] is True
        assert data["query_b"]["is_valid"] is True

        # 6. 실행
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 200
        assert res.json()["status"] == "DONE"

    def test_validate_without_sql(self):
        res = client.post("/api/comparisons?title=빈쿼리")
        req_id = res.json()["id"]

        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is False
        assert data["query_b"]["is_valid"] is False

    def test_execute_without_validation(self):
        res = client.post("/api/comparisons?title=미검증")
        req_id = res.json()["id"]
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 400

    def test_not_found(self):
        res = client.get("/api/comparisons/nonexistent-id")
        assert res.status_code == 404


# --- API 통합 흐름 테스트 ---

class TestAPIIntegration:
    """API 엔드포인트 간 상태 전이 및 흐름 통합 테스트"""

    def _create_and_setup(self, sql_a="SELECT 1 FROM dual", sql_b="SELECT 1 FROM t",
                          dialect_a="oracle", dialect_b="hive"):
        """비교 요청 생성 후 A/B 쿼리와 요약을 세팅하는 헬퍼"""
        res = client.post("/api/comparisons?title=통합테스트")
        req_id = res.json()["id"]
        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "TEXT", "sql_raw": sql_a, "dialect": dialect_a,
        })
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "source_type": "TEXT", "sql_raw": sql_b, "dialect": dialect_b,
        })
        client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "건수", "value_a": 1000, "value_b": 990}]
        })
        return req_id

    # --- 상태 전이 검증 ---

    def test_status_draft_after_create(self):
        """생성 직후 상태는 DRAFT"""
        res = client.post("/api/comparisons?title=상태테스트")
        assert res.json()["status"] == "DRAFT"

    def test_status_ready_after_valid_validation(self):
        """A/B 모두 유효하면 검증 후 READY"""
        req_id = self._create_and_setup()
        client.post(f"/api/comparisons/{req_id}/validate")
        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "READY"

    def test_status_error_when_a_invalid(self):
        """A쿼리만 유효하지 않으면 ERROR"""
        req_id = self._create_and_setup(
            sql_a="INVALID @@@ SQL SYNTAX",
            sql_b="SELECT 1 FROM t",
        )
        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is False
        assert data["query_b"]["is_valid"] is True

        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "ERROR"

    def test_status_error_when_b_invalid(self):
        """B쿼리만 유효하지 않으면 ERROR"""
        req_id = self._create_and_setup(
            sql_a="SELECT 1 FROM dual",
            sql_b="INVALID @@@ SQL SYNTAX",
        )
        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is True
        assert data["query_b"]["is_valid"] is False

        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "ERROR"

    def test_status_done_after_execute(self):
        """실행 후 DONE"""
        req_id = self._create_and_setup()
        client.post(f"/api/comparisons/{req_id}/validate")
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.json()["status"] == "DONE"

    # --- 쿼리 수정 시 상태 리셋 ---

    def test_query_update_resets_to_draft(self):
        """검증(READY) 후 쿼리 수정하면 DRAFT로 리셋"""
        req_id = self._create_and_setup()
        client.post(f"/api/comparisons/{req_id}/validate")
        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "READY"

        # A쿼리 수정 → DRAFT로 리셋
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "SELECT col1, col2 FROM new_table",
        })
        assert res.json()["status"] == "DRAFT"
        # 검증 상태도 초기화
        assert res.json()["query_a"]["is_valid"] is None
        assert res.json()["query_a"]["structure"] is None

    def test_query_b_update_resets_to_draft(self):
        """B쿼리 수정 시에도 DRAFT로 리셋"""
        req_id = self._create_and_setup()
        client.post(f"/api/comparisons/{req_id}/validate")

        res = client.put(f"/api/comparisons/{req_id}/query-b", json={
            "dialect": "mysql",
        })
        assert res.json()["status"] == "DRAFT"
        assert res.json()["query_b"]["is_valid"] is None

    # --- 재검증 흐름 (fix-and-retry) ---

    def test_fix_and_revalidate(self):
        """잘못된 SQL → ERROR → 수정 → 재검증 → READY"""
        req_id = self._create_and_setup(sql_a="INVALID SYNTAX @@@")

        # 1차 검증: 실패
        res = client.post(f"/api/comparisons/{req_id}/validate")
        assert res.json()["query_a"]["is_valid"] is False

        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "ERROR"

        # SQL 수정
        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "SELECT id FROM fixed_table",
        })

        # 2차 검증: 성공
        res = client.post(f"/api/comparisons/{req_id}/validate")
        assert res.json()["query_a"]["is_valid"] is True
        assert res.json()["query_b"]["is_valid"] is True

        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "READY"

    # --- 실행 조건 검증 ---

    def test_execute_requires_metrics(self):
        """READY 상태여도 지표 없으면 실행 불가"""
        res = client.post("/api/comparisons?title=지표없음")
        req_id = res.json()["id"]

        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "SELECT 1 FROM dual", "dialect": "oracle",
        })
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "sql_raw": "SELECT 1 FROM t", "dialect": "hive",
        })
        client.post(f"/api/comparisons/{req_id}/validate")

        # 지표 없이 실행
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 400
        assert "차이 요약" in res.json()["detail"]

    def test_execute_rerun_allowed(self):
        """DONE 상태에서 재실행 가능"""
        req_id = self._create_and_setup()
        client.post(f"/api/comparisons/{req_id}/validate")
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.json()["status"] == "DONE"

        # 재실행
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 200
        assert res.json()["status"] == "DONE"

    # --- 부분 업데이트 ---

    def test_partial_update_preserves_fields(self):
        """dialect만 변경해도 sql_raw은 유지"""
        req_id = self._create_and_setup()
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "dialect": "mysql",
        })
        data = res.json()
        assert data["query_a"]["dialect"] == "mysql"
        assert data["query_a"]["sql_raw"] == "SELECT 1 FROM dual"

    # --- 요약 지표 검증 ---

    def test_summary_diff_calculation(self):
        """API 응답에서 diff_value, diff_pct 자동 계산 확인"""
        req_id = self._create_and_setup()
        res = client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [
                {"metric_name": "매출합계", "value_a": 10000, "value_b": 9900},
                {"metric_name": "건수", "value_a": 500, "value_b": 500},
            ]
        })
        data = res.json()
        metrics = data["summary"]["metrics"]
        assert len(metrics) == 2

        m0 = metrics[0]
        assert m0["metric_name"] == "매출합계"
        assert float(m0["diff_value"]) == 100.0
        assert float(m0["diff_pct"]) == 1.0

        m1 = metrics[1]
        assert float(m1["diff_value"]) == 0.0
        assert float(m1["diff_pct"]) == 0.0

    def test_summary_overwrite(self):
        """요약을 다시 PUT하면 이전 지표가 대체됨"""
        req_id = self._create_and_setup()

        # 첫 번째 요약
        client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "A", "value_a": 100, "value_b": 90}]
        })
        # 두 번째 요약으로 대체
        res = client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "B", "value_a": 200, "value_b": 150}]
        })
        data = res.json()
        assert len(data["summary"]["metrics"]) == 1
        assert data["summary"]["metrics"][0]["metric_name"] == "B"

    # --- 목록 조회 ---

    def test_list_comparisons(self):
        """여러 비교 요청 생성 후 목록 조회"""
        ids = set()
        for title in ["목록1", "목록2", "목록3"]:
            res = client.post(f"/api/comparisons?title={title}")
            ids.add(res.json()["id"])

        res = client.get("/api/comparisons")
        all_ids = {item["id"] for item in res.json()}
        assert all_ids == ids  # store 격리로 정확히 3개만 존재

    # --- 404 전체 엔드포인트 ---

    def test_404_all_endpoints(self):
        """존재하지 않는 ID로 모든 엔드포인트 호출 시 404"""
        fake_id = "nonexistent-id-12345"

        assert client.get(f"/api/comparisons/{fake_id}").status_code == 404
        assert client.put(f"/api/comparisons/{fake_id}/query-a", json={
            "sql_raw": "SELECT 1"
        }).status_code == 404
        assert client.put(f"/api/comparisons/{fake_id}/query-b", json={
            "sql_raw": "SELECT 1"
        }).status_code == 404
        assert client.put(f"/api/comparisons/{fake_id}/summary", json={
            "metrics": []
        }).status_code == 404
        assert client.post(f"/api/comparisons/{fake_id}/validate").status_code == 404
        assert client.post(f"/api/comparisons/{fake_id}/execute").status_code == 404

    # --- 실 운영 HiveQL 템플릿 변수 통합 흐름 ---

    def test_template_var_hive_full_flow(self):
        """실 운영 HiveQL (템플릿 변수 + 한글 alias + JOIN) 전체 흐름"""
        hive_sql = """select
            year(so.apv_dtl_dttm) 연도,
            from_timestamp(so.apv_dtl_dttm, 'yyyyMM') 년월,
            so.asp_id ASP_ID,
            ka.ptn_nm KA명,
            sum(case when pcs_cd != '200800' then gm_tr_amt else 0 end) as 결제금액
            from ods.stlm_ods so
            inner join kod.contract ka on ka.ptn_id = so.ka_id
            where so.apv_dt between ${start=20260201} and ${end=20260231}
            and so.asp_id = '${aspId=000140000000000}'
            group by 1, 2, 3, 4"""

        oracle_sql = """SELECT
            TO_CHAR(s.apv_dtl_dttm, 'YYYY') AS year_val,
            TO_CHAR(s.apv_dtl_dttm, 'YYYYMM') AS month_val,
            s.asp_id,
            k.ptn_nm,
            SUM(CASE WHEN pcs_cd != '200800' THEN gm_tr_amt ELSE 0 END) AS pay_amt
            FROM hr.stlm s
            INNER JOIN hr.contract k ON k.ptn_id = s.ka_id
            WHERE s.apv_dt BETWEEN 20260201 AND 20260231
            GROUP BY TO_CHAR(s.apv_dtl_dttm, 'YYYY'), TO_CHAR(s.apv_dtl_dttm, 'YYYYMM'),
                     s.asp_id, k.ptn_nm"""

        # 1. 생성
        res = client.post("/api/comparisons?title=결제금액 운영-분석 비교")
        req_id = res.json()["id"]

        # 2. A쿼리 (Oracle)
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "TEXT", "sql_raw": oracle_sql, "dialect": "oracle",
        })
        assert res.status_code == 200

        # 3. B쿼리 (HiveQL with template vars)
        res = client.put(f"/api/comparisons/{req_id}/query-b", json={
            "source_type": "TEXT", "sql_raw": hive_sql, "dialect": "hive",
        })
        assert res.status_code == 200

        # 4. 차이 요약
        res = client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [
                {"metric_name": "결제금액합계", "value_a": 1500000, "value_b": 1499800},
            ]
        })
        assert res.status_code == 200

        # 5. 검증 — 양쪽 모두 파싱 성공해야 함
        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is True, f"Oracle 파싱 실패: {data['query_a'].get('error_message')}"
        assert data["query_b"]["is_valid"] is True, f"Hive 파싱 실패: {data['query_b'].get('error_message')}"

        # 구조 분석 확인
        assert data["query_a"]["structure"]["joins"] >= 1
        assert data["query_b"]["structure"]["joins"] >= 1

        # 6. GET으로 상태 확인
        res = client.get(f"/api/comparisons/{req_id}")
        req_data = res.json()
        assert req_data["status"] == "READY"
        assert req_data["query_b"]["sql_normalized"] is not None  # 정규화 SQL 저장됨

        # 7. 실행
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 200
        assert res.json()["status"] == "DONE"

    # --- 구조 분석 결과 반영 검증 ---

    def test_structure_persisted_after_validation(self):
        """검증 후 구조 분석 결과가 ComparisonRequest에 저장됨"""
        req_id = self._create_and_setup(
            sql_a="""SELECT a.id, a.name, b.amount
                     FROM orders a
                     JOIN customers b ON a.cust_id = b.id
                     LEFT JOIN regions r ON b.region_id = r.id
                     WHERE a.status = 'active' AND a.amount > 100
                     GROUP BY a.id, a.name, b.amount
                     HAVING SUM(b.amount) > 500
                     ORDER BY a.name""",
            sql_b="SELECT id, name FROM dim_orders GROUP BY id, name",
        )
        client.post(f"/api/comparisons/{req_id}/validate")

        res = client.get(f"/api/comparisons/{req_id}")
        data = res.json()

        struct_a = data["query_a"]["structure"]
        assert struct_a["select_columns"] == 3
        assert struct_a["joins"] == 2
        assert struct_a["where_conditions"] >= 2
        assert struct_a["group_by_columns"] == 3
        assert struct_a["having_conditions"] >= 1
        assert struct_a["order_by_columns"] == 1

        struct_b = data["query_b"]["structure"]
        assert struct_b["select_columns"] == 2
        assert struct_b["joins"] == 0
        assert struct_b["group_by_columns"] == 2


# --- 엣지 케이스 테스트 ---

class TestEdgeCases:
    """경계값, 특수 입력, 비정상 흐름 엣지 케이스"""

    # --- SQL 전처리 엣지 케이스 ---

    def test_preprocess_multiple_template_vars(self):
        """단일 SQL에 다수 템플릿 변수 혼합"""
        sql = "SELECT * FROM t WHERE a=${v1=10} AND b='${v2=hello}' AND c=${v3}"
        result = _preprocess_sql(sql)
        assert "10" in result           # 숫자 기본값
        assert "hello" in result        # 문자열 기본값 (외부 따옴표 안)
        assert "__PLACEHOLDER__" in result  # 기본값 없음

    def test_preprocess_empty_default(self):
        """기본값이 빈 문자열인 템플릿 변수 ${name=}"""
        result = _preprocess_sql("WHERE x = '${key=}'")
        # 빈 기본값 → 빈 문자열로 치환, 파싱 깨지지 않아야 함
        assert "${" not in result

    def test_preprocess_no_template_vars(self):
        """템플릿 변수 없는 SQL은 그대로 통과"""
        sql = "SELECT id FROM users WHERE name = 'test'"
        assert _preprocess_sql(sql) == sql

    def test_preprocess_dollar_not_template(self):
        """$만 있고 {}가 없는 경우 치환하지 않음"""
        sql = "SELECT $price FROM t"
        assert _preprocess_sql(sql) == sql

    # --- SQL 파싱 엣지 케이스 ---

    def test_whitespace_only_sql(self):
        """공백만 있는 SQL"""
        result = validate_sql("   \n\t  ", Dialect.ORACLE)
        assert result.is_valid is False

    def test_comment_only_sql(self):
        """주석만 있는 SQL"""
        result = validate_sql("-- 이건 주석입니다\n/* 블록 주석 */", Dialect.ORACLE)
        assert result.is_valid is False

    def test_semicolon_terminated_sql(self):
        """세미콜론으로 끝나는 SQL"""
        result = validate_sql("SELECT 1 FROM dual;", Dialect.ORACLE)
        assert result.is_valid is True

    def test_multiline_sql_with_korean_comments(self):
        """한글 주석(--구분자)이 포함된 SQL"""
        sql = """
        --매출 집계 쿼리
        SELECT
            dept_cd,  --부서코드
            SUM(amt)  --금액합계
        FROM sales
        --조건절
        WHERE yr = 2026
        GROUP BY dept_cd
        """
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True
        assert result.structure.select_columns == 2

    def test_nested_subquery(self):
        """중첩 서브쿼리 카운트"""
        sql = """
        SELECT * FROM (
            SELECT id FROM (
                SELECT id FROM innermost
            ) sub1
        ) sub2
        """
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True
        assert result.structure.subqueries == 2

    def test_cte_with_query(self):
        """CTE(WITH절) 포함 SQL"""
        sql = """
        WITH base AS (
            SELECT dept_cd, SUM(amt) AS total
            FROM sales
            GROUP BY dept_cd
        )
        SELECT dept_cd, total
        FROM base
        WHERE total > 1000
        """
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True
        assert result.structure.select_columns >= 2

    def test_union_query(self):
        """UNION 쿼리"""
        sql = """
        SELECT id, name FROM table_a
        UNION ALL
        SELECT id, name FROM table_b
        """
        result = validate_sql(sql, Dialect.ORACLE)
        assert result.is_valid is True

    # --- DiffMetric 엣지 케이스 ---

    def test_diff_metric_negative_values(self):
        """음수 값이 있는 지표"""
        m = DiffMetric(metric_name="손익", value_a=Decimal("-500"), value_b=Decimal("-600"))
        assert m.diff_value == Decimal("100")  # -500 - (-600) = 100
        assert m.diff_pct == Decimal("-20.00")  # 100 / -500 * 100

    def test_diff_metric_large_numbers(self):
        """큰 수 정밀도"""
        m = DiffMetric(metric_name="매출", value_a=Decimal("9999999999"), value_b=Decimal("9999999998"))
        assert m.diff_value == Decimal("1")
        assert m.diff_pct == Decimal("0.00")  # 거의 0%

    def test_diff_metric_decimal_precision(self):
        """소수점 정밀도"""
        m = DiffMetric(metric_name="비율", value_a=Decimal("100.50"), value_b=Decimal("100.33"))
        assert m.diff_value == Decimal("0.17")
        assert float(m.diff_pct) == pytest.approx(0.17, abs=0.01)

    def test_diff_metric_b_larger_than_a(self):
        """B가 A보다 큰 경우 음수 차이"""
        m = DiffMetric(metric_name="건수", value_a=Decimal("100"), value_b=Decimal("200"))
        assert m.diff_value == Decimal("-100")
        assert m.diff_pct == Decimal("-100.00")

    # --- API 엣지 케이스 ---

    def test_create_with_empty_title(self):
        """빈 제목으로 생성"""
        res = client.post("/api/comparisons?title=")
        assert res.status_code == 200
        assert res.json()["title"] == ""

    def test_create_default_dialects(self):
        """생성 시 기본 dialect: A=oracle, B=hive"""
        res = client.post("/api/comparisons")
        data = res.json()
        assert data["query_a"]["dialect"] == "oracle"
        assert data["query_b"]["dialect"] == "hive"

    def test_update_empty_sql_clears_validation(self):
        """빈 SQL로 업데이트하면 이전 검증 결과 초기화"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        # SQL 입력 후 검증
        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "SELECT 1 FROM dual", "dialect": "oracle",
        })
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "sql_raw": "SELECT 1 FROM t", "dialect": "hive",
        })
        client.post(f"/api/comparisons/{req_id}/validate")

        # 빈 SQL로 덮어쓰기
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "",
        })
        assert res.json()["query_a"]["is_valid"] is None
        assert res.json()["status"] == "DRAFT"

    def test_summary_empty_metrics(self):
        """빈 지표 배열로 요약 업데이트"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        res = client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": []
        })
        assert res.status_code == 200
        assert len(res.json()["summary"]["metrics"]) == 0

    def test_validate_one_valid_one_empty(self):
        """A만 입력, B는 빈 상태로 검증"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "SELECT 1 FROM dual", "dialect": "oracle",
        })
        # B는 기본값(빈 SQL) 그대로

        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is True
        assert data["query_b"]["is_valid"] is False

    def test_execute_from_error_status_blocked(self):
        """ERROR 상태에서 실행 시도 → 400"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "sql_raw": "INVALID @@@",
        })
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "sql_raw": "SELECT 1 FROM t", "dialect": "hive",
        })
        client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "건수", "value_a": 100, "value_b": 99}]
        })
        client.post(f"/api/comparisons/{req_id}/validate")

        res = client.get(f"/api/comparisons/{req_id}")
        assert res.json()["status"] == "ERROR"

        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.status_code == 400

    # --- Wiki 추출 엣지 케이스 ---

    def test_wiki_extract_non_sql_code_block(self):
        """비-SQL 코드 블록은 필터링"""
        html = """
        <pre><code class="language-python">print("hello")</code></pre>
        <pre><code class="language-sql">SELECT 1 FROM dual</code></pre>
        """
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 1
        assert "SELECT" in blocks[0].preview

    def test_wiki_extract_empty_code_block(self):
        """빈 코드 블록 무시"""
        html = '<pre><code class="language-sql"></code></pre>'
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 0

    def test_wiki_extract_mixed_languages(self):
        """SQL + Java + SQL 혼합 시 SQL만 추출"""
        html = """
        <pre><code class="language-sql">SELECT id FROM users</code></pre>
        <pre><code class="language-java">System.out.println("test");</code></pre>
        <pre><code class="language-plsql">BEGIN UPDATE t SET x=1; END;</code></pre>
        """
        blocks = extract_sql_blocks_from_html(html)
        # sql과 plsql만 추출
        assert len(blocks) == 2
        languages = {b.language for b in blocks}
        assert "sql" in languages
        assert "plsql" in languages

    def test_wiki_extract_long_preview_truncated(self):
        """미리보기가 80자 초과 시 잘림"""
        long_sql = "SELECT " + ", ".join([f"col_{i}" for i in range(50)]) + " FROM very_long_table"
        html = f'<pre><code>{long_sql}</code></pre>'
        blocks = extract_sql_blocks_from_html(html)
        assert len(blocks) == 1
        assert len(blocks[0].preview) <= 84  # 80 + "..."

    # --- Dialect-specific 엣지 케이스 ---

    def test_hive_lateral_view(self):
        """HiveQL LATERAL VIEW 구문"""
        sql = """
        SELECT id, tag
        FROM events
        LATERAL VIEW explode(tags) t AS tag
        """
        result = validate_sql(sql, Dialect.HIVE)
        assert result.is_valid is True

    def test_oracle_dual(self):
        """Oracle DUAL 테이블 기본 쿼리"""
        result = validate_sql("SELECT SYSDATE FROM dual", Dialect.ORACLE)
        assert result.is_valid is True

    def test_dialect_switch_same_sql(self):
        """같은 SQL을 다른 dialect로 파싱"""
        sql = "SELECT id, COUNT(*) FROM orders GROUP BY id"
        for dialect in [Dialect.ORACLE, Dialect.HIVE, Dialect.MYSQL, Dialect.POSTGRES]:
            result = validate_sql(sql, dialect)
            assert result.is_valid is True, f"{dialect.value}에서 파싱 실패"


# --- Wiki 외부 호출 Mock 테스트 ---

class TestWikiExternalCall:
    """fetch_confluence_page / extract_sql_from_url 네트워크 호출 mock 테스트"""

    _FAKE_HTML = """
    <ac:structured-macro ac:name="code">
        <ac:parameter ac:name="language">sql</ac:parameter>
        <ac:plain-text-body>SELECT id, SUM(amt) FROM sales GROUP BY id</ac:plain-text-body>
    </ac:structured-macro>
    """

    @patch("query_diff.wiki_service.requests.get")
    def test_fetch_confluence_page_success(self, mock_get):
        """Confluence REST API 호출 성공"""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "body": {"storage": {"value": self._FAKE_HTML}}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        html = fetch_confluence_page("https://wiki.example.com/wiki/spaces/DEV/pages/12345")
        assert "SELECT" in html
        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert "/rest/api/content/12345" in call_url

    @patch("query_diff.wiki_service.requests.get")
    def test_fetch_confluence_page_no_page_id(self, mock_get):
        """URL에 page ID가 없으면 ValueError"""
        with pytest.raises(ValueError, match="page ID"):
            fetch_confluence_page("https://wiki.example.com/wiki/spaces/DEV/overview")

    @patch("query_diff.wiki_service.requests.get")
    def test_extract_sql_from_url_full_flow(self, mock_get):
        """URL → HTML fetch → SQL 추출 전체 흐름 (mock)"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "body": {"storage": {"value": self._FAKE_HTML}}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        blocks, sqls = extract_sql_from_url("https://wiki.example.com/wiki/spaces/DEV/pages/99999")
        assert len(blocks) == 1
        assert "SELECT" in blocks[0].preview
        assert len(sqls) == 1
        assert "SUM(amt)" in sqls[0]

    @patch("query_diff.wiki_service.requests.get")
    def test_fetch_confluence_with_bearer_token(self, mock_get):
        """Bearer 토큰이 Authorization 헤더에 포함되는지 확인"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "body": {"storage": {"value": "<p>empty</p>"}}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        fetch_confluence_page("https://wiki.example.com/wiki/spaces/DEV/pages/555", token="my-token")
        call_headers = mock_get.call_args[1]["headers"]
        assert call_headers["Authorization"] == "Bearer my-token"

    @patch("query_diff.wiki_service.requests.get")
    def test_extract_wiki_api_endpoint(self, mock_get):
        """API extract-wiki 엔드포인트 + mock 통합"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "body": {"storage": {"value": self._FAKE_HTML}}
        }
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        res = client.post(f"/api/comparisons/{req_id}/extract-wiki", json={
            "url": "https://wiki.example.com/wiki/spaces/DEV/pages/11111"
        })
        assert res.status_code == 200
        data = res.json()
        assert len(data["blocks"]) == 1
        assert data["blocks"][0]["language"] == "sql"


# --- 파일 업로드 시나리오 테스트 ---

class TestFileUploadScenario:
    """source_type=FILE 경로의 API 통합 테스트"""

    def test_file_source_type_workflow(self):
        """파일 업로드 시나리오: source_type=FILE, file_name 설정, SQL 텍스트는 클라이언트에서 읽어 전달"""
        res = client.post("/api/comparisons?title=파일업로드테스트")
        req_id = res.json()["id"]

        file_sql = "SELECT order_id, customer_name, total_amount FROM orders WHERE status = 'PAID'"

        # A: 파일 업로드 시뮬레이션 (프론트에서 FileReader로 읽은 내용을 sql_raw로 전달)
        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "FILE",
            "sql_raw": file_sql,
            "dialect": "oracle",
            "file_name": "매출조회_운영.sql",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["query_a"]["source_type"] == "FILE"
        assert data["query_a"]["file_name"] == "매출조회_운영.sql"
        assert data["query_a"]["sql_raw"] == file_sql

        # B: 텍스트 입력
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "source_type": "TEXT",
            "sql_raw": "SELECT order_id, customer_name, total_amount FROM dim_orders WHERE status = 'PAID'",
            "dialect": "hive",
        })

        # 요약
        client.put(f"/api/comparisons/{req_id}/summary", json={
            "metrics": [{"metric_name": "매출건수", "value_a": 3200, "value_b": 3180}]
        })

        # 검증
        res = client.post(f"/api/comparisons/{req_id}/validate")
        data = res.json()
        assert data["query_a"]["is_valid"] is True
        assert data["query_b"]["is_valid"] is True

        # 실행
        res = client.post(f"/api/comparisons/{req_id}/execute")
        assert res.json()["status"] == "DONE"

    def test_file_source_preserves_after_validation(self):
        """파일 소스 정보가 검증 후에도 유지됨"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "FILE",
            "sql_raw": "SELECT 1 FROM dual",
            "dialect": "oracle",
            "file_name": "test.sql",
        })
        client.put(f"/api/comparisons/{req_id}/query-b", json={
            "sql_raw": "SELECT 1 FROM t", "dialect": "hive",
        })
        client.post(f"/api/comparisons/{req_id}/validate")

        res = client.get(f"/api/comparisons/{req_id}")
        data = res.json()
        assert data["query_a"]["source_type"] == "FILE"
        assert data["query_a"]["file_name"] == "test.sql"
        assert data["query_a"]["is_valid"] is True

    def test_wiki_source_type(self):
        """source_type=WIKI 경로 설정"""
        res = client.post("/api/comparisons")
        req_id = res.json()["id"]

        res = client.put(f"/api/comparisons/{req_id}/query-a", json={
            "source_type": "WIKI",
            "sql_raw": "SELECT dept_cd, SUM(amt) FROM sales GROUP BY dept_cd",
            "dialect": "oracle",
            "wiki_url": "https://wiki.example.com/pages/12345",
        })
        data = res.json()
        assert data["query_a"]["source_type"] == "WIKI"
        assert data["query_a"]["wiki_url"] == "https://wiki.example.com/pages/12345"
