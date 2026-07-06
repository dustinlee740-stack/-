# meta3 스키마매핑 데이터 검증 보고서

> 대상: `meta3.table_col_mapping`(+`v_oltp_tbl_col_info`) 을 query_diff **No.3 스키마 매핑 딕셔너리**(운영계 Oracle ↔ 분석계 Hive)의 소스로 쓸 수 있는가
> 검증일: 2026-06-25 (v2: 2026-06-26 v_oltp identity 규칙 반영) · 조회: MCP `meta3-db`(PostgreSQL), 모든 식별자 **대문자** 조회
> 관련 문서: `AGENTS.md`(규칙①·②), `query_diff/flow.md`(No.3/No.5/No.6), `query_diff/structure_diff/schema_mapping.py`

## 0. 결론 (요약)

**판정: 적합 (USABLE) — 단, 두 객체를 결합하고 값 변환은 보완.**

운영↔분석 매핑은 **단일 테이블이 아니라 두 meta3 객체의 결합**으로 해석한다(§B-2, §G):

1. `table_col_mapping` 에 있으면 → **리네임 매핑**(asis 운영 → tobe 분석). 운영≠분석.
2. 없고 `v_oltp_tbl_col_info` 에 있으면(주로 std_yn='Y') → **운영=분석 identity**(표준화 완료, 이름 그대로).
3. 둘 다 없으면 → meta3 미커버.

- ✅ `table_col_mapping`(27,543행) 은 운영(asis)↔분석(tobe) **컬럼 단위 리네임 매핑**으로 No.3 축과 일치. (asis=운영, tobe=분석 — 사용자 확인)
- ✅ 리네임 집합에서는 `IdentitySchemaMapping`(이름 동일=동일)이 **실패**함이 증명됨: col_id **88.9%**, 논리명 **75.9%**, 테이블 ID **42.6%** 상이.
- ✅ 반면 v_oltp에만 있는 **identity 집합(14,489컬럼, std_yn=Y)** 에서는 `IdentitySchemaMapping` 이 **정답** — 폐기가 아니라 **2단계 fallback**으로 재배치한다(§E).
- ✅ meta3 tobe가 실제 분석계(Hive) 물리명임을 ODS 쿼리로 실증(§B-3).
- ⚠️ **값 변환 규칙 부재.** `col_mapping_type`·`mapping_biz_condition` **전수 NULL** → No.5 Row diff 값 비교는 `migration_dashboard/data/an_schema.csv` 의 `source_expr`(변환식 1,192건)로 보완(§D, §F).
- ⚠️ **잔여 미커버.** std_yn='N' 2,793컬럼(v_oltp 존재·비표준·미매핑)은 identity 단정 보류(§G). AML(A-Safe) 등은 meta3에 없고 an_schema.csv에만 있다(§F).

---

## A. 축·구조 확정

| 항목 | 값 |
|---|---|
| 총 매핑 행 | **27,543** |
| 축 | `asis_*` = 운영계(Oracle) / `tobe_*` = 분석계(Hive) |
| 단위 | 컬럼(column) |
| 보유 필드 | db_id, table_id, col_id, 논리명, `tobe_pk`, `tobe_data_type`, `asis_data_type` 등 |
| **값 변환 규칙** | `col_mapping_type` **전수 NULL**, `mapping_biz_condition` **전수 빈값** → 미제공 |

표본 — `KODASP.DCNT_GROUP_MAPPING`(운영) → `KOD.DCNT_GROUP_MAPPING`(분석), 8컬럼:

| 운영 col_id (asis) | 운영 논리명 | 분석 col_id (tobe) | 분석 논리명 | PK |
|---|---|---|---|---|
| DCNT_TYPE | 할인타입 | DC_BNF_CD | 할인혜택코드 | Y |
| SVC_ID | 상품ID | SVC_ID | 서비스ID | Y |
| CHANNEL | 매입채널 | ACQR_DV_CD | 매입사구분코드 | Y |
| GROUP_ID | 그룹ID | BZTP_GRP_ID | 업종그룹ID | – |
| REG_DATE | 등록일 | SYS_CRE_DTTM | 시스템생성일시 | – |

