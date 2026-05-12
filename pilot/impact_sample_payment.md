# 영향 범위 분석: sample_payment.md (결제 환불 자동화 검토)

- 요건 파일: `D:\da\pilot\reqs\sample_payment.md`
- 분석 시각: 2026-05-08T12:00:00 (6회차 정정 — CLAUDE.md 추론 가이드라인 #1~#9 자체 적용) — 이전 이력: 2026-05-06 1차(카탈로그 어휘 매칭, 38개) → 5월 7일 2차 도메인 원장 매핑(환불=RS, IAS는 raw data 제공만) + by-pass 라우팅 제거 → 5월 7일 3차 호출 vs 변경 분리(CMS/DCP/MAP/AGS 검토 메모) → 5월 8일 4차 FDS/KFDS 역할 분담(FDS 제거, KFDS 1차 편입, 사유 갱신) → 5월 8일 5차 정책 본체 KOD 모형 적용(KOD_ITN/KOD_ETN 2차) → 5월 8일 6차 사유 정밀화
- 분석 주체: Claude Code (CLAUDE.md 함정 #1~#9 자체 적용 정정)
- 도출된 분류: 10개 (영향 들어간 분류 기준)
- 영향 가능 컴포넌트: **18개** (1차 영향 2개 / 2차 영향 16개)

요건 핵심: 가맹점 결제의 환불 신청을 콜센터 → **사용자 앱**으로 이관, RS 환불 자동화 본체에 사용자 앱 채널 신설, 부정 거래 자동 보류 신규 룰 도입, 가맹점 알림·정산 영향 반영. 제외: B2B 정산 변경, 해외 결제 환불.

---

## 도출된 분류

- **거래 > 환불** — RS 본체. 사용자 앱 채널 신설 = 본 요건의 핵심 변경 도메인.
- **거래 > 사기 탐지** — 부정 거래 자동 보류 신규 룰(KFDS).
- **거래 > 정산** — "정산 영향 반영" 명시(CLR/CLR_KT/FPS).
- **카드 > 카드 조회** — 사용자 앱에서 거래내역·환불 조회(PCS/PCSI/PIS).
- **가맹점 > 가맹점 포탈** — 가맹점 거래 동기화(MPT).
- **플랫폼 > 알림** — "가맹점 알림 발송"(KNOTIFY 본체).
- **플랫폼 > 인프라/공통** — 사용자 앱 환불 신청 API 신규(APIGW).
- **운영 > 고객센터** — 콜센터 환불 일부 자동화 이관(KMC).
- **운영 > 운영 포탈** — 환불 정책 등록·관리(KOD_ITN/KOD_ETN).
- **부가서비스 > 포인트·리워드** — 결제 후속 회수(KPS/CRS/KCPS/KSTS).

(검토 메모로 이동된 분류: 거래 > 결제, 거래 > 거래 인프라, 카드 > 카드 관리, 플랫폼 > 외부 연계, 회원·인증 — 모두 본 요건의 변경 주체 아님. 자세한 이유는 ## 검토 메모 참조.)

---

## 영향 컴포넌트

### 거래 > 환불 (1차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| **RS** | Refund Service | **환불 도메인 원장**. 사용자 앱 채널 신설 = 핵심 변경. 환불 자동화 본체로 정지/해지 카드 환불 정책 처리, 가맹점 알림·정산 트리거, 부정 거래 자동 보류 워크플로우 통합. | [components.md](components.md#rs) |

### 거래 > 사기 탐지 (1차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| **KFDS** | Kona Fraud Detection System | **신규 이상탐지 룰 본체+수행자**. "부정 거래 패턴 → 자동 보류 + 검토 큐 적재" 신규 룰 추가. 기존 FDS는 룰 추가 불가(read-only)이므로 본 요건의 신규 룰 변경 주체는 KFDS. | [components.md](components.md#kfds) |

### 거래 > 정산 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| CLR | Clearing | 환불 발생 시 수수료/대금 재계산 — "정산 영향 반영" 명시. RS 환불 처리 후 정산 데이터 흐름. | [components.md](components.md#clr) |
| CLR_KT | Clearing Kotlin | CLR 신규 동일 사유. | [components.md](components.md#clr_kt) |
| FPS | Fee Policy System | 환불 수수료 정책 정의 가능성 — 환불 자동화에 수수료 도입 시 적용자. | [components.md](components.md#fps) |

### 카드 > 카드 조회 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| PCS | Prepaid Card Service | Wallet App 향 선불카드 서비스 레이어. 환불 신청 화면이 PCS 호출하여 거래내역·카드 정보 조합 응답. | [components.md](components.md#pcs) |
| PCSI | Prepaid Card Service Inquiry | **사용자 거래내역·환불 조회 본체**. 사용자 앱 환불 화면이 직접 사용 — 채널 신설로 응답 데이터·UI 흐름 변경. | [components.md](components.md#pcsi) |
| PIS | Prepaid Card Inquiry Service | PCSI 신규 채널 동일 사유. | [components.md](components.md#pis) |

### 가맹점 > 가맹점 포탈 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| MPT | Merchant Portal Two | 가맹점 거래내역·통계, 거래 취소. 환불 발생 시 가맹점 측 동기화 — 요건 "가맹점 알림·정산 영향" 명시. | [components.md](components.md#mpt) |

### 플랫폼 > 알림 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KNOTIFY | Knotify | **알림 본체 API**. "가맹점 알림 발송" 명시 — KNOTIFY가 SMS/Push/E-Mail 발송 정책 본체. 환불 자동화에 따른 가맹점 알림 신규 흐름 정의. | [components.md](components.md#knotify) |

### 플랫폼 > 인프라/공통 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| APIGW | Api Gateway | 사용자 앱 환불 신청 API 신규 — 라우팅·세션 등록. | [components.md](components.md#apigw) |

### 운영 > 고객센터 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KMC | Konacard Multi Crm | 콜센터 환불 처리 화면. 일부 케이스 사용자 앱 이관 = 흐름 분기·상담원 가이드 변경. | [components.md](components.md#kmc) |

### 운영 > 운영 포탈 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KOD_ITN | Kona Operation Desk Internal | 환불 정책 본체(내부). 환불 자동화 정책 등록·관리, 정지/해지 카드 환불 처리 정책 데이터. | [components.md](components.md#kod_itn) |
| KOD_ETN | Kona Operation Desk External | 환불 정책 본체(외부). KOD_ITN 짝으로 외부 채널 정책 정보 제공. | [components.md](components.md#kod_etn) |

### 부가서비스 > 포인트·리워드 (2차 영향)

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KPS | Kona Point System | 결제 시 적립 포인트 회수. 환불 자동화의 후속 트랜잭션. | [components.md](components.md#kps) |
| CRS | Customer Reward System | 활성 리워드 조건 재검사·회수. | [components.md](components.md#crs) |
| KCPS | Kona Coupon System | 결제 사용 쿠폰 복원/취소. 쿠폰 정책 본체. | [components.md](components.md#kcps) |
| KSTS | Kona Stamp System | 결제 이력 기준 스탬프 적립 → 환불 시 취소. | [components.md](components.md#ksts) |

---

## 검토 메모 (정정 사이클로 영향에서 제거된 항목)

**도메인 원장 매핑 #1·#2 — 환불 원장은 RS, IAS 아님**
- **IAS** — 결제 원장(승인/지불/환불). 환불 정책·플로우의 직접 본체 아님. RS에 거래 raw data 제공만. 1차 분석에서 잘못 1순위로 잡힘.

**by-pass 라우팅 #3 — 정책·플로우 자체 변경 없음**
- **PP** — 카드 거래 흐름 게이트웨이(VAN ISO8583). 환불 거래도 by-pass.
- **VVAN** — 가맹점/단말기 검증. by-pass.
- **EGS** — 콜센터·포탈 → 코어 라우팅. by-pass.
- **BGS** — 카드 잔액 → 은행 환불 시 호출되는 은행 API. RS가 환불 처리 본체, BGS 자체 변경 없음.
- **FEP** — 외부 매입사로 환불 거래 전송 변환. by-pass.

**호출됨 vs 변경됨 #4 — 단순 조회·적재만 받음**
- **CMS** — 카드 원장. 환불 신청 시 정지/해지 상태 조회만, RS가 정책 판단. CMS 자체 변경 없음.
- **DCP** — 모바일 카드 라이프사이클. CMS와 동일 — 호출만 받음.
- **ACS** — 거래 누적. RS 환불 처리 후 raw data 받아 적재.
- **ITA(TMS)** — 토큰 어댑터. 환불 시 토큰 관련 동작은 RS 책임, ITA 자체 변경 없음.
- **TSP** — 토큰 발행/조회 본체이나 환불 시 신규 토큰 발행 불필요.
- **CPG/EZPS/KPG/RPG/COPS** — 결제 게이트웨이. 환불은 RS 본체 처리, 본 게이트웨이는 결제 시 호출자(환불 라우팅의 직접 변경 주체 아님). COPS 모아서 결제 환불 흐름은 별도 정의 시 확장 가능 — 본 요건 명시 범위 아님.
- **TCS** — VAN 대사. RS의 환불 거래 raw data 받아 처리.

**이상탐지 룰 — FDS는 룰 추가 불가**
- **FDS** — 기존 이상탐지 수행 전용(룰 추가 불가). 본 요건의 "부정 거래 자동 보류 신규 룰"은 KFDS 영역. FDS는 변경 주체 아님. 1차 분석의 `KFDS = A-safe 대체`는 카탈로그 outdated 표현을 그대로 옮긴 #9 함정.

**인증 실행 vs 조회 #5 — 인증 실행 자체 변경 없음**
- **MAP** — 사용자 앱 인증·라이프사이클. 환불 신청 시 본인 식별만 수행, 인증 실행 자체 변경 없음.
- **AGS** — JWT 기반 인증 게이트웨이. 환불 API는 신규지만 게이트웨이 자체 변경 없음.

**인프라 일반론 #7 — 직접 영향 없음**
- **KAFKA** — 메시징 인프라. "검토 큐 적재"가 명시되지만 새 토픽 정의는 RS/KFDS 영역, KAFKA 자체 변경 없음.
- **KNOTIFY-DMZ** — FCM/APN 라우팅. 정책은 KNOTIFY, DMZ는 부수 영향만.
- **SMS-CORE** — SMS 발송 중계. 정책은 KNOTIFY, SMS-CORE 자체 변경 없음.

**외부 솔루션 의존 — 본 요건에 변경 명시 없음**
- **AMLS** — AML 검증 가능성이나 본 요건에 AML 새 기준 변경 명시 없음. A-Safe(외부)가 본체, 본 요건은 어댑터 변경 사유 부재.

**채널 분리 — 본 요건 범위 외**
- **USERSITE** — 앱 없는 사용자 채널. 본 요건은 "사용자 앱" 이관 — USERSITE는 무관.
- **PARTNER PORTAL** — 파트너 거래·정산. 본 요건은 "가맹점"(MPT 영역) 명시 범위.

**통계 의존 #6 — 원장 데이터 의존, 정책 변경 아님**
- **TBOS** — 차세대 포탈(통계·집계·정산). 본 요건은 환불 정책 변경이 아닌 채널·플로우 변경. 통계가 자연스럽게 갱신되나 본 요건 명시 변경은 아님.

**도메인 외 — 1차 분석에도 검토 메모로 처리됨 (유지)**
- **FDMS** (해외결제 FDS), **CAS/BAS** (카드 인증), **MING** (앱 QR), **AFS/CAMS/CDM/CIMS/EAS/ECA/IIS/KBC_B** (카드 신청·발급·배송), **DDA/DDV** (앱 전시), **AICC/ACC/VCC/VCF** (AI 챗봇), **BIZS/BIZB/BIZU/BPP** (B2B), **ORS** (해외 송금), 재난지원금/정책수당 분류, 모빌리티 분류 — 본 요건 도메인 외.

---

## 정정 사이클 메모

본 산출물은 1차 분석(2026-05-06T09:40:00)에서 카탈로그 어휘 매칭 의존으로 다수의 false positive를 포함했었음. 5회 정정을 거쳐 18개로 수렴. 핵심 학습:

1. **환불 도메인 원장은 RS, IAS 아님** — CLAUDE.md 도메인 메모 핵심 원칙. 1차에서 IAS를 환불 자동화의 "직접 변경 대상"으로 잡은 것이 가장 큰 오류였음.
2. **이상탐지 룰 본체 = KFDS, FDS 아님** — FDS는 기존 룰 수행 전용. 본 요건의 "부정 거래 자동 보류 신규 룰"은 명백히 KFDS 영역. `KFDS = A-safe 대체`는 카탈로그 outdated 표현(#9 어휘 매칭 함정).
3. **by-pass 게이트웨이 다수 포함이 1차 분량 인플레이션의 주원인** — PP/VVAN/EGS/BGS/FEP + CPG/EZPS/KPG/RPG/COPS 모두 라우팅 컴포넌트로서 정책·플로우 자체 변경 없음. RS가 환불 처리하는 동안 by-pass 역할만.
4. **사용자 앱 = MAP/AGS 영향이라는 결합도 위험** — 본 요건은 환불 *채널 신설*이지 인증 *흐름 변경*이 아니므로 MAP/AGS는 영향 아님. 사용자 앱 환불 조회는 PCSI/PIS/PCS 영역.
5. **"검토 큐 적재" = KAFKA 영향이라는 어휘 매칭 함정** — 새 토픽 정의는 토픽 소유자(RS/KFDS) 영역. 인프라(KAFKA) 자체는 변경 안 됨.
