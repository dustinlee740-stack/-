# 영향 범위 분석: sample_payment.md (결제 환불 자동화 검토)

- 요건 파일: `D:\da\pilot\reqs\sample_payment.md`
- 분석 시각: 2026-05-06T09:40:00
- 도출된 분류: 15개 (대분류 6개)
- 영향 가능 컴포넌트: 38개

요건 핵심: 가맹점 결제의 환불 신청을 콜센터 → 사용자 앱으로 이관, IAS 거래 원장과 자동 연계, CMS 카드 라이프사이클 상태 확인, 가맹점 알림+정산 영향 반영, FDS 부정 거래 패턴 시 자동 보류·검토 큐 적재. 제외: B2B 정산 변경, 해외 결제 환불.

---

## 도출된 분류

- **거래 > 결제** — 환불은 결제 거래 흐름의 일부. IAS·PP·FDS가 정확히 매칭됨.
- **거래 > 정산** — 요건에 "정산 영향 반영" 명시.
- **거래 > 환불** — 환불 서비스 본업.
- **거래 > 거래 인프라** — VAN·매입사로 환불 거래 전송.
- **카드 > 카드 관리** — "카드 라이프사이클(CMS)" 명시.
- **카드 > 카드 조회** — 사용자 앱에서 결제 내역·환불 조회 필요.
- **가맹점 > 가맹점 포탈** — 가맹점 측 거래 내역·정산 동기화.
- **플랫폼 > 알림** — "가맹점에 알림 발송" 명시.
- **플랫폼 > 인프라/공통** — 사용자 앱 API 추가, 환불·검토 큐 메시징.
- **플랫폼 > 외부 연계** — AML 검증·은행 환불 계좌 연동 가능성.
- **회원·인증 > 회원** — 사용자 앱 인증, 거래내역 조회.
- **회원·인증 > 인증** — 환불 신청 시 본인 확인.
- **운영 > 고객센터** — 콜센터 환불 흐름 일부가 자동화로 이관.
- **운영 > 운영 포탈** — 환불·수수료·정산 정책 운영.
- **부가서비스 > 포인트·리워드** — 결제 환불 시 적립 포인트/리워드/스탬프 회수.

---

## 영향 컴포넌트

