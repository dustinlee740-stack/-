# Query Diff Module — 기본 기능 테스트 시나리오

- **대상 서비스**: `http://127.0.0.1:8000/`
- **기준 모듈**: `D:\da\query_diff` (api.py, models.py, validation_service.py, wiki_service.py, store.py)
- **테스트 위치**: `D:\da\tests`
- **실행 전제**: `uvicorn query_diff.api:app --host 127.0.0.1 --port 8000 --workers 1`
- **작성일**: 2026-04-21

---

## 0. 사전 준비

| 항목 | 내용 |
| --- | --- |
| 환경변수 (dev) | `QUERY_DIFF_ENV=dev` (미설정 시 기본값). `ALLOWED_ORIGINS` 미설정 → `*` 허용 |
| 환경변수 (prod) | `QUERY_DIFF_ENV=prod`, `ALLOWED_ORIGINS=https://internal.example.com` 필수 |
| 워커 | `--workers 1` (인메모리 store는 단일 워커 전제) |
| 초기 상태 | 서버 기동 직후 `store`는 비어 있음 |

---

## 1. 서비스 기동 및 정적 페이지

### TC-01-01 루트 페이지 응답
- **전제**: 서버가 기동되어 있고 `query_diff/static/index.html`이 존재
- **요청**: `GET /`
- **기대**: `200 OK`, `Content-Type: text/html`, `index.html` 본문 반환
- **근거**: `api.py:54-59`

### TC-01-02 정적 리소스 서빙
- **요청**: `GET /static/index.html`
- **기대**: `200 OK`
- **근거**: `api.py:49-51`

### TC-01-03 prod 환경 CORS 필수값 누락 시 기동 실패
- **전제**: `QUERY_DIFF_ENV=prod`, `ALLOWED_ORIGINS` 미설정
- **기대**: 서버 기동 시 `RuntimeError` 발생
- **근거**: `api.py:30-34`

---

## 2. 비교 요청(ComparisonRequest) CRUD

### TC-02-01 비교 요청 생성 (title 없음)
- **요청**: `POST /api/comparisons`
- **기대**:
  - `200 OK`
  - `id` (UUID), `title=""`, `status="DRAFT"`
  - `query_a.dialect="oracle"`, `query_b.dialect="hive"` (기본값)
  - `summary.metrics=[]`, `matching_keys=[]`
- **근거**: `api.py:64-67`, `models.py:87-95`

### TC-02-02 비교 요청 생성 (title 지정)
- **요청**: `POST /api/comparisons?title=2026Q1_매출비교`
- **기대**: `title="2026Q1_매출비교"`, 이외 기본값

### TC-02-03 비교 요청 단건 조회
- **전제**: TC-02-01로 `{req_id}` 확보
- **요청**: `GET /api/comparisons/{req_id}`
- **기대**: `200 OK`, 생성 시와 동일 객체

### TC-02-04 존재하지 않는 ID 조회
- **요청**: `GET /api/comparisons/not-exist-id`
- **기대**: `404`, `detail="비교 요청을 찾을 수 없습니다."`
- **근거**: `api.py:73-74`

### TC-02-05 전체 목록 조회
- **전제**: 2개 비교 요청 생성
- **요청**: `GET /api/comparisons`
- **기대**: `200 OK`, 길이 2 배열

---

## 3. 쿼리 입력 업데이트 (Query A / Query B)

### TC-03-01 Query A TEXT 입력 업데이트
- **요청**: `PUT /api/comparisons/{req_id}/query-a`
  ```json
  {
    "source_type": "TEXT",
    "sql_raw": "SELECT id, name FROM users WHERE id = 1",
    "dialect": "oracle"
  }
  ```
- **기대**:
  - `200 OK`
  - `query_a.source_type="TEXT"`, `query_a.sql_raw` 반영
  - `query_a.is_valid=null`, `validation_error=null`, `structure=null`, `sql_normalized=null` (재검증 대기)
  - `status="DRAFT"`로 롤백
- **근거**: `api.py:85-112`

