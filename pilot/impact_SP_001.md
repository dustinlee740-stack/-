# 영향 범위 분석: SP_001 (선불카드 1일 충전 한도 상향 변경)

- 요건 파일: `D:\da\pilot\SP_001.docx` (추출본 `D:\da\pilot\reqs\SP_001.md`)
- 분석 시각: 2026-05-08T<현재> (7회차 확장 — E-01~E-07 매핑 반영) — 이전 이력: 2026-05-06 1차 → 5월 6일 동일자에 도메인 전문가 정정 5회(2차 모형 갱신=정책 본체 KOD / 3차 AML=A-Safe 외부 본체 / 4차 FDS·KFDS 역할 분담 / 5차 사유 정밀화 F-XX 매핑 / 6차 F-07 책임 분리 KOD_ITN↔TBOS) → 2026-05-07 6회차 재검증(변동 없음) → 2026-05-08 7회차 확장(E-01~E-07 본문 동기화)
- 분석 주체: Claude Code (재검증) → 사용자 도메인 전문가 (이전 5회 정정 결과 보존)
- 도출된 분류: 8개 (영향 들어간 분류 기준)
- 영향 가능 컴포넌트: **19개** (1차 영향 3개 / 2차 영향 16개)
- flat 인덱스 행: **55행** (F-XX 15 / E-XX 18 / S-XX 8 / 9-X 6 / 공통 8)

요건 핵심: 선불카드 **본인인증 완료 사용자의 1일 충전 한도 50→100만원 상향**, AML 탐지 기준 동반 조정. 1회/월/잔액/미성년/법인 한도 변경 없음. F-01~F-08, S-01~S-07, E-01~E-10, DB 3개 테이블, API 4종, 자동충전 자동 조정, 분할 충전 AML 강화, 고령자 UX.

---

## 요건 ID 별 영향 컴포넌트 (flat 인덱스)

요건ID 기준 한 눈 스캔용 인덱스. 같은 컴포넌트가 여러 요건ID에 걸리면 여러 행으로 분해. 사유 컬럼은 본문 분류별 표의 축약본이며, 본문(아래 "## 영향 컴포넌트")이 진실의 원천.

### F-XX (기능 요건)

