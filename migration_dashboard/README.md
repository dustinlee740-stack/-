# 운영계 → 분석계 이관 현황 대시보드

운영계 DB와 분석계 DB의 스키마(컴포넌트·테이블·컬럼)를 비교해 **이관 현황**을 단독 실행 HTML 하나로 보여준다.
무엇이 이관됐고, 안 됐다면 사유(이관 요청 없음 / 개인정보 제외 / 요청 부적합 등)가 무엇인지를 컴포넌트 → 테이블 → 컬럼 3단계로 드릴다운한다.

> 현재는 **설계 단계**다. 실제 운영계/분석계 CSV는 향후 일자별로 제공되며, 대시보드는 **항상 최신 데이터만** 반영한다. 지금은 레포의 `ttp_workflow`(분석계 이관 정답지) + `pilot/components.xlsx`(컴포넌트 역할)로 **실제와 동형인 샘플 데이터**를 만들어 동작을 보여준다.

## 빠른 시작

```bash
python parse_ttp_sql.py --ttp-root ../ttp_workflow   # 분석계 샘플
python gen_sample_op_schema.py                        # 운영계 샘플
python gen_sample_reasons.py                          # 사유 샘플
python sync_hue_comments.py --full                    # (선택) Hue → 컬럼 설명+순서 캐시 (hue_config.md 필요)
python build_dashboard.py                             # → dashboard.html
```

생성된 `dashboard.html`을 브라우저로 **더블클릭**하면 끝(서버 불필요). 다른 날짜의 CSV를 즉석에서 보려면 같은 페이지에 CSV 파일들을 **드래그&드롭**한다.

## 입력 CSV 포맷 (합의안)

모든 파일 UTF-8(BOM 허용). 조인 키(`component`/`table`/`column`)는 비교 전에 **trim + 대문자** 정규화된다.

### 1) `data/op_schema.csv` — 운영계 스키마 (이관 모집단 = 분모의 원천)

| 컬럼 | 필수 | 설명 |
|---|:--:|---|
| `component` | ● | 운영계 컴포넌트 코드 (예: CS, IAS) |
| `table` | ● | 운영계 테이블명 |
| `column` | ● | 운영계 컬럼명 |
| `data_type` | | 원천 데이터 타입 |
| `column_desc` | | 컬럼 역할 설명 (테이블/컬럼 역할의 유일한 공급원) |
| `table_desc` | | 테이블 역할 설명 (테이블 단위로 값 중복 허용) |
| `is_pii` | | 개인정보 여부 `Y`/`N` |

### 2) `data/an_schema.csv` — 분석계 스키마 (실제 이관된 것)

| 컬럼 | 필수 | 설명 |
|---|:--:|---|
| `an_component` | ● | 분석계 컴포넌트 (적재문 `... into table X.Y`의 X) |
| `an_table` | ● | 분석계 테이블 (Y) |
| `an_column` | ● | 분석계 컬럼 (`... as <컬럼>`의 타깃) |
| `op_component` | ● | 매핑되는 운영계 컴포넌트 |
| `op_table` | ● | 매핑되는 운영계 테이블 — **컬럼 단위 1:1 조인에 필수** |
| `op_column` | ● | 매핑되는 운영계 컬럼 (단일 식별자일 때) |
| `source_expr` | | 원본 매핑식 (CASE/cast 등으로 1:1이 아닐 때 보존) |

> 분석계 적재 SQL은 운영계 *테이블명*을 담지 않는다(`from temp.tmp_*`만). 따라서 실데이터에서는 `op_table`을 **반드시** 채워야 컬럼 단위 매칭이 된다. 샘플 파서는 `tmp_<X>_<Y>` 관례로 추정해 채운다.

### 3) `data/reasons.csv` — 미이관 사유 매핑 (사용자 제공)

| 컬럼 | 필수 | 설명 |
|---|:--:|---|
| `component` | ● | |
| `table` | ● | |
| `column` | | **빈칸이면 해당 테이블 전체에 적용**(와일드카드). 특정 컬럼 행이 테이블 행을 override |
| `reason_code` | ● | 아래 5종 enum |
| `reason_note` | | 자유 설명. `ETC`는 필수 |

**reason_code enum (확정)**

| 코드 | 한글 라벨 | 이관율 분모 |
|---|---|:--:|
| `NO_REQUEST` | 이관 요청 없음 | 제외 |
| `PII_EXCLUDED` | 개인정보로 이관 제외 | 제외 |
| `UNFIT` | 요청 부적합 | 제외 |
| `PENDING` | 이관 예정 | 포함(미이관) |
| `ETC` | 기타 | 포함(미이관) |

### 4) `data/components.csv` — 컴포넌트 역할 설명

`pilot/components.xlsx`의 사본. 컬럼: `Name`(키), `Full Name`, `Korean Description`, `English Description`, `대분류`/`중분류`/`소분류`(또는 영문 헤더 `Major Categories`/`Medium Category`/`Subcategories`).

### 5) `data/column_comments.csv` — 컬럼 한글 설명 + 순서 캐시 (Hue에서 동기화)