### TC-03-02 Query B FILE 입력 업데이트
- **요청 body**: `{"source_type":"FILE","sql_raw":"SELECT 1 FROM dual","dialect":"hive","file_name":"q1.sql"}`
- **기대**: `query_b.file_name="q1.sql"` 포함 반영

### TC-03-03 Query B WIKI 입력 업데이트
- **요청 body**: `{"source_type":"WIKI","wiki_url":"https://confluence.example.com/wiki/spaces/X/pages/123"}`
- **기대**: `query_b.wiki_url` 반영

### TC-03-04 업데이트 시 검증 결과 리셋
- **전제**: `query_a.is_valid=true`, `sql_normalized="..."`인 상태
- **행위**: `sql_raw`만 변경하는 PUT
- **기대**: `is_valid`, `structure`, `sql_normalized`, `validation_error` 모두 null 리셋
- **근거**: `api.py:98-101` (최근 수정: `d328542 fix: reset sql_normalized on query update`)

### TC-03-05 존재하지 않는 ID로 업데이트
- **요청**: `PUT /api/comparisons/invalid-id/query-a` (정상 body)
- **기대**: `404`

### TC-03-06 Pydantic 타입 오류
- **요청 body**: `{"dialect":"db2"}` (허용 외 값)
- **기대**: `422 Unprocessable Entity`

---

## 4. SQL 검증 (Validate)

### TC-04-01 A/B 모두 유효 → READY
- **전제**:
  - A: `SELECT id FROM users` / dialect=oracle
  - B: `SELECT id FROM users` / dialect=hive
- **요청**: `POST /api/comparisons/{req_id}/validate`
- **기대**:
  - `query_a.is_valid=true`, `dialect_detected="oracle"`, `structure.select_columns=1`, `from_tables=1`
  - `query_b.is_valid=true`, `dialect_detected="hive"`
  - 비교 요청 `status="READY"`
- **근거**: `api.py:140-158`, `validation_service.py:128-149`

### TC-04-02 A 빈 SQL → ERROR
- **전제**: `query_a.sql_raw=""`
- **기대**: `query_a.is_valid=false`, `error_message="SQL이 입력되지 않았습니다."`, 전체 `status="ERROR"`
- **근거**: `validation_service.py:178-182`

### TC-04-03 방언 불일치 시 제안 문구 반환 (같은 계열)
- **전제**: Oracle 전용 문법(예: `SELECT 1 FROM dual`)에 dialect=mysql 지정
- **기대**: `is_valid=false`, `suggestion` 문자열에 `'oracle'` 포함 (MySQL↔Oracle은 같은 family)
- **근거**: `validation_service.py:34-39, 154-166`

### TC-04-04 Hive SQL에는 Oracle 제안 금지
- **전제**: Hive 전용 문법(예: `SELECT * FROM t LATERAL VIEW explode(arr) x AS v`)에 dialect=hive 파싱 실패 케이스
- **기대**: 실패 시 suggestion에 `oracle` 포함되지 않음 (Hive family=∅)
- **근거**: `validation_service.py:36` (`Dialect.HIVE: set()`)

### TC-04-05 템플릿 변수 전처리
- **전제**: `sql_raw="SELECT * FROM t WHERE id=${id=10} AND name='${name=kim}'"`, dialect=oracle
- **기대**:
  - `is_valid=true`
  - `sql_normalized`에 숫자 기본값은 `10`, 문자열 기본값은 `'kim'` 형태로 치환되어 저장
- **근거**: `validation_service.py:44-64`, `191-196`

### TC-04-06 AST 구조 카운트
- **입력**: `SELECT a,b FROM t1 JOIN t2 ON t1.id=t2.id WHERE a>1 AND b<2 GROUP BY a HAVING count(*)>0 ORDER BY a`
- **기대 structure**: `select_columns=2, from_tables=2, joins=1, where_conditions>=2, group_by_columns=1, having_conditions=1, order_by_columns=1`
- **근거**: `validation_service.py:71-125`

### TC-04-07 서브쿼리 카운트
- **입력**: `SELECT a FROM (SELECT a FROM t) sub`
- **기대**: `subqueries=1`

### TC-04-08 존재하지 않는 ID 검증
- **요청**: `POST /api/comparisons/invalid-id/validate`
- **기대**: `404`