### 거래 > 결제

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| IAS | Issuer Authorization System | 거래 원장(승인/지불/환불) 본체. 자동 환불 흐름의 정책·트랜잭션 변경 직접 대상. | [components.md](components.md#ias) |
| PP | Payment Processor | 충전/환불/잔액 이동/지불 모든 카드 거래 흐름의 게이트웨이. 환불 자동 라우팅 변경 대상. | [components.md](components.md#pp) |
| FDS | Fraud Detection System | 부정 거래 패턴 감지 → 자동 보류 정책 추가. 환불 신청에 대한 신규 룰 도입 대상. | [components.md](components.md#fds) |
| KFDS | Kona Fraud Detection System | A-safe 대체 신규 FDS. FDS와 동일 사유로 룰·플로우 변경. | [components.md](components.md#kfds) |
| ACS | Accumulation Calculation System | 환불 시 거래 누적 데이터 차감/조정 필요. | [components.md](components.md#acs) |
| ITA(TMS) | Issuer Token Adapter | 환불 거래도 토큰 검증·해제 대상. | [components.md](components.md#itatms) |
| TSP | Token Service Provider | 환불 거래의 토큰 처리. | [components.md](components.md#tsp) |
| CPG | Credit Payment Gateway | 신용카드 환불 중계. | [components.md](components.md#cpg) |
| EZPS | Easy Payment Service | 신용카드 간편결제 관리, 환불 시 매핑 필요. | [components.md](components.md#ezps) |
| KPG | Kona Payment Gateway | 신용카드 충전 환불 시 영향. | [components.md](components.md#kpg) |
| RPG | Remote Payment Gateway | 온라인 결제 환불 흐름. | [components.md](components.md#rpg) |
| COPS | Co Payment Service | 모아서 결제(공동 결제)의 환불은 별도 흐름. 정책 정의 필요. | [components.md](components.md#cops) |

### 거래 > 환불

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| RS | Refund Service | 환불 서비스 본체(카드 잔액 계좌 환불, 콜센터 환불). 사용자 앱 채널 신설 = 핵심 변경. | [components.md](components.md#rs) |

### 거래 > 정산

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| CLR | Clearing | 환불 발생 시 수수료/대금 재계산. | [components.md](components.md#clr) |
| CLR_KT | Clearing Kotlin | CLR 신규 정산. 동일 사유. | [components.md](components.md#clr_kt) |
| TCS | Transaction Compare System | 환불 거래도 VAN 대사 대상. | [components.md](components.md#tcs) |
| FPS | Fee Policy System | 환불 수수료 정책 도입 가능성. | [components.md](components.md#fps) |

### 거래 > 거래 인프라

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| FEP | Front End Point | 외부 매입사로 환불 거래 전송 시 변환. | [components.md](components.md#fep) |
| VVAN | Virtual Value Addition Network | 환불 거래 검증(ISO8583, 결제 로직). | [components.md](components.md#vvan) |

### 카드 > 카드 관리

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| CMS | Card Management System | 카드 원장. 정지/해지된 카드 환불 정책의 라이프사이클 상태 조회 대상. | [components.md](components.md#cms) |
| DCP | Digital Card Platform | 모바일 카드 라이프사이클(DELETE/ACTIVE/SUSPENDED). 환불 시 상태 확인. | [components.md](components.md#dcp) |

### 카드 > 카드 조회

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| PCS | Prepaid Card Service | 카드 기준 정보 조회 + 라이프사이클 관리. 환불 신청 시 호출. | [components.md](components.md#pcs) |
| PCSI | Prepaid Card Service Inquiry | 사용자 거래내역·환불 조회 본체. 사용자 앱 환불 화면이 직접 사용. | [components.md](components.md#pcsi) |
| PIS | Prepaid Card Inquiry Service | PCSI 신규 채널. 동일 사유. | [components.md](components.md#pis) |

### 가맹점 > 가맹점 포탈

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| MPT | Merchant Portal Two | 가맹점 거래내역/통계, 거래 취소. 환불 발생 시 동기화. | [components.md](components.md#mpt) |
| PARTNER PORTAL | Partner Portal | 파트너 거래/정산 내역 조회. 정산 영향 반영. | [components.md](components.md#partner-portal) |

### 플랫폼 > 알림

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KNOTIFY | Knotify | SMS/Push/E-Mail 알림 본체. 가맹점 알림 발송. | [components.md](components.md#knotify) |
| KNOTIFY-DMZ | Knotify Dmz | FCM/APN 라우팅. 사용자 앱 푸시 환불 처리 결과. | [components.md](components.md#knotify-dmz) |
| SMS-CORE | Sms Core | 가맹점 SMS 발송 중계. | [components.md](components.md#sms-core) |

### 플랫폼 > 인프라/공통

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| APIGW | Api Gateway | 사용자 앱 환불 신청 API 추가 시 세션·라우팅 변경. | [components.md](components.md#apigw) |
| EGS | External Gateway System | 콜센터·포탈에서 코어로의 환불 호출. | [components.md](components.md#egs) |
| KAFKA | Apache Kafka | 환불 이벤트·검토 큐 적재용 메시징. | [components.md](components.md#kafka) |

### 플랫폼 > 외부 연계

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| AMLS | Aml Service | 환불도 AML 검증 대상일 가능성(자금세탁 우회 방지). | [components.md](components.md#amls) |
| BGS | Bank Gateway Service | 카드 잔액 → 사용자 은행 계좌 환불 시 은행 API. | [components.md](components.md#bgs) |

### 회원·인증

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| MAP | Mobile Application Platform | 사용자 앱(Wallet) 인증·라이프사이클. 환불 신청 사용자 식별. | [components.md](components.md#map) |
| AGS | Authorization Gateway Service | JWT 기반 환불 API 라우팅 인증. | [components.md](components.md#ags) |
| USERSITE | User Site | 앱이 없는 사용자가 거래내역/환불을 조회하는 채널. 변경 파급 가능. | [components.md](components.md#usersite) |

### 운영 > 고객센터

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KMC | Konacard Multi Crm | 콜센터 환불 처리 화면. 일부 케이스가 사용자 앱으로 이관되며 흐름 분기. | [components.md](components.md#kmc) |

### 운영 > 운영 포탈

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KOD_ITN | Kona Operation Desk Internal | 결제 우선순위·수수료·정산 정책 정보. 환불 정책 신규 등록 대상. | [components.md](components.md#kod_itn) |
| TBOS | Total Back Office Service | 차세대 포탈(통계/집계/정산 포함). 환불 통계 노출. | [components.md](components.md#tbos) |

### 부가서비스 > 포인트·리워드

| Name | Full Name | 영향 사유 | 링크 |
| --- | --- | --- | --- |
| KPS | Kona Point System | 결제 시 적립된 포인트 회수. 환불 자동화의 후속 트랜잭션. | [components.md](components.md#kps) |
| CRS | Customer Reward System | 활성 리워드 조건 재검사·회수. | [components.md](components.md#crs) |
| KCPS | Kona Coupon System | 결제에 사용된 쿠폰 복원/취소. | [components.md](components.md#kcps) |
| KSTS | Kona Stamp System | 결제 이력 기준 스탬프 적립 → 환불 시 취소. | [components.md](components.md#ksts) |

---

## 검토 메모(영향 가능성 낮음으로 판정 — 추후 검토 가능)

- **FDMS** (마스터카드 해외결제 FDS 매입사 KB 연동) — 요건에서 "해외 결제 환불은 차후 단계"로 명시 제외. 다만 fraud 룰 정의가 글로벌하게 변경되면 간접 영향.
- **CAS / BAS** (카드 인증) — 환불 흐름에 카드 인증 재호출은 통상 불필요. 정책 변경 시 재검토.
- **MING** (앱 QR 표시) — 환불은 QR과 무관.
- **AFS / CAMS / CDM / CIMS / EAS / ECA / IIS / KBC_B** (카드 신청·발급·배송·재고·외부제휴) — 환불 자동화와 직접 연관 없음.
- **DDA / DDV** (앱 전시 데이터) — 데이터 표시 무관 명시.
- **AICC / ACC / VCC / VCF** (AI 챗봇) — 환불 안내에 봇 연동 가능성은 있으나 본 요건 명시 범위에 없음.
- **BIZS / BIZB / BIZU / BPP** (비즈포탈/B2B) — "B2B 정산 변경은 제외" 요건. 명시적 비범위.
- **ORS** (해외 송금) — "해외 결제 환불은 차후 단계" 제외 범위에 해당.
- **재난지원금/정책수당 분류 전체** (BIZA, GDIS, TDIS, IEPS 등) — 본 요건 도메인 외.
- **모빌리티 분류 전체** (MAS, TTS, IMCS 등) — 가맹점 결제와 도메인 분리.

검토 메모 항목들은 요건이 확장되거나 명시 제외 조건이 풀리면 재분석 필요.