`sync_hue_comments.py`가 생성·갱신. 컬럼: `schema, table, column, comment, col_seq, table_comment` (분석계 식별자 기준, `col_seq`=Hue 노출 순서).
빌드 시 **이관된 컬럼**의 설명을 이 캐시로 채운다 — 운영계 컬럼을 분석계 매핑 `(an_table, an_column)`으로 찾아 Hue Comment를 붙이고(●), **3-depth 컬럼을 `col_seq`(Hue 순서)대로 정렬**한다. 분석계전용(파생) 컬럼도 직접 매칭. 미이관 컬럼은 Hue에 매칭이 없으면 `op_schema.column_desc`(샘플) 유지.

## 컬럼 설명 동기화 (Hue / Hive Metastore)

설명 원천은 **Hue 테이블 브라우저(Hive Metastore)**의 테이블 상세 **컬럼 Comment**. Hive Metastore는 **Kudu 관리 테이블과 LOCATION/외부 테이블의 컬럼 설명을 모두** 보유하므로(Kudu UI는 LOCATION 테이블이 누락됨) 커버리지가 완전하고, 컬럼 **순서(ordinal)**도 제공한다.

### 🔒 안전 (반드시 준수)
- 테이블 상세 페이지로 **goto(GET) + 컬럼 DOM 읽기만**. 쿼리/Sample/가져오기/삭제/새로고침/Invalidate/상태변경 등 **어떤 액션도 하지 않음**.
- 스크립트가 모든 네트워크 요청을 가로채 **GET/HEAD가 아니거나 액션 URL**(execute/sample/invalidate/refresh/autocomplete/import/delete…)이면 즉시 차단한다. 이동 URL은 메타스토어 테이블 상세 **화이트리스트**로만 제한.

### 실행
```bash
# 1) hue_config.md 채우기: HUE_URL + (권장)HUE_SESSIONID/HUE_CSRFTOKEN 또는 HUE_USERNAME/HUE_PASSWORD
pip install playwright && playwright install chromium      # 최초 1회
python hue_login.py                  # (id/pw 방식일 때만) 로그인 페이지에서만 인증 → hue_auth.json
python sync_hue_comments.py          # 증분: 변경/추가 컬럼만 upsert
python sync_hue_comments.py --full   # 전체 재작성
python sync_hue_comments.py --table CS_MCPM_CHRG   # 특정 테이블만
```
- 대상 테이블은 기본 `an_schema.csv`의 분석계 테이블(대시보드 표시 대상). `hue_config.md`의 `HUE_DBS`로 한정 가능.
- 캐시가 상태 — `added/updated/unchanged/removed` 리포트. **매일 불필요** — 최초 1회 + 컬럼 추가/수정 시 (필요하면 `--table`) 재실행.
- Hue 버전마다 DOM/경로가 달라 컬럼 추출 셀렉터·경로는 첫 실행 후 1회 보정이 필요할 수 있음(`hue_config.md`의 `HUE_TABLE_PATH` 등으로 오버라이드).

> `sync_column_comments.py`(Kudu)는 **deprecated** — Hue 접속 전 오프라인 시드/정렬 검증용으로만 동일 스키마(`col_seq` 포함) 캐시를 생성한다.

## 집계 규칙

운영계를 기준(LEFT)으로 분석계와 컬럼 키 `(component, table, column) ↔ (op_component, op_table, op_column)`로 조인한다.

- **이관**: 운영계 ∩ 분석계
- **미이관**: 운영계에만 존재. 사유 매핑을 부착한다.
  - `is_pii=Y`인데 사유 없음 → `PII_EXCLUDED` **자동 추정**("(자동)" 표기)
  - 그래도 사유 없음 → **사유미지정**(누락 가시화)
- **제외(대상 아님)**: 미이관 ∧ `reason_code ∈ {NO_REQUEST, PII_EXCLUDED, UNFIT}`
- **분석계전용**: 분석계에만 존재. `source_expr`이 함수/CASE/상수면 **파생컬럼**, 아니면 **운영계미등재**(데이터 품질 경고)

**이관율 = 이관 ÷ (운영계 전체 − 제외)**. 분모가 0이면 `대상아님`.

상태 배지: `완료`(100%) / `부분`(0<율<100) / `미이관`(0%, 분모>0) / `대상아님`(분모=0).
컴플라이언스: `is_pii=Y` 컬럼이 분석계에 실제 존재하면 **"PII 이관됨" 경고**.

## 파일 구성

| 파일 | 역할 |
|---|---|
| `parse_ttp_sql.py` | `ttp_workflow/*.sql` → `data/an_schema.csv` (샘플 분석계) |
| `gen_sample_op_schema.py` | 샘플 운영계 CSV (미이관·PII 인위 주입, 고정 seed) |
| `gen_sample_reasons.py` | 샘플 사유 CSV |
| `common.py` | 정규화·상태판정·CSV/xlsx 읽기 헬퍼 (외부 import 없음) |
| `build_dashboard.py` | CSV 4종 → 조인·집계 → `dashboard.html` |
| `template/dashboard.html.tmpl` | 단독 HTML 템플릿(JS 집계 fallback + 드래그앤드롭) |