| 요건ID | 요건 이름 | Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- | --- | --- |
| F-01 | 1일 충전 한도 상향 | KOD_ITN | Kona Operation Desk Internal | 1일 한도 50→100만원 정책 본체(내부) | [components.md](components.md#kod_itn) |
| F-01 | 1일 충전 한도 상향 | KOD_ETN | Kona Operation Desk External | 1일 한도 정책 본체(외부) | [components.md](components.md#kod_etn) |
| F-01 | 1일 충전 한도 상향 | CS | Charge Service | 충전 원장 — KOD 정책 받아 한도 검증·집행 | [components.md](components.md#cs) |
| F-02 | 한도 초과 안내 문구 수정 | DDA | Display Data Api | 한도 초과 안내 문구(100만원 기준) 데이터 API | [components.md](components.md#dda) |
| F-02 | 한도 초과 안내 문구 수정 | DDV | Display Data Webview | 한도 초과 안내 문구 웹뷰 노출 | [components.md](components.md#ddv) |
| F-03 | 충전 가능액 실시간 표시 | CS | Charge Service | 당일 누적·잔여 가능액 계산(원장 로직) | [components.md](components.md#cs) |
| F-03 | 충전 가능액 실시간 표시 | PCSI | Prepaid Card Service Inquiry | 잔여 충전 가능액 실시간 표시 본체 | [components.md](components.md#pcsi) |
| F-04 | AML 탐지 기준 연동 변경 | AMLS | Aml Service | A-Safe(외부 본체)로 1일 50→100만원 새 기준값 전달 중재 어댑터 | [components.md](components.md#amls) |
| F-05 | 미성년자 예외 처리 유지 | KOD_ITN | Kona Operation Desk Internal | 미성년자 14세 미만 10만원/일 유지 정책 본체(내부) | [components.md](components.md#kod_itn) |
| F-05 | 미성년자 예외 처리 유지 | KOD_ETN | Kona Operation Desk External | 미성년자 예외 정책 본체(외부) | [components.md](components.md#kod_etn) |
| F-06 | 자동충전 설정 한도 반영 | CS | Charge Service | 자동충전 본체 — 최대 설정 100만원 반영 | [components.md](components.md#cs) |
| F-06 | 자동충전 설정 한도 반영 | KNOTIFY | Knotify | 자동충전 자동 조정 알림 본체 API | [components.md](components.md#knotify) |
| F-07 | 관리자 한도 관리 수정 | KOD_ITN | Kona Operation Desk Internal | 운영팀 사용자별 한도 정책 데이터 본체 | [components.md](components.md#kod_itn) |
| F-07 | 관리자 한도 관리 수정 | TBOS | Total Back Office Service | 운영팀 한도 조회/수정 설정 화면 본체(차세대 포탈) | [components.md](components.md#tbos) |
| F-08 | 고령자 충전 안내 강화 | PCSI | Prepaid Card Service Inquiry | 65세 이상 재확인 단계·쉬운 말 안내 데이터 | [components.md](components.md#pcsi) |

### E-XX (예외 케이스)

| 요건ID | 요건 이름 | Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- | --- | --- |
| E-01 | 미성년자 계정 | CS | Charge Service | 미성년자 14세 미만 10만원/일 — 기존 정책 유지 필요(변경 적용 제외 검증) | [components.md](components.md#cs) |
| E-01 | 미성년자 계정 | KOD_ITN | Kona Operation Desk Internal | 미성년자 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_itn) |
| E-01 | 미성년자 계정 | KOD_ETN | Kona Operation Desk External | 미성년자 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_etn) |
| E-02 | 미인증 사용자 | CS | Charge Service | 미인증 5만원/일 — 기존 정책 유지 필요(변경 없음 검증) | [components.md](components.md#cs) |
| E-02 | 미인증 사용자 | KOD_ITN | Kona Operation Desk Internal | 미인증 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_itn) |
| E-02 | 미인증 사용자 | KOD_ETN | Kona Operation Desk External | 미인증 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_etn) |
| E-03 | 법인 카드 | CS | Charge Service | 법인 별도 계약 한도 — 기존 정책 유지 필요(분기 유지 검증) | [components.md](components.md#cs) |
| E-03 | 법인 카드 | KOD_ITN | Kona Operation Desk Internal | 법인 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_itn) |
| E-03 | 법인 카드 | KOD_ETN | Kona Operation Desk External | 법인 한도 정책 — 기존 유지 필요 확인 | [components.md](components.md#kod_etn) |
| E-04 | 당일 한도 소진 후 | CS | Charge Service | "오늘 충전 한도를 모두 사용했습니다" 안내 후 차단 — 에러 처리 추가 필요 | [components.md](components.md#cs) |
| E-05 | 자정 기준 초기화 | CS | Charge Service | 23:59 충전 후 자정 초과 — 1일 한도 초기화 로직 검토 필요 | [components.md](components.md#cs) |
| E-06 | 잔액 한도 중복 | CS | Charge Service | 잔액 200만원 한도 초과분만큼 부분 충전 허용 — 로직 검토 필요 | [components.md](components.md#cs) |
| E-06 | 잔액 한도 중복 | PCSI | Prepaid Card Service Inquiry | 부분 충전 안내 로직 검토 필요 | [components.md](components.md#pcsi) |
| E-07 | PEP 고객 | AMLS | Aml Service | 정치적 주요 인물 — AML 자동 탐지·강화 모니터링 추가 필요(A-Safe 룰 본체) | [components.md](components.md#amls) |
| E-07 | PEP 고객 | KFDS | Kona Fraud Detection System | PEP 고객 강화 모니터링 — 신규 이상탐지 룰 추가 필요 | [components.md](components.md#kfds) |
| E-08 | 자동충전 초과 설정 | CS | Charge Service | 100만원 초과 자동충전 설정값 자동 조정 처리 | [components.md](components.md#cs) |
| E-08 | 자동충전 초과 설정 | KNOTIFY | Knotify | 자동충전 설정값 자동 조정 사용자 알림 발송 | [components.md](components.md#knotify) |
| E-10 | 분할 충전 시도 | KFDS | Kona Fraud Detection System | 분할 충전 탐지(24시간 5회 이상) 신규 이상탐지 룰 본체·수행자 | [components.md](components.md#kfds) |

### S-XX (화면 구성)

| 요건ID | 요건 이름 | Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- | --- | --- |
| S-01 | 충전 메인 화면 | DDA | Display Data Api | 충전 메인 — 1일 충전 가능 금액(최대 100만원) 표시 데이터 | [components.md](components.md#dda) |
| S-02 | 충전 금액 입력 | DDA | Display Data Api | 충전 금액 입력 — 잔여 충전 가능액 실시간 표시 데이터 | [components.md](components.md#dda) |
| S-03 | 충전 확인 화면 | DDA | Display Data Api | 충전 확인 — 50만원 이상 재확인 단계 데이터 | [components.md](components.md#dda) |
| S-04 | 한도 초과 안내 팝업 | DDA | Display Data Api | 한도 초과 안내 팝업 데이터(F-02 본체) | [components.md](components.md#dda) |
| S-04 | 한도 초과 안내 팝업 | DDV | Display Data Webview | 한도 초과 안내 팝업 웹뷰 노출 | [components.md](components.md#ddv) |
| S-05 | 충전 완료 화면 | DDA | Display Data Api | 충전 완료 — 잔여 충전 가능액 표시 데이터 | [components.md](components.md#dda) |
| S-06 | 자동충전 설정 | DDA | Display Data Api | 자동충전 설정 — 최대 금액 100만원 안내 데이터 | [components.md](components.md#dda) |
| S-07 | 관리자 한도 관리 | TBOS | Total Back Office Service | 운영팀 사용자 한도 조회/변경 화면 | [components.md](components.md#tbos) |

### 9-X (개발자 전달 사항)

| 요건ID | 요건 이름 | Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- | --- | --- |
| 9-1 | API 요건 | APIGW | Api Gateway | 신규/변경 API 4종(한도 조회·가능액 계산·초과 검증·AML 연동) 라우팅 등록 | [components.md](components.md#apigw) |
| 9-2 | DB 변경 사항 | KOD_ITN | Kona Operation Desk Internal | 충전한도 daily_limit_amount, 사용자한도 max_daily_charge 갱신 | [components.md](components.md#kod_itn) |
| 9-2 | DB 변경 사항 | AMLS | Aml Service | AML 탐지 기준 daily_threshold 50→100만원 A-Safe 전달 | [components.md](components.md#amls) |
| 9-3 | 비즈니스 로직 처리 순서 | CS | Charge Service | 충전 비즈니스 로직 7단계(인증·미성년·법인·누적·한도·잔액·AML) 본체 | [components.md](components.md#cs) |
| 9-4 | 주의 사항 | CS | Charge Service | 자정 초기화·자동충전 자동 조정 처리 | [components.md](components.md#cs) |
| 9-4 | 주의 사항 | KNOTIFY | Knotify | 자동충전 조정 후 사용자 알림 발송 | [components.md](components.md#knotify) |

### `-` 공통 (요건ID 직접 매핑 없음 — 한도 변경 일반 영향)

| 요건ID | 요건 이름 | Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- | --- | --- |
| - | 공통 | PCS | Prepaid Card Service | Wallet App향 선불카드 서비스 레이어 — 한도/누적 응답 흐름 변경 | [components.md](components.md#pcs) |
| - | 공통 | PIS | Prepaid Card Inquiry Service | PCSI 신규 채널 동일 사유 | [components.md](components.md#pis) |
| - | 공통 | KMC | Konacard Multi Crm | 콜센터 한도 변경 안내문·상담원 교육 1차 대상 | [components.md](components.md#kmc) |
| - | 공통 | AICC | Ai Contact Center | AI 고객센터 한도 관련 문의 응대 정책 업데이트 | [components.md](components.md#aicc) |
| - | 공통 | ACC | Agent Chatbot Core | 챗봇 코어 한도 정책 문서 갱신 | [components.md](components.md#acc) |
| - | 공통 | VCC | Visible Chatbot Core | 보이는 챗봇 코어 인덱스 갱신 | [components.md](components.md#vcc) |
| - | 공통 | VCF | Visible Chatbot Front | 보이는 챗봇 프론트 한도 안내 메시지 | [components.md](components.md#vcf) |
| - | 공통 | KNOTIFY-DMZ | Knotify Dmz | FCM/APN 라우팅 — KNOTIFY 부수 영향 | [components.md](components.md#knotify-dmz) |

---

## 6회차 재검증 결과 (2026-05-07)

**변경 사항: 없음.** 6회차 재검증에서 영향 컴포넌트 19개·위계·사유가 5월 6일 5차 정정 결과(이후 6차 정밀화 반영)와 일치함을 확인. CLAUDE.md "추론 가이드라인 9개 함정"과 메모리(`feedback_pilot_impact_inference_pitfalls.md`, `project_konacard_ledger_distinction.md`)를 독립 적용해도 결과 동일.

검증 요지:
- 정책 본체 1차 영향: KOD_ITN/KOD_ETN(한도) + KFDS(신규 분할 충전 룰) → 변동 없음
- 정책 적용자 2차 영향: CS(충전 원장) + 카드 조회 5개 + 운영 UI/고객센터 6개 + 알림 2개 + APIGW + AMLS → 변동 없음
- 검토 메모로 빠진 항목(by-pass·인증실행·통계·인프라·도메인 외) → 추가/회수 없음
- F-07 책임 분리(정책 데이터=KOD_ITN, 화면 UI=TBOS) → 그대로 유지

---

## 7회차 확장 (2026-05-08)

**변경 사항: 본문 사유 확장.** flat 인덱스에 E-01~E-07 추가 매핑(검증·로직·탐지 작업) 반영. **영향 컴포넌트 19개·위계는 변동 없음** — 동일 컴포넌트의 작업 범위(E-XX 사유)만 확장.

확장 범위:
- **E-01/E-02/E-03** (미성년자/미인증/법인 한도) → KOD_ITN/KOD_ETN/CS — "기존 정책 유지" 검증 작업 명시. 이전 "명시 제외 케이스"에서 검증 작업으로 위상 변경.
- **E-04** (당일 한도 소진 후) → CS — "오늘 충전 한도를 모두 사용했습니다" 차단 안내 에러 처리 추가.
- **E-05** (자정 기준 초기화) → CS — 1일 한도 초기화 로직 검토.
- **E-06** (잔액 한도 중복) → CS + PCSI — 잔액 200만원 한도 초과분만큼 부분 충전 허용 로직·안내 검토.
- **E-07** (PEP 고객) → AMLS + KFDS — 정치적 주요 인물 자동 탐지·강화 모니터링 추가(룰 본체는 A-Safe, 코나 측은 AMLS 어댑터 + KFDS 강화 룰).

flat 인덱스 카운터: 40행 → 55행 (E-XX 3 → 18).

---

## 도출된 분류

(영향 항목이 들어간 8개 분류만 표시. 도출은 됐지만 영향 0개로 판정한 분류는 검토 메모 참조.)

- **운영 > 운영 포탈** — **정책 본체(1차)**. 한도 정책 등록·관리(KOD) + 운영자 한도 설정 화면(TBOS).
- **거래 > 충전** — 정책 적용자(2차). CS가 KOD 정책을 받아 검증·집행.
- **거래 > 사기 탐지** — **신규 이상탐지 룰 본체(1차)**. KFDS에 E-10 분할 충전 탐지 + E-07 PEP 고객 강화 모니터링 룰 추가.
- **카드 > 카드 조회** — 잔여 충전 가능액 표시·한도 안내 문구 노출.
- **운영 > 고객센터** — 안내문·상담원 교육·챗봇 정책 문서 갱신.
- **플랫폼 > 알림** — 자동충전 자동 조정 알림·마케팅 커뮤니케이션.
- **플랫폼 > 인프라/공통** — 신규 API 라우팅(APIGW).
- **플랫폼 > 외부 연계** — AML 솔루션(A-Safe) 연계.

---

## 영향 컴포넌트 (19개)

### ◆ 1차 영향 — 정책 본체

#### 운영 > 운영 포탈 (한도 정책 본체)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| **KOD_ITN** | Kona Operation Desk Internal | **본 요건의 한도 정책 본체(내부)**. F-01(1일 한도 50→100만원), **F-05(미성년자 예외 처리 — 14세 미만 10만원/일 유지 정책)**, **F-07의 정책 데이터(운영팀 사용자별 한도)** 등록·관리 직접 수행. (F-07의 *설정 화면*은 TBOS — 2차 영향 참조) **추가**: E-01(미성년자)·E-02(미인증)·E-03(법인) 한도 정책 — 기존 유지 필요 검증 대상. | [components.md](components.md#kod_itn) |
| **KOD_ETN** | Kona Operation Desk External | **본 요건의 한도 정책 본체(외부)**. KOD_ITN과 짝으로 한도 정책(F-01, **F-05**) 변경의 직접 본체. **추가**: E-01·E-02·E-03 한도 정책 — 기존 유지 필요 검증 대상. | [components.md](components.md#kod_etn) |

#### 거래 > 사기 탐지 (신규 이상탐지 룰 본체)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| **KFDS** | Kona Fraud Detection System | **본 요건의 신규 이상탐지 룰 본체이자 수행자**. E-10 분할 충전 탐지(24시간 5회 이상)는 신규 이상탐지 룰이므로 KFDS에 룰 추가 + 수행. AML 회피 목적 패턴 재설정·금액+횟수 복합 탐지 강화. **추가**: E-07(PEP 고객) 정치적 주요 인물 강화 모니터링 신규 룰 추가. (FDS는 룰 추가 불가, 본 요건의 신규 룰 영역 아님 — 검토 메모 참조) | [components.md](components.md#kfds) |

> **외부 솔루션 영역**: F-04 AML 탐지 기준(1일 50→100만원)의 정책 본체는 외부 솔루션 **A-Safe**(코나 카탈로그 외부)이며, 코나 측 영향은 AMLS(중재 어댑터)에 한정. FDS는 A-Safe 룰을 *수행*하지만 룰 추가 불가이므로 본 요건의 변경 주체 아님.

### ◆ 2차 영향 — 정책 적용자 (도메인 원장 + 흐름 컴포넌트)

#### 거래 > 충전

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| CS | Charge Service | **충전 도메인 원장**. KOD 정책을 받아 적용하는 클라이언트. F-01 한도 검증, F-03 가능액 표시, **F-06 자동충전 설정 한도 100만원 반영(자동충전 본체)**, 9-3 비즈니스 로직(누적액 조회·한도 검증·잔액 한도 검증), AML 누적 충전액 전달 직접 구현. **추가**: E-01·E-02·E-03(미성년/미인증/법인) 한도 분기 — 기존 정책 유지 검증; E-04 당일 한도 소진 후 차단 안내 에러 처리 추가; E-05 자정 기준 1일 한도 초기화 로직 검토; E-06 잔액 200만원 한도 초과분만큼 부분 충전 허용 로직 검토. | [components.md](components.md#cs) |

#### 카드 > 카드 조회

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| PCS | Prepaid Card Service | Wallet App향 선불카드 서비스 레이어. 사용자 한도/누적 정보 조회 응답 — KOD 정책에 따라 응답 데이터 흐름 변경. | [components.md](components.md#pcs) |
| PCSI | Prepaid Card Service Inquiry | **F-03 잔여 충전 가능액 실시간 표시 본체**. 카드 한도 노출 화면 데이터 제공자. **F-08 고령자 충전 안내(65세 이상 재확인 단계·쉬운 말 안내) 데이터** 제공. **추가**: E-06 잔액 한도 초과분만큼 부분 충전 시 안내 로직 검토. | [components.md](components.md#pcsi) |
| PIS | Prepaid Card Inquiry Service | PCSI 신규 채널 동일 사유. | [components.md](components.md#pis) |
| DDA | Display Data Api | **F-02 한도 초과 안내 문구 수정**(100만원 기준 업데이트), S-01~S-06 한도 안내 문구·잔여 한도 표시 데이터 API. | [components.md](components.md#dda) |
| DDV | Display Data Webview | **F-02 한도 초과 안내 문구 수정** 웹뷰. DDA와 짝으로 안내 문구 노출 채널. | [components.md](components.md#ddv) |

#### 운영 > 운영 포탈 (보조 — 운영자 설정 화면)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| TBOS | Total Back Office Service | **F-07 운영팀 사용자별 한도 조회/수정 설정 화면 본체**(차세대 포탈). KOD_ITN이 정책 데이터를 들고 있지만, 운영자가 실제로 한도를 조회·수정하는 UI는 TBOS가 제공. | [components.md](components.md#tbos) |

#### 운영 > 고객센터

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KMC | Konacard Multi Crm | 콜센터. 한도 변경 안내문·상담원 교육 1차 대상. 사용자 한도/누적 충전액 조회 화면. | [components.md](components.md#kmc) |
| AICC | Ai Contact Center | AI 고객센터. 한도 관련 문의 응대 정책 업데이트. | [components.md](components.md#aicc) |
| ACC | Agent Chatbot Core | 챗봇 코어(LLM+도메인 문서). 한도 정책 문서 갱신. | [components.md](components.md#acc) |
| VCC | Visible Chatbot Core | 보이는 챗봇 코어 인덱스 갱신. | [components.md](components.md#vcc) |
| VCF | Visible Chatbot Front | 보이는 챗봇 프론트 한도 안내 메시지. | [components.md](components.md#vcf) |

#### 플랫폼 > 알림

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KNOTIFY | Knotify | 알림 본체 API. **F-06/E-08 자동충전 자동 조정 알림**, 마케팅 커뮤니케이션 발송 정책 진입점. | [components.md](components.md#knotify) |
| KNOTIFY-DMZ | Knotify Dmz | FCM/APN 라우팅. 정책은 KNOTIFY에서 결정되므로 부수 영향. | [components.md](components.md#knotify-dmz) |

#### 플랫폼 > 인프라/공통

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| APIGW | Api Gateway | 앱-서비스 API 게이트웨이. **9-1 신규/변경 API 4종**(한도 조회·충전 가능액 계산·한도 초과 검증·AML 탐지 연동) 라우팅 등록 동반. | [components.md](components.md#apigw) |

#### 플랫폼 > 외부 연계

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| AMLS | Aml Service | **A-Safe(외부 AML 솔루션) ↔ 코나 중재 어댑터**. AML 탐지 기준 본체는 A-Safe(카탈로그 외부)이며, AMLS는 코나 측에서 A-Safe로 호출/응답을 중계. **F-04 AML 탐지 기준 변경**이 A-Safe에 반영되는 흐름의 핵심 어댑터. 정책 본체 자체는 아니지만 새 기준값 전달 흐름 변경에 영향. **추가**: E-07(PEP 고객) 정치적 주요 인물 자동 탐지·강화 모니터링 기준 전달(룰 본체는 A-Safe). | [components.md](components.md#amls) |

---

## 검토 메모 (영향 없음 판정)

### 함정 #2/#4 — 충전 도메인 원장 혼동, 호출 vs 변경

충전의 원장은 CS이고, 아래는 CS의 응답을 by-pass하거나 raw data를 적재할 뿐, 본 요건이 변경을 요구하지 않음:
- **PP** — CS의 API Response를 그대로 by-pass하는 결제 라우팅. 직접 영향 없음.
- **IAS** — 결제 도메인 원장. 충전 거래는 CS가 주는 raw data만 적재. 직접 영향 없음.
- **ACS** — 거래 누적. IAS 데이터 기반 적재로 본 요건 무관.
- **VVAN** — 가맹점/단말기 검증, VAN 대행. CS 응답 by-pass.
- **EGS** — Portal/고객센터 → 코어 라우팅. 원장 응답 by-pass.
- **BGS** — 충전 시 은행 호출 경로지만 본 요건이 BGS 변경 요구 없음.
- **CMS / DCP** — 충전 시 카드 상태 *조회*만 호출, 본 요건이 라이프사이클 변경 요구 없음.
- **MAP** — 충전 시 회원 상태 *조회*만 호출, 본 요건이 등급 정책 변경 요구 없음.

### 함정 #5 — 인증 실행 vs 인증 결과 조회

본 요건은 본인인증 *결과 조회*만 수행, 인증 *실행* 자체에 변경 없음:
- **NICE-CORE** — KG Mobiliance 본인인증 실행. 본 요건은 "본인인증 됐는지" 조회만.
- **NCS** — KG이니시스 통합인증 실행. 동일 사유.
- **CVS** — 신분증 인증. 카탈로그 "충전한도 상향 시 사용" 문구는 *신분증 인증으로 등급이 상승할 때* 의미이지 *한도값 변경 시*가 아님(함정 #9 카탈로그 어휘 매칭).
- **UIS** — 신분증 진위 확인. 본 요건 변경 영역 아님.

### 함정 #6 — 통계/집계는 원장 데이터 의존

원장 데이터를 받아 적재할 뿐, 본 요건 정책 변경으로 직접 변경 없음:
- **SAS** — 통계 시각화. 추후 한도 변경 후 통계 추적이 필요하면 별도 요건.
- **CBSS** — 혜택 집계. 원장 데이터 기반 적재.
- **TBOSB** — 차세대 포탈 배치. SAS 통계 의존.

### 함정 #7 — 인프라 일반론

본 요건의 직접 영향 없음:
- **AGS** — JWT 인증 게이트웨이. 본 요건은 인증 정책 변경 아님.
- **KMS** — HSM 키 관리. 본 요건은 키 정책 변경 아님.
- **KAFKA** — 분산 스트리밍. 본 요건은 메시지 흐름 신규 추가 아님.
- **SCC** — OpenAPI 설정 통합 관리. 본 요건은 OpenAPI 영역 아님.

### 함정 #8 외 — 알림 채널 본체 외

알림 정책은 KNOTIFY에서 결정. 채널 컴포넌트 자체는 변경 없음:
- **SMS-CORE** — 문자 발송 중계.
- **BIG_AGENT** — BGF SMS Agent.
- **IMC_AGENT** — IMC SMS Agent.

### 도메인 외/명시 제외

- **KPG** — 신용카드 충전 채널. 신용카드는 충전 한도가 없음(선불카드 법률에 의거 선불카드만 적용).
- **CRMS** — 법인 충전. **E-03(법인 카드 한도 변경 없음)**에 의거하여 정책 무관.
- **ATC** — 어드민(코나 재무팀) 전용 Bulk 충전. 사용자 1일 한도 영역 아님.
- **APS** — 충전 단말기 인증. 매장 충전 영역, 사용자 앱 1일 한도와 결합 약함.
- **FDMS** — 마스터카드 해외 FDS. 해외결제 도메인.
- **FDS** — 기존 이상탐지 수행 전용(룰 추가 불가). 본 요건의 신규 룰(E-10)은 KFDS, F-04 AML 기준값은 A-Safe 본체 → FDS는 변경 주체 아님(코드·설정 변경 없이 새 값을 받아 수행만).
- **KCPS** — 쿠폰 정책 본체이지만 본 요건은 쿠폰 무관.
- **KPS / CRS / KSTS** — 포인트/리워드/스탬프. 충전 자체에 적립 정책 결합 없음.
- **SYSTEM PORTAL** — 카드 발급 전문 영역.
- **CLR / CLR_KT** (정산) / **TCS** (대사) / **FPS** (과금) — 충전은 정산 대상이지만 한도 변경 자체가 정산 정책 변경 아님.
- **FEP** (외부 매입사) / **EWSM** (MG ARS) / **USERSITE** — 채널 명시 변경 없음.
- **OpenAPI 22개 전체** — 외부 OpenAPI 채널이 사용자 1일 한도 공유 여부는 정책 의존, 본 요건이 OpenAPI 채널을 명시 변경하지 않음.
- **카드 발급** (CARDSE, CDM, CIMS, CAMS, EAS, ECA, IIS, KBC_B, AFS) — 발급은 변경 없음.
- **모빌리티/외국인/마이데이터/정책지원금/B2B 비즈포탈/가맹점/광고/외환·송금** — 도메인 외.
- **회원 이관/메시징/트래픽/쿼리** (BUSAN, TSS, ELASTIC, MONGO, FTM, KTC, KTCA, QRS) — 인프라.
- **DB 보안/암호화** (CUBEONE AGENT, CUBEONE POLICY, PLD, RPG-KM) — 인프라.
- **본인인증 보조** (CA, SPS) — 인증서 발급/안심번호.
- **전자문서/외부제휴** (SDTS, EDM, LSS, EPMS, ICMS) — 외부 연계.
- **모니터링** (DBMT, KFM, RDMT) — 운영 모니터링.
- **모집인** (KCMW, KCS) — 모집 실적과 충전 한도 분리.

### 명시 제외 케이스

(E-01·E-02·E-03은 7회차 확장에서 "기존 정책 유지 검증 작업"으로 위상 변경 — KOD_ITN/KOD_ETN/CS 본문 사유 및 flat 인덱스 참조. 본 절은 향후 명시 제외 케이스 추가 시 사용.)

검토 메모 항목들은 요건이 확장되거나 명시 제외 조건이 풀리면 즉시 영향 컴포넌트로 재분류 대상.