---

## 5. 차이 요약 (Summary)

### TC-05-01 단일 지표 등록
- **요청**:
  ```json
  { "metrics": [{"metric_name":"매출합계","value_a":"10000","value_b":"9900"}] }
  ```
- **기대**:
  - `200 OK`
  - 반환 객체 `summary.metrics[0].diff_value="100"`, `diff_pct="1.00"`
- **근거**: `api.py:128-135`, `models.py:60-75`

### TC-05-02 value_a=0 → diff_pct=0
- **요청 metric**: `{"metric_name":"건수","value_a":"0","value_b":"50"}`
- **기대**: `diff_value="-50"`, `diff_pct="0"`
- **근거**: `models.py:72-75`

### TC-05-03 다중 지표 등록
- **요청**: 3개 지표 배열
- **기대**: `summary.metrics` 길이 3, 각 diff 계산 정상

### TC-05-04 Summary 요청 body 누락
- **요청**: `{}`
- **기대**: `422`

---

## 6. 비교 실행 (Execute)

### TC-06-01 READY + metrics 존재 → DONE
- **전제**: TC-04-01 통과 + TC-05-01 등록
- **요청**: `POST /api/comparisons/{req_id}/execute`
- **기대**: `200 OK`, `status="DONE"`
- **근거**: `api.py:181-198`

### TC-06-02 DRAFT 상태에서 실행 차단
- **전제**: validate 전
- **기대**: `400`, `detail="검증 완료 상태에서만 실행할 수 있습니다."`

### TC-06-03 ERROR 상태에서 실행 차단
- **전제**: TC-04-02 상태
- **기대**: `400`

### TC-06-04 metrics 비어 있을 때 실행 차단
- **전제**: READY 상태, summary 미등록
- **기대**: `400`, `detail="차이 요약을 최소 1개 입력해주세요."`

### TC-06-05 DONE 상태에서 재실행 허용
- **전제**: TC-06-01 완료
- **기대**: 재호출 시 `200 OK`, `status="DONE"` 유지
- **근거**: `api.py:187` (`READY, DONE` 모두 허용)

---

## 7. Wiki SQL 추출

### TC-07-01 정상 Confluence URL → SQL 블록 반환
- **전제**: `extract_sql_from_url` mock — 2개 SQL 블록 반환
- **요청**: `POST /api/comparisons/{req_id}/extract-wiki` with `{"url":"https://confluence.example.com/wiki/spaces/X/pages/12345"}`
- **기대**:
  - `200 OK`
  - `blocks[*]`: `index`, `preview` (80자 + `...`), `lines`, `language` 포함
- **근거**: `api.py:163-176`, `wiki_service.py:171-181`

### TC-07-02 Confluence 코드 매크로 파싱
- **입력 HTML**: `<ac:structured-macro ac:name="code">...` 포함
- **기대**: `language` = parameter 값 또는 `"sql"` 기본
- **근거**: `wiki_service.py:68-75`

### TC-07-03 `<pre><code class="language-sql">` 파싱
- **기대**: `language="sql"`
- **근거**: `wiki_service.py:78-89`

### TC-07-04 마크다운 코드 펜스 파싱
- **입력 HTML 본문**: ```` ```sql\nSELECT 1\n``` ```` 포함
- **기대**: 해당 블록 추출
- **근거**: `wiki_service.py:92-98`

### TC-07-05 비-SQL 블록 필터링
- **입력**: language="python" + 본문에 SELECT/INSERT 등 없음
- **기대**: blocks에 포함되지 않음
- **근거**: `wiki_service.py:103-109, 120`

### TC-07-06 page_id 파싱 실패
- **요청 URL**: `https://confluence.example.com/spaces/X/nopages/abc`
- **기대**: `400`, detail에 `"page ID를 추출할 수 없습니다"` 포함
- **근거**: `wiki_service.py:152-154`, `api.py:171-172`

### TC-07-07 Confluence API 네트워크 오류
- **전제**: `requests.get` → `ConnectionError`
- **기대**: `502`, detail에 `"Wiki 페이지 접근 실패"` 포함
- **근거**: `api.py:173-174`