→ db_id·col_id·논리명이 모두 변하며, 동일 col_id(`SVC_ID`)라도 의미(상품ID→서비스ID)가 달라질 수 있다.

---

## B. 커버리지

### B-1. 운영계 컴포넌트 커버리지 — ✅ 양호

운영(asis) **53개 DB**, 운영 테이블 **1,703개**가 분석(tobe)으로 매핑됨. pilot 도메인 원장 핵심 컴포넌트 전부 존재:

| 운영(asis_db) | 분석(tobe_db) | 행수 |
|---|---|---|
| IAS(승인거래) | IAS | 499 |
| RS(환불) | RS | 76 |
| CS(충전) | CS | 821 |
| CMS(카드원장) | CMS | 187 |
| KODASP(기준정보) | **KOD** | 1,640 |
| KCPS(쿠폰) | **KCP** | 238 |

- by-pass 컴포넌트(PP, BGS)도 매핑에 존재(PP→PP 10, BGS→BGS 135).
- **db_id 리네이밍 다수**: KODASP→KOD, PORTAL→POR, KCPS→KCP, ESIGN→ESI, BIZD→BID, CRMS→RMS, KSTS→KST, CAMS→CAM 등(7,282행, 26.4%가 db_id 변경). 매퍼는 컴포넌트 코드 변환표를 가져야 함.
- 주의: `CAMS` 는 `CAM`(538) + `CAMS`(16) 두 분석 DB로 분기 → 1개 운영 DB가 복수 분석 DB로 갈 수 있음.

### B-2. v_oltp 의 역할 = identity(운영=분석) 집합 — ✅ 재해석

`v_oltp_tbl_col_info`(운영 물리 카탈로그, 22,953컬럼)는 `table_col_mapping` 의 **결손이 아니라 보완 객체**다. 두 객체는 **거의 분리된 테이블 모집단**을 가진다(매핑 테이블 1,703개 중 v_oltp에 존재하는 건 205개뿐). 이는 누락이 아니라 **역할 분담**이다:

- `table_col_mapping` = 표준화 과정에서 **이름이 바뀐(리네임)** 컬럼.
- `v_oltp_tbl_col_info` = **이미 표준화돼 운영=분석이 동일한** 컬럼(+ 일부 비표준).

v_oltp 22,953컬럼을 매핑 기준으로 분류:

| 분류 | 건수 | 의미 |
|---|---|---|
| mapping **asis** 매칭 | 5,646 | 리네임 대상(운영≠분석) → 매핑 사용 |
| mapping **tobe** 매칭 | 267 | (표준명이 이미 운영 카탈로그에 등장) |
| **둘 다 미매칭** | **17,282** | 매핑 불요 → v_oltp 단독 판정 |
| └ 그중 std_yn='Y' | **14,489 (83.8%)** | **표준화 완료 = 운영=분석 identity** |
| └ 그중 std_yn='N' | 2,793 (16.2%) | 비표준·미매핑 → identity 단정 보류(§G) |

- v_oltp는 **운영(asis) 명명과 정렬**됨(asis 매칭 5,646 ≫ tobe 267).
- 70개 운영 DB **전부** identity 컬럼을 보유.
- 표본(identity) — `IAS.IAS_BENEFIT_TRAN.CRD_SPPS_DV_CD`(카드부가서비스구분코드),
  `IAS.IAS_CARD_LASTTX.LAST_APV_DTL_DTTM`(최종승인상세일시) 등: 매핑에 없고 v_oltp에
  존재하는 이미 표준화된 컬럼 → 운영=분석.

→ **1차 보고서의 "측정 불가/허위 17,307" 결론은 정정한다.** 그 미매칭분은 gap이 아니라
**identity 집합**이다. No.3 매핑 해석은 §G 알고리즘으로 통합한다.

### B-3. 분석계 실재 ↔ tobe 일치 — ✅ 실증됨

`ttp_workflow/ODS/ODS_ACUM_MBR_BYDT_AGG.sql` 이 `INNER JOIN kod.contract kc` 로 `kc.ptn_id`, `kc.ptn_nm` 를 사용한다. meta3 tobe에 동일 객체가 존재:

| 분석 tobe | 값 | 운영 asis | PK |
|---|---|---|---|
| KOD.CONTRACT.PTN_ID | 파트너ID | PLAYER_ID(PlayerId) | Y |
| KOD.CONTRACT.PTN_NM | 파트너명 | NAME(사업자명) | – |

→ ODS 쿼리의 물리 컬럼명(`ptn_id`,`ptn_nm`)이 meta3 **tobe col_id와 정확히 일치** → **meta3 tobe = 분석계(Hive) 물리 카탈로그**임이 확인됨. AGENTS.md 규칙①("분석계=meta3 참조")은 정확하다.

---

## C. 카디널리티 / 무결성

| 지표 | 값 | 해석 |
|---|---|---|
| 완전 중복 행 | **0** | 무결성 양호 |
| 1:N (운영1→분석N) | **1건** | 분할 거의 없음 |
| N:1 (운영N→분석1) | **19건** | 소수 병합 존재(아래) |
| 테이블 ID 변경 | 11,744 (42.6%) | — |
| DB ID 변경 | 7,282 (26.4%) | 컴포넌트 코드 변환 필요 |
| **컬럼 ID 변경** | **24,488 (88.9%)** | IdentityMapping 실패율의 정량 근거 |
| 논리명 변경 | 20,901 (75.9%) | — |

N:1 병합 표본:
- `KOD.*_MERCHANT.MC_REG_DT`(가맹점등록일자) ← {`MCT_REG_DATE`, `REG_DATE`} (BC/HANA/PAYCO/SHINHAN/SSUMPASS 등 다수 가맹점 테이블)
- `KPS.KPS_PRVC_TNSF.PRVC_MGBR_ID` ← {`RES_BRANCH_ID`, `REQ_BRANCH_ID`}

### PK 매핑 일관성 — ⚠️ 주의

| | 건수 |
|---|---|
| 운영 PK(asis_pk=Y) | 4,479 |
| 분석 PK(tobe_pk=Y) | 4,456 |
| 양쪽 PK 유지 | 2,417 (운영 PK의 **54%**) |
| 운영만 PK(분석서 해제) | 2,062 |
| 분석만 PK(신규 부여) | 2,039 |

→ PK 정의가 운영↔분석에서 **절반만 보존**됨. No.5 Row diff의 매칭 키는 어느 한쪽 PK를 맹신하지 말고 매핑 단위로 양쪽 PK를 교차 확인해야 한다.

---

## D. 데이터 품질

- `asis_col_id` / `tobe_col_id` 빈값 **0** (모든 행이 양쪽 ID 보유) — 클린.
- **타입 변경 18,801건(68.3%)**. 운영 45개 타입 → 분석 **9개 타입으로 축소**(Hive 표준화).

| 운영(asis) | 분석(tobe) | 건수 | 비고 |
|---|---|---|---|
| VARCHAR2 | VARCHAR | 8,693 | 단순 표준화 |
| NVARCHAR2 | VARCHAR | 6,790 | 단순 표준화 |
| TIMESTAMP(6) | DATE | 911 | **정밀도 손실** |
| CHAR | VARCHAR | 596 | 트림 주의 |
| NUMBER | VARCHAR | 551 | **수치→문자** |
| VARCHAR2 | NUMBER | 320 | **문자→수치** |
| TIMESTAMP(6) | TIMESTAMP | 308 | — |
| NVARCHAR2 | NUMBER | 203 | **문자→수치** |

→ NUMBER↔VARCHAR, TIMESTAMP→DATE 등 **의미 있는 타입 변환**이 존재. No.5 값 비교 시 정규화(트림/타입 캐스팅/날짜 포맷) 필요.

---

## E. schema_mapping.py 적용 메모 (후속 구현 참고, 본 검증 범위 밖)

`SchemaMapping` Protocol을 구현하는 `Meta3SchemaMapping` 는 **§G 알고리즘을 그대로 코드화**한다:

