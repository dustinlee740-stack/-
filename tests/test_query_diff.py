"""쿼리 비교 모듈 테스트"""

import pytest
from decimal import Decimal
from fastapi.testclient import TestClient

from query_diff.api import app
from query_diff.models import Dialect, DiffMetric, QueryInput
from query_diff.validation_service import validate_sql, validate_query_input, _preprocess_sql
from query_diff.wiki_service import extract_sql_blocks_from_html


client = TestClient(app)


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