### TC-07-08 SSRF — 127.0.0.1
- **요청 URL**: `http://127.0.0.1/wiki/spaces/X/pages/1`
- **기대**: `400`, detail에 `"내부 네트워크"` 포함
- **근거**: `wiki_service.py:19-53`

### TC-07-09 SSRF — 내부 사설망
- **URL 예시**: `http://10.0.0.1/...`, `http://192.168.1.1/...`, `http://172.16.0.1/...`, `http://169.254.169.254/...` (메타데이터 서비스)
- **기대**: 모두 `400`

### TC-07-10 SSRF — 허용되지 않는 스키마
- **URL**: `file:///etc/passwd`, `gopher://...`
- **기대**: `400`, detail에 `"허용되지 않는 스키마"` 포함
- **근거**: `wiki_service.py:39-40`

### TC-07-11 SSRF — DNS 해석 실패
- **URL 호스트**: 해석 불가 도메인
- **기대**: `400`, detail에 `"호스트를 해석할 수 없습니다"` 포함

### TC-07-12 SSRF — DNS rebinding 호스트 (공인→사설 해석)
- **전제**: `socket.getaddrinfo` mock이 사설 IP 반환
- **기대**: `400`
- **근거**: `wiki_service.py:47-53`

---

## 8. 상태 전이 전체 시나리오 (Happy Path)

순차 실행 시 기대 `status` 흐름:

1. `POST /api/comparisons` → `DRAFT`
2. `PUT /query-a` (유효 SQL) → `DRAFT`
3. `PUT /query-b` (유효 SQL) → `DRAFT`
4. `POST /validate` (A,B 모두 유효) → `READY`
5. `PUT /summary` (metric 1개 이상) → `READY` (summary 수정은 status 미변경)
6. `POST /execute` → `COMPARING` → `DONE`

---

## 9. 회귀/보안 시나리오

### TC-09-01 store 단일 워커 제약
- **전제**: `uvicorn --workers 2`로 기동
- **행위**: 워커 A에서 생성 → 워커 B에서 조회
- **기대**: 일부 요청에서 `404` 발생 (프로세스 간 state 격리)
- **대응**: 운영은 반드시 `--workers 1` 또는 외부 저장소(Redis/PG) 전환
- **근거**: `store.py:3-6`

### TC-09-02 CORS preflight (dev)
- **요청**: `OPTIONS /api/comparisons` + `Origin: http://localhost:3000`
- **기대**: `200`, `Access-Control-Allow-Origin: *`

### TC-09-03 CORS preflight (prod, 허용 origin)
- **환경**: `ALLOWED_ORIGINS=https://internal.example.com`
- **요청 Origin**: `https://internal.example.com`
- **기대**: 해당 origin echo

### TC-09-04 CORS preflight (prod, 비허용 origin)
- **요청 Origin**: `https://evil.example.com`
- **기대**: `Access-Control-Allow-Origin` 헤더 미반환

---

## 10. 실행 방법 메모

```bash
# 1) 서버 기동
cd D:/da
uvicorn query_diff.api:app --host 127.0.0.1 --port 8000 --workers 1

# 2) 기존 자동화 테스트 (pytest)
cd D:/da
pytest tests/test_query_diff.py -v

# 3) 본 시나리오 수동 검증 (브라우저)
#    http://127.0.0.1:8000/          → index.html
#    http://127.0.0.1:8000/docs      → FastAPI Swagger UI
```

## 11. 커버리지 매트릭스

| 영역 | 케이스 수 | 참조 파일 |
| --- | --- | --- |
| 서비스 기동·정적 | 3 | api.py |
| 비교 요청 CRUD | 5 | api.py, models.py, store.py |
| 쿼리 입력 업데이트 | 6 | api.py, models.py |
| SQL 검증 | 8 | validation_service.py |
| 차이 요약 | 4 | models.py |
| 비교 실행 | 5 | api.py |
| Wiki 추출 + SSRF | 12 | wiki_service.py |
| 상태 전이 | 1 | api.py 전반 |
| 회귀/보안 | 4 | store.py, api.py CORS |
| **합계** | **48** | |