- `same_table(a,b)` / `same_column(a,b)`:
  1. `table_col_mapping` 에서 asis↔tobe 대응을 조회(운영≠분석 리네임). 컴포넌트(db_id) 컨텍스트 필수(KODASP↔KOD 변환표).
  2. 없으면 `v_oltp_tbl_col_info` 존재 여부로 identity 판정 → **이때는 기존 `IdentitySchemaMapping`(이름 동일=동일)이 정답**. 즉 IdentityMapping은 **폐기 대상이 아니라 2단계 fallback 컴포넌트로 재사용**한다.
  3. 둘 다 없으면 미커버(False/예외).
- 캐싱: 27,543 매핑행 + v_oltp 22,953행 모두 소규모 → 메모리 적재 가능. 조회 식별자 **대문자 정규화** 필수.
- 추가 제공: PK(`tobe_pk`)·타입(`tobe_data_type`) → No.5 매칭 키/캐스팅에 활용.
- **한계**: 값 변환식 미제공 → an_schema.csv `source_expr` 결합 필요. std_yn='N' 미매핑분은 미커버로 표시.

---

## F. 두 매핑 소스 비교 (중요)

운영↔분석 매핑 소스가 **둘** 존재한다:

| | `meta3.table_col_mapping` | `migration_dashboard/data/an_schema.csv` |
|---|---|---|
| 행수 | 27,543 | 7,556 |
| 컬럼 ID/논리명 변환 | ✅ | ✅ |
| PK 정보 | ✅(`tobe_pk`) | ❌ |
| 데이터 타입 | ✅(asis/tobe) | ❌ |
| **값 변환식** | ❌ (전수 NULL) | ✅ **`source_expr` 1,192건** |
| 컴포넌트 명명 | 분석=KOD | 분석=KODASP(운영명 유지) |
| AML(A-Safe) | ❌ 없음 | ✅ 있음 |
| 범위 | 53 운영 DB | VCC·DAP·PRS·CTI·ODS 등 추가 포함 |

- an_schema.csv 예: `AMLS.AML_USER_INFO.SYS_CRE_DTTM ← from_unixtime(unix_timestamp(CREATED,'yyyy/MM/dd HH:mm:ss'))` — meta3에 없는 변환 로직 보유.
- **권고**: No.3 컬럼 식별·PK·타입의 권위 소스는 **meta3**, 값 변환(No.5)은 **an_schema.csv `source_expr`** 로 결합. AML 등 meta3 미수록 컴포넌트는 an_schema로 보완.

---

## G. No.3 매핑 해석 알고리즘 (확정)

운영 객체(컴포넌트/테이블/컬럼) 하나가 주어졌을 때 분석계 대응을 다음 순서로 판정한다:

```
1) table_col_mapping(asis) 에 있나?
     ├─ 예 → 분석 = 대응 tobe (운영≠분석, 리네임).  [27,543 매핑]
     └─ 아니오 ↓
2) v_oltp_tbl_col_info 에 있나?
     ├─ 예(std_yn='Y') → 운영=분석 identity (이름 그대로).  [14,489 표준화 컬럼]
     ├─ 예(std_yn='N') → ⚠️ identity 단정 보류, "확인 필요" 표시.  [2,793]
     └─ 아니오 ↓
3) meta3 미커버 → an_schema.csv 등 외부 소스로 보완하거나 사람 판단.
```

- 근거: §B-1(리네임 커버리지), §B-2(identity 집합 분류), §B-3(분석계 실재 일치).
- 이 알고리즘이 `Meta3SchemaMapping`(§E)과 `meta3_mapping_checks.sql` 의 분류 쿼리의 기준이다.
- std_yn='N' 보류분(2,793)은 **과추출 우선**(누락보다 "확인 필요"로 남김) 원칙에 따라 미확정 처리.

---

## 부록: 재현 방법

- 본 보고서 수치는 `query_diff/structure_diff/meta3_mapping_checks.sql` 의 쿼리를 meta3-db에 **대문자 식별자**로 실행한 실제 출력이다. 매핑 갱신 시 재실행해 수치 재현 확인.
- 분석계 실재 대조: `ttp_workflow/ODS/ODS_ACUM_MBR_BYDT_AGG.sql`(`kod.contract`) ↔ meta3 `KOD.CONTRACT` 로 검증함.
