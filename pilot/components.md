# 코나카드 컴포넌트 목록

- 총 컴포넌트 수: **208**
- 대분류 수: 9 · 중분류 수: 33 · 소분류 수: 150
- 원본: `D:\da\pilot\components.xlsx` (이 md는 자동 생성, 수정 시 원본 갱신 후 재변환)

---

## 목차

- **운영** (39)
  - 고객센터 (9)
    - [ACC — Agent Chatbot Core](#acc)
    - [ACW — Agent Chatbot Web](#acw)
    - [AICC — Ai Contact Center](#aicc)
    - [KMC — Konacard Multi Crm](#kmc)
    - [KS-BATCH — Ks Data Batch Server](#ks-batch)
    - [STT — Speech To Text](#stt)
    - [VAS — Voice Assistant Service](#vas)
    - [VCC — Visible Chatbot Core](#vcc)
    - [VCF — Visible Chatbot Front](#vcf)
  - 운영 포탈 (14)
    - [AMP — Asp Management Portal](#amp)
    - [BPP — Business Portal Platform](#bpp)
    - [KBC_P — Kona Business Card Portal](#kbc_p)
    - [KOD_ETN — Kona Operation Desk External](#kod_etn)
    - [KOD_ITN — Kona Operation Desk Internal](#kod_itn)
    - [PLATFORM PORTAL — Platform Portal](#platform-portal)
    - [SYSTEM PORTAL — System Portal](#system-portal)
    - [TBOS — Total Back Office Service](#tbos)
    - [TBOSB — Total Back Office Service Batch](#tbosb)
    - [TBOST — Total Back Office Service Third Party](#tbost)
    - [TBOS_A — Total Back Office Service Account](#tbos_a)
    - [TBOS_AB — Total Back Office Service Account Api](#tbos_ab)
    - [TBOS_AM — Total Back Office Service Account Management](#tbos_am)
    - [USER PORTAL — User Portal](#user-portal)
  - 통계 (2)
    - [CBSS — Customer Benefit Segmentation Statics](#cbss)
    - [SAS — Statistics Analysis System](#sas)
  - 광고/추천 (4)
    - [DAPA — Display Advertisment Platform Api](#dapa)
    - [DAPC — Display Advertisment Platform Core](#dapc)
    - [DAPM — Display Advertisment Platform Messagebroker](#dapm)
    - [PRS — Personalized Recommendation System](#prs)
  - 모니터링/도구 (6)
    - [DBMT — Database Monitoring](#dbmt)
    - [KFM — Kona File Manager](#kfm)
    - [PRM — Personal Information Access Record Management System](#prm)
    - [RDMT — Rundeck Monitoring](#rdmt)
    - [YBAT — Konays Batch Service](#ybat)
    - [YSTORE — Konays Store Service](#ystore)
  - 외국인 (2)
    - [IBFA — Inbound Foreiner Api](#ibfa)
    - [IBFP — Inbound Foreigner Portal](#ibfp)
  - 마이데이터 (2)
    - [MYDG — My Data Gateway](#mydg)
    - [MYDS — My Data Service](#myds)
- **거래** (27)
  - 결제 (16)
    - [ACS — Accumulation Calculation System](#acs)
    - [BAS — Bconline Authentication Service](#bas)
    - [CAS — Card Authentification Service](#cas)
    - [COPS — Co Payment Service](#cops)
    - [CPG — Credit Payment Gateway](#cpg)
    - [EZPS — Easy Payment Service](#ezps)
    - [FDMS — Fds Management System](#fdms)
    - [FDS — Fraud Detection System](#fds)
    - [IAS — Issuer Authorization System](#ias)
    - [ITA(TMS) — Issuer Token Adapter](#itatms)
    - [KFDS — Kona Fraud Detection System](#kfds)
    - [KPG — Kona Payment Gateway](#kpg)
    - [MING — Mobileweb Into Native Group](#ming)
    - [PP — Payment Processor](#pp)
    - [RPG — Remote Payment Gateway](#rpg)
    - [TSP — Token Service Provider](#tsp)
  - 충전 (4)
    - [APS — Authentication Processing Server](#aps)
    - [ATC — Administrator To Card](#atc)
    - [CRMS — Corporation Recharge Management Service](#crms)
    - [CS — Charge Service](#cs)
  - 정산 (4)
    - [CLR — Clearing](#clr)
    - [CLR_KT — Clearing Kotlin](#clr_kt)
    - [FPS — Fee Policy System](#fps)
    - [TCS — Transaction Compare System](#tcs)
  - 거래 인프라 (2)
    - [FEP — Front End Point](#fep)
    - [VVAN — Virtual Value Addition Network](#vvan)
  - 환불 (1)
    - [RS — Refund Service](#rs)
- **카드** (16)
  - 카드 관리 (11)
    - [AFS — Annual Fee Service](#afs)
    - [CAMS — Card Application Manage System](#cams)
    - [CARDSE — Cardse](#cardse)
    - [CDM — Card Delivery Management (System)](#cdm)
    - [CIMS — Card Inventory Management Service](#cims)
    - [CMS — Card Management System](#cms)
    - [DCP — Digital Card Platform](#dcp)
    - [EAS — External Alliance Service](#eas)
    - [ECA — Easy Card Apply](#eca)
    - [IIS — Instant Issue Service](#iis)
    - [KBC_B — Kona Business Card Batch](#kbc_b)
  - 카드 조회 (5)
    - [DDA — Display Data Api](#dda)
    - [DDV — Display Data Webview](#ddv)
    - [PCS — Prepaid Card Service](#pcs)
    - [PCSI — Prepaid Card Service Inquiry](#pcsi)
    - [PIS — Prepaid Card Inquiry Service](#pis)
- **회원·인증** (15)
  - 인증 (9)
    - [AGS — Authorization Gateway Service](#ags)
    - [CA — Certificate Authority](#ca)
    - [CVS — Certificate Verification Service](#cvs)
    - [EWSM — External Web Service Manager](#ewsm)
    - [KMS — Key Management System](#kms)
    - [NCS — Name Check Service](#ncs)
    - [NICE-CORE — Nice Core](#nice-core)
    - [SPS — Secure Phonenumber Service](#sps)
    - [UIS — User Identification Service](#uis)
  - 회원 (6)
    - [BUSAN — Busan Core Service](#busan)
    - [KCMW — Kona Consultant Mobile Web](#kcmw)
    - [KCS — Kona Consultant Service](#kcs)
    - [MAP — Mobile Application Platform](#map)
    - [TSS — Transfer(Take-over) Support Service](#tss)
    - [USERSITE — User Site](#usersite)
- **가맹점** (8)
  - 가맹점 관리 (6)
    - [AICV — Ai Contract Validation](#aicv)
    - [BIZD — Business Portal D](#bizd)
    - [ESIGN — Esign](#esign)
    - [KAS — Kona Address System](#kas)
    - [LBMS — Location Base Merchant Service](#lbms)
    - [PMP — Payable Merchant Portal](#pmp)
  - 가맹점 포탈 (2)
    - [MPT — Merchant Portal Two](#mpt)
    - [PARTNER PORTAL — Partner Portal](#partner-portal)
- **플랫폼** (49)
  - 외부 연계 (7)
    - [AMLS — Aml Service](#amls)
    - [BGS — Bank Gateway Service](#bgs)
    - [EDM — External Data Manager](#edm)
    - [EPMS — External Portal Data Management Service](#epms)
    - [ICMS — Integrated Cash Management System](#icms)
    - [LSS — Luckyloco Support Service](#lss)
    - [SDTS — Secure Document Transfer System](#sdts)
  - 인프라/공통 (11)
    - [APIGW — Api Gateway](#apigw)
    - [BTS — Barcode Translator Service](#bts)
    - [EGS — External Gateway System](#egs)
    - [ELASTIC — Elastic Search](#elastic)
    - [FTM — File Transfer Management](#ftm)
    - [KAFKA — Apache Kafka](#kafka)
    - [KTC — Kona Traffic Controller](#ktc)
    - [KTCA — Kona Traffic Controller Api Server](#ktca)
    - [MONGO — Mongo Db](#mongo)
    - [QRS — Query Running Service](#qrs)
    - [SCC — Spring Cloud Config](#scc)
  - 알림 (5)
    - [BIG_AGENT — Big Agent](#big_agent)
    - [IMC_AGENT — Imc Agent](#imc_agent)
    - [KNOTIFY — Knotify](#knotify)
    - [KNOTIFY-DMZ — Knotify Dmz](#knotify-dmz)
    - [SMS-CORE — Sms Core](#sms-core)
  - OpenAPI (22)
    - [BMCS — Bank Mock Service](#bmcs)
    - [CISS — Card Issuance Simulator Service](#ciss)
    - [CLMK — Nice Mock Service](#clmk)
    - [OAGW — Open Api Admin Panel Gateway](#oagw)
    - [OASG — Open Api Service Gateway](#oasg)
    - [OASL — Open Api Service Layer](#oasl)
    - [OASP — Open Api Service Portal](#oasp)
    - [OASR — Open Api Service Route & Data Remapping Service](#oasr)
    - [OCAP — Open Api Center Admin Portal](#ocap)
    - [OCCMS — Open Api Center Content Management System](#occms)
    - [OCDPS — Open Api Center Data Processor Service](#ocdps)
    - [OCGW — Open Api Center Gateway](#ocgw)
    - [OCIS — Open Api Center Inquiry Service](#ocis)
    - [OCMS — Open Api Center Management System](#ocms)
    - [OCPM — Open Api Center Project Management](#ocpm)
    - [OCS — Open Api Center Site](#ocs)
    - [OCSE — Open Api Center Search Engine](#ocse)
    - [OINS — Open Api Inspector](#oins)
    - [OMCS — Open Api Mock Server](#omcs)
    - [ONOTIFY — Open Api Notify](#onotify)
    - [OPBO — Open Partner Back Office](#opbo)
    - [TGS — Tall Gate Service](#tgs)
  - 보안 (4)
    - [CUBEONE AGENT — Cubeone Agent](#cubeone-agent)
    - [CUBEONE POLICY — Cubeone Policy](#cubeone-policy)
    - [PLD — Personal Identifiable Information Leak Detection](#pld)
    - [RPG-KM — Remote Payment Gateway Key Management](#rpg-km)
- **모빌리티** (30)
  - 택시 운영/자산 (9)
    - [AMM — App Meter Manager](#amm)
    - [CSG — Call Service Gateway](#csg)
    - [MASM — Mobility Application Service Management Portal](#masm)
    - [MASP — Mobility Application Service Partner Portal](#masp)
    - [MDPS — Mobility Data Purge Service](#mdps)
    - [MIS — Mobility Integration Service](#mis)
    - [MOSP — Mobility Ota Service Portal](#mosp)
    - [MSMA — Mobility Supply Chain Management Api Service](#msma)
    - [MSMW — Mobility Supply Chain Management Web](#msmw)
  - 택시 거래/관제 (11)
    - [ESP — Elastic Search Platform](#esp)
    - [ETH — Event To Hadoop](#eth)
    - [ETM — Event To Mongo](#etm)
    - [MAS — Mobility Application Service](#mas)
    - [MAS-B — Mobility Application Service Batch](#mas-b)
    - [MAS-J — Mobility Application Service Job](#mas-j)
    - [MAS-S — Mobility Application Service Service](#mas-s)
    - [MASI — Mobility Application Service Interface](#masi)
    - [MASV — Mobility Application Service View Api](#masv)
    - [MONIS — Monitoring Interface Service](#monis)
    - [RDS — Realtime Dispatcher Service](#rds)
  - 모빌리티 정산 (2)
    - [IMCS — Integrated Mobility Clearing And Settlement](#imcs)
    - [TTS — Taxi Transaction System](#tts)
  - 배달 (5)
    - [KDS — Kona Delivery Service](#kds)
    - [LOP — Local Order Platform](#lop)
    - [LOP_DTS — Local Order Platform Data Transfer Service](#lop_dts)
    - [LOP_EXT — Local Order Platform Externel](#lop_ext)
    - [LOP_RDS — Local Order Platform Realtime Dispatcher Service](#lop_rds)
  - 모빌리티 바우처 (3)
    - [MAS_VOP — Mobility Application Service Voucher Portal](#mas_vop)
    - [MAS_VOS — Mobility Application Service Voucher Service Api](#mas_vos)
    - [MAS_VOV — Mobility Application Service Voucher View](#mas_vov)
- **정책·지원금** (11)
  - 재난지원금 (5)
    - [BIZA — Business Portal A](#biza)
    - [BIZCF — Business Portal Front](#bizcf)
    - [GDIS — Gyeonggido Disaster Service](#gdis)
    - [OGD — Onsite Grant Disbursement](#ogd)
    - [TDIS — Business Portal Total Disaster](#tdis)
  - 정책수당 (6)
    - [BIZB — Business Batch Server](#bizb)
    - [BIZS — Business Portal Api Server](#bizs)
    - [BIZU — Business Portal Cu](#bizu)
    - [IEPS — Integrated Execution Processing System](#ieps)
    - [RFS — Request For Subsidy](#rfs)
    - [RFSP — Recommendation For Subsidy Portal](#rfsp)
- **부가서비스** (13)
  - 포인트·리워드 (7)
    - [CRS — Customer Reward System](#crs)
    - [EMS — Echo Mileage Service](#ems)
    - [ETMS — Entry Ticket Management System](#etms)
    - [KCPS — Kona Coupon System](#kcps)
    - [KPS — Kona Point System](#kps)
    - [KSTS — Kona Stamp System](#ksts)
    - [MLS — Mileage Service](#mls)
  - 외환 (1)
    - [FXS — Foreign Exchange Service](#fxs)
  - 송금·기부·선물 (5)
    - [GS — Gift Service](#gs)
    - [KPF — Kona Private Funding](#kpf)
    - [ORS — Overseas Remittance Service](#ors)
    - [PMS — Pocket Money Management Service](#pms)
    - [VAM — Virtual Account Management](#vam)

---

## 컴포넌트 상세

### ACC — Agent Chatbot Core

**분류**: 운영 > 고객센터 > AI 챗봇 코어

**한글 설명**

```
목적: 지역화폐 챗봇 에이전트의 코어 서버. LLM과 지역화폐 문서, Wallet 정책/개인화 정보를 결합해 응답 생성.
주요 기능:
- AI(LLM)·도메인 문서·Wallet 정책 결합 응답 생성
- 민감정보 마스킹 처리
- ACW로 SSE 응답 전달
도메인: AI 챗봇, 지역화폐, LLM, 마스킹
연계: ACW, Wallet 서버
```

**English Description**

```
Purpose: Core server of the local-currency chatbot agent; combines LLM with domain docs and Wallet policy/personalization data.
Functions:
- Synthesize responses from LLM, knowledge base, Wallet data
- Mask sensitive personal information
- Stream responses to ACW via SSE
Domain: AI chatbot, local currency, LLM, masking
Related: ACW, Wallet servers
```

---

### ACS — Accumulation Calculation System

**분류**: 거래 > 결제 > 거래 누적

**한글 설명**

```
목적: 거래에 대한 누적 정보를 관리하고 누적 기준 이벤트에 제공.
주요 기능:
- 거래 누적 데이터 관리
- 이벤트별 누적 기준 정보 제공
도메인: 누적, 거래, 이벤트
연계: IAS
```

**English Description**

```
Purpose: Manages cumulative transaction information and feeds it to events.
Functions:
- Manage cumulative transaction data
- Provide cumulative info to event policies
Domain: accumulation, transaction, event
Related: IAS
```

---

### ACW — Agent Chatbot Web

**분류**: 운영 > 고객센터 > AI 챗봇 UI

**한글 설명**

```
목적: 지역화폐 챗봇 에이전트의 웹 서버. ACC와 SSE로 통신하며 사용자에게 화면을 실시간 렌더링.
주요 기능:
- ACC와 SSE 실시간 통신
- 사용자 UI 실시간 렌더링
도메인: AI 챗봇, 웹 UI, SSE
연계: ACC
```

**English Description**

```
Purpose: Web server of the local-currency chatbot agent; renders UI in real time via SSE with ACC.
Functions:
- Real-time SSE link to ACC
- Render chatbot UI to user
Domain: AI chatbot, web UI, SSE
Related: ACC
```

---

### AFS — Annual Fee Service

**분류**: 카드 > 카드 관리 > 연회비

**한글 설명**

```
목적: 연회비 정기 결제 서비스. 카드 출금 실패 시 계좌 출금으로 진행.
주요 기능:
- 연회비 정기 결제 처리
- 카드 출금 → 계좌 출금 순 폴백
- 카드 혜택 기준 결제
도메인: 연회비, 정기결제, 카드, 계좌출금
```

**English Description**

```
Purpose: Recurring payment service for annual fees; falls back from card debit to bank debit on failure.
Functions:
- Recurring annual fee charge
- Card debit, fallback to bank debit
- Charge based on card benefits
Domain: annual fee, recurring payment, card, bank debit
```

---

### AGS — Authorization Gateway Service

**분류**: 회원·인증 > 인증 > 인증 게이트웨이

**한글 설명**

```
목적: JWT 토큰 기반으로 인증된 API만 특정 서버로 라우팅하는 인증 게이트웨이.
주요 기능:
- JWT 토큰 검증
- 인증된 API만 백엔드 라우팅
도메인: 인증, JWT, 게이트웨이, 라우팅
```

**English Description**

```
Purpose: Authorization gateway routing only JWT-authenticated API calls to specific servers.
Functions:
- Validate JWT tokens
- Route authenticated API to backend
Domain: auth, JWT, gateway, routing
```

---

### AICC — Ai Contact Center

**분류**: 운영 > 고객센터 > AI 챗봇 코어

**한글 설명**

```
목적: AI 고객센터. 문의 의도 파악 후 시스템 정책과 개인화 데이터를 활용해 고객 서비스 운영을 간소화.
주요 기능:
- 고객 문의 의도 분석
- 정책+개인화 기반 AI 응대
- 상담 자동화
도메인: AI, 고객센터, 챗봇, 의도분석
연계: 개인화 데이터, 정책 컴포넌트
```

**English Description**

```
Purpose: AI customer-contact center; understands inquiry intent and streamlines operations using policy and personalization.
Functions:
- Detect customer inquiry intent
- Respond using policy + personalization
- Automate contact center
Domain: AI, contact center, chatbot, intent
Related: personalization, policy components
```

---

### AICV — Ai Contract Validation

**분류**: 가맹점 > 가맹점 관리 > 가맹점 검증

**한글 설명**

```
목적: 가맹점 계약 검증 컴포넌트. 가맹점 계약 검수 API 제공.
주요 기능:
- 가맹점 계약 검수 API 제공
도메인: 가맹점, 계약, 검증, API
```

**English Description**

```
Purpose: Merchant contract validation component (API server).
Functions:
- Provide merchant contract validation API
Domain: merchant, contract, validation, API
```

---

### AMLS — Aml Service

**분류**: 플랫폼 > 외부 연계 > AML 연계

**한글 설명**

```
목적: 코나카드 결제 플랫폼과 AML 솔루션을 연계하는 인터페이스 서비스.
주요 기능:
- 결제 플랫폼-AML 호출 중계
- AML 응답 처리
도메인: AML, 결제, 외부연계
연계: AML 솔루션, 결제 플랫폼
```

**English Description**

```
Purpose: Interface service that bridges KonaCard payment platform and the AML solution.
Functions:
- Relay calls between platform and AML
- Handle AML responses
Domain: AML, payment, integration
Related: AML solution, payment platform
```

---

### AMM — App Meter Manager

**분류**: 모빌리티 > 택시 운영/자산 > 앱미터

**한글 설명**

```
목적: 앱미터 단말기를 관리하는 서비스. 개통/해지/설정 업데이트 수행.
주요 기능:
- 앱미터 단말기 개통
- 단말기 해지
- 단말기 설정 업데이트
도메인: 모빌리티, 앱미터, 단말기 관리
```

**English Description**

```
Purpose: AppMeter terminal manager; opens, cancels, and updates settings of AppMeter devices.
Functions:
- Open AppMeter terminal
- Cancel terminal
- Update terminal settings
Domain: mobility, AppMeter, terminal management
```

---

### AMP — Asp Management Portal

**분류**: 운영 > 운영 포탈 > 외부 운영 포탈

**한글 설명**

```
목적: 직불승인 고객사 운영자(웰컴저축은행)에게 제공되는 포탈 서비스.
주요 기능:
- 직불승인 고객사 운영 화면 제공
도메인: 포탈, 직불승인, 웰컴저축은행
```

**English Description**

```
Purpose: Portal service provided to direct-payment customer operators (Welcome Savings Bank).
Functions:
- Provide ops portal for direct-payment customer
Domain: portal, direct payment, Welcome Bank
```

---

### APIGW — Api Gateway

**분류**: 플랫폼 > 인프라/공통 > API 게이트웨이

**한글 설명**

```
목적: 앱(월렛) ↔ 서비스 서버 간 API 게이트웨이. 세션·라우팅·보안키보드·에러 지역화 처리.
주요 기능:
- 월렛-서비스 서버 세션 관리
- 월렛 API 호출 라우팅
- 보안키보드 처리
- API 버전 관리
- 에러 메시지 통합/지역화(국문/일문/중문/영문)
도메인: API 게이트웨이, 세션, 보안키보드, 지역화
연계: 월렛 앱, 코어 컴포넌트
```

**English Description**

```
Purpose: App(Wallet) ↔ service-server API gateway; handles session, routing, secure keyboard, error localization.
Functions:
- Manage Wallet ↔ service session
- Route Wallet API calls
- Secure keyboard handling
- API version management
- Uniform error response with localization (KR/JP/CN/EN)
Domain: API gateway, session, secure keyboard, localization
Related: Wallet app, core components
```

---

### APS — Authentication Processing Server

**분류**: 거래 > 충전 > 단말기 충전 인증

**한글 설명**

```
목적: 코나카드 충전단말기의 거래 인증을 위한 보안 컴포넌트. SAM에서 연산된 MAC 값을 검증.
주요 기능:
- Card Activation 시 MAC 검증
- 충전/충전취소 거래 시 MAC 검증
도메인: 인증, 충전단말기, SAM, MAC
연계: 충전 단말기 SAM
```

**English Description**

```
Purpose: Security component authenticating transactions from charging terminals by verifying SAM-computed MAC values.
Functions:
- Verify MAC on Card Activation
- Verify MAC on charge / charge cancel
Domain: auth, charge terminal, SAM, MAC
Related: charging terminal SAM
```

---

### ATC — Administrator To Card

**분류**: 거래 > 충전 > 어드민 충전

**한글 설명**

```
목적: 관리자(코나 재무팀) 전용으로 카드에 포인트/잔액을 Bulk 충전하는 시스템.
주요 기능:
- 카드 Bulk 포인트/잔액 충전
- 관리자 전용 충전 처리
도메인: Admin, Bulk 충전, 포인트, 잔액
연계: 재무팀, 카드
```

**English Description**

```
Purpose: Admin-only system that bulk-loads points and balances onto cards (Kona finance team).
Functions:
- Bulk-charge points and balance to cards
- Admin-only deposit
Domain: admin, bulk recharge, points, balance
Related: finance team, card
```

---

### BAS — Bconline Authentication Service

**분류**: 거래 > 결제 > 카드 인증

**한글 설명**

```
목적: BC 온라인 거래 발생 시 코나카드 내부 검증에 사용되는 Cryptogram을 생성.
주요 기능:
- BC 온라인 거래용 Cryptogram 생성
도메인: BC온라인, Cryptogram, 검증
```

**English Description**

```
Purpose: Generates cryptograms used in internal verification when BC online transactions occur.
Functions:
- Generate cryptogram for BC online tx
Domain: BC online, cryptogram, verification
```

---

### BGS — Bank Gateway Service

**분류**: 플랫폼 > 외부 연계 > 은행 게이트웨이

**한글 설명**

```
목적: 은행이 제공하는 API 기반으로 은행 업무 로직을 수행하는 게이트웨이.
주요 기능:
- 은행 API 호출/응답 처리
- 은행 업무 로직 실행
도메인: 은행, 게이트웨이, 외부연계
연계: 외부 은행 API
```

**English Description**

```
Purpose: Bank gateway component executing banking logic based on bank-provided APIs.
Functions:
- Call and handle bank APIs
- Run banking business logic
Domain: bank, gateway, integration
Related: external bank APIs
```

---

### BIG_AGENT — Big Agent

**분류**: 플랫폼 > 알림 > SMS Agent

**한글 설명**

```
목적: BGF 네트웍스 SMS Agent. SMS_core가 DB에 등록한 문자 내역을 중계서버로 전송하고 결과를 DB에 저장. 국내 문자 전송만 지원.
주요 기능:
- SMS_core가 DB에 등록한 문자 내역 조회
- BGF 중계서버로 문자 전송
- 전송 결과 DB 저장
도메인: SMS, 문자 전송, BGF, 국내 한정
연계: SMS-core, BGF Networks
```

**English Description**

```
Purpose: BGF SMS Agent; reads SMS records that SMS_core registered in the DB, sends to relay server, stores result. Domestic SMS only.
Functions:
- Read SMS records registered by SMS_core
- Send SMS to BGF relay server
- Persist transmission result to DB
Domain: SMS, message sending, BGF, domestic only
Related: SMS-core, BGF Networks
```

---

### BIZA — Business Portal A

**분류**: 정책·지원금 > 재난지원금 > 신청 사이트

**한글 설명**

```
목적: 오프라인 긴급재난지원금 신청 관리사이트. 신청자/공무원이 사용.
주요 기능:
- 오프라인 재난지원금 신청 관리
도메인: 재난지원금, 오프라인, 포탈
```

**English Description**

```
Purpose: Offline emergency disaster-relief application management site for applicants/officials.
Functions:
- Manage offline disaster-relief applications
Domain: disaster relief, offline, portal
```

---

### BIZB — Business Batch Server

**분류**: 정책·지원금 > 정책수당 > 비즈포탈 배치

**한글 설명**

```
목적: 행안부 데이터(dis)와 비즈포탈 승인 데이터를 양방향 변환·동기화하는 배치 서버.
주요 기능:
- 행안부 데이터 ↔ 비즈포탈 데이터 변환
- 코나카드 정보 결합 후 비즈포탈에 전달
- 지급 이력 행안부 반영
- 온라인/오프라인 신청 배치로 승인 데이터 생성
도메인: 행안부, 비즈포탈, 정책수당, 배치
```

**English Description**

```
Purpose: Batch server transforming and syncing Government (dis) data with Biz Portal approval data.
Functions:
- Transform Gov ↔ Biz Portal data
- Push Kona-card-merged data to Biz Portal
- Reflect payment history back to Gov data
- Generate approval data from online/offline applications
Domain: government, biz portal, subsidy, batch
```

---

### BIZCF — Business Portal Front

**분류**: 정책·지원금 > 재난지원금 > 현장지급

**한글 설명**

```
목적: 현장지급 시스템 지급관리를 위한 운영 포탈. 지급등록/관리/통계 UI 제공.
주요 기능:
- 지급 등록/관리 UI
- 지급 통계 화면
- 지자체 공무원 운영 화면
도메인: 현장지급, 정책수당, 운영포탈, 지자체
```

**English Description**

```
Purpose: Operation portal for the on-site payment system; provides payment registration/management/statistics UI.
Functions:
- Payment registration/management UI
- Statistics screen
- Used by local-gov officials
Domain: on-site payment, subsidy, ops portal, local gov
```

---

### BIZD — Business Portal D

**분류**: 가맹점 > 가맹점 관리 > 가맹점 등록 포탈

**한글 설명**

```
목적: 지역화폐 이용 가맹점 등록 사이트. 지자체 가맹점주·공무원이 사용.
주요 기능:
- 지역화폐 가맹점 등록
도메인: 지역화폐, 가맹점, 등록 포탈, 지사상
```

**English Description**

```
Purpose: Site for registering affiliated stores using local currency (used by merchants/officials).
Functions:
- Register local-currency-using affiliated stores
Domain: local currency, merchant, registration portal
```

---

### BIZS — Business Portal Api Server

**분류**: 정책·지원금 > 정책수당 > 비즈포탈 API

**한글 설명**

```
목적: BPP(business portal platform) ↔ 코나카드 코어 통신용 API 서버. 정책수당 수혜자 검증과 수당 지급 배치 수행.
주요 기능:
- BPP-코어 데이터 통신 API
- 정책수당 수혜 대상자 검증
- 카드등록/교체 시 비즈서버 동기화
- 매일 배치로 지급일 도래 수당 지급
도메인: 비즈포탈, 정책수당, 카드등록, 배치 지급
연계: BPP, 월렛 서버
```

**English Description**

```
Purpose: API server bridging Business Portal Platform (BPP) and Kona Card core; verifies subsidy beneficiaries and runs daily payout batch.
Functions:
- BPP ↔ core data API
- Verify policy-subsidy beneficiaries
- Sync biz server on card register/replace
- Daily batch pays subsidies due
Domain: biz portal, subsidy, card register, payout batch
Related: BPP, Wallet server
```

---

### BIZU — Business Portal Cu

**분류**: 정책·지원금 > 정책수당 > 비즈포탈 운영

**한글 설명**

```
목적: CU 과일 바우처 신청 사이트. 지자체 공무원이 정책수당 신청 및 통계 확인.
주요 기능:
- CU 과일 바우처 신청 처리
- 신청 통계 제공
도메인: CU 바우처, 정책수당, 지자체
```

**English Description**

```
Purpose: Site for applying for CU Fruit Voucher (used by local-gov officials for application and stats).
Functions:
- Process CU Fruit Voucher applications
- Provide application statistics
Domain: CU voucher, subsidy, local gov
```

---

### BMCS — Bank Mock Service

**분류**: 플랫폼 > OpenAPI > OpenAPI Mock

**한글 설명**

```
목적: OpenAPI 카드 테스트용 은행 계좌 관련 Mock 서비스.
주요 기능:
- 회원 계좌 생성 및 조회
- ARS 인증
- 실명 조회
- 충전 계좌 등록
- 출금 이체
도메인: OpenAPI, Mock, 은행 계좌, 테스트
연계: OpenAPI Center
```

**English Description**

```
Purpose: Bank-account Mock service for OpenAPI card testing.
Functions:
- Create and view member accounts
- ARS verification
- Real-name lookup
- Register charging account
- Withdrawal transfer
Domain: OpenAPI, mock, bank account, testing
Related: OpenAPI Center
```

---

### BPP — Business Portal Platform

**분류**: 운영 > 운영 포탈 > 비즈포탈 플랫폼

**한글 설명**

```
목적: 코나카드 B2B/B2C/B2G 포탈서비스 플랫폼. 다양한 수요부의 서비스 요구를 빠르게 대응하기 위해 개발됨.
주요 기능:
- 파트너/상품 관리
- 포인트·잔액 지급 및 회수
- 거래내역 조회
- 통계화면 제공
- 지역화폐·법인·복지카드 관리포탈 운영(RCS 포함)
도메인: 포탈 플랫폼, B2B, B2C, B2G, 지역화폐 관리, 파트너, 통계
```

**English Description**

```
Purpose: Portal service platform for KonaCard B2B/B2C/B2G services; rapidly delivers portal services per business need.
Functions:
- Manage partners and products
- Grant/recall points and balance
- View transaction history
- Provide statistics screens
- Run local-currency / corporate / welfare card admin portals (incl. RCS)
Domain: portal platform, B2B, B2C, B2G, local currency, partner, stats
```

---

### BTS — Barcode Translator Service

**분류**: 플랫폼 > 인프라/공통 > QR 생성

**한글 설명**

```
목적: QR코드 정보를 생성하는 서버 컴포넌트.
주요 기능:
- QR코드 정보 생성
도메인: QR, 바코드, 변환
```

**English Description**

```
Purpose: Server component that generates QR code information.
Functions:
- Generate QR code information
Domain: QR, barcode, translator
```

---

### BUSAN — Busan Core Service

**분류**: 회원·인증 > 회원 > 회원 이관

**한글 설명**

```
목적: 부산 동백전 정보 이관 연계 컴포넌트. 회원/잔액/이용내역 이관.
주요 기능:
- 동백전 회원 정보 이관 및 ID 매핑
- 카드 발급 시 잔액 정보 이관
- 동백전 이용내역 이관
도메인: 부산, 동백전, 회원 이관, 잔액 이관
```

**English Description**

```
Purpose: Component that takes over Busan Dongbaek-jeon data (members, balances, history).
Functions:
- Take over member info and map to new wallet ID
- Take over balances on card issuance
- Take over usage history
Domain: Busan, Dongbaek-jeon, member migration, balance migration
```

---

### CA — Certificate Authority

**분류**: 회원·인증 > 인증 > 인증서

**한글 설명**

```
목적: 인증서 발급 및 전자서명 컴포넌트. Portal에서 상품·가맹점 등록/승인 시 사용.
주요 기능:
- 인증서 발급
- 전자서명 처리
- 상품/가맹점 등록·승인 지원
도메인: 인증서, 전자서명, CA, 상품 승인
```

**English Description**

```
Purpose: Certificate-issuance and digital-signature component; used during product/merchant registration and approval.
Functions:
- Issue certificates
- Digital signature operations
- Support product/merchant approval
Domain: certificate, digital signature, CA, product approval
```

---

### CAMS — Card Application Manage System

**분류**: 카드 > 카드 관리 > 체크카드 신청

**한글 설명**

```
목적: 체크 카드 신청 및 발급을 관리.
주요 기능:
- 체크 카드 신청 처리
- 체크 카드 발급/상태 관리
도메인: 체크카드, 신청, 발급, 카드 상태
```

**English Description**

```
Purpose: Manages check-card application and issuance.
Functions:
- Process check-card application
- Manage card issuance/status
Domain: check card, application, issuance
```

---

### CARDSE — Cardse

**분류**: 카드 > 카드 관리 > 실물카드

**한글 설명**

```
목적: 실물카드(CardSE) 발급/폐기 관리 및 모바일카드(HCE)와의 연결·복제 기능 제공.
주요 기능:
- 실물카드 발급/폐기
- 실물카드 ↔ HCE 카드 연결/복제
- Batch Raw 데이터 생성 및 토큰화
- 발급 후 활성/비활성 처리
도메인: 실물카드, CardSE, HCE, 토큰화
연계: HCE, TSP
```

**English Description**

```
Purpose: Manages physical card (CardSE) issuance/destruction and links/replicates with mobile (HCE) cards.
Functions:
- Issue/destroy physical CardSE
- Link/replicate active CardSE with active HCE
- Batch raw-data generation and tokenization
- Activate/deactivate after issuance
Domain: CardSE, physical card, HCE, tokenization
Related: HCE, TSP
```

---

### CAS — Card Authentification Service

**분류**: 거래 > 결제 > 카드 인증

**한글 설명**

```
목적: 카드 인증 서비스. 간편결제·구인증·해외결제·직가맹 카드인증 제공.
주요 기능:
- 간편결제 카드 인증
- 구인증 처리
- 해외결제 인증
- 직가맹 카드 인증
도메인: 카드 인증, 간편결제, 해외결제, 직가맹
```

**English Description**

```
Purpose: Card authentication service; simple payment, legacy auth, overseas payment, direct-affiliate card auth.
Functions:
- Simple-payment card auth
- Legacy auth
- Overseas-payment auth
- Direct-affiliate card auth
Domain: card auth, simple payment, overseas, direct affiliate
```

---

### CBSS — Customer Benefit Segmentation Statics

**분류**: 운영 > 통계 > 혜택 집계

**한글 설명**

```
목적: 고객 혜택 집계 관리 컴포넌트. IAS·KPS 거래 데이터를 수집해 혜택 유형별 집계 제공.
주요 기능:
- IAS·KPS 거래 데이터 수집
- 혜택 유형별 집계 데이터 제공
도메인: 고객 혜택, 집계, 통계
연계: IAS, KPS
```

**English Description**

```
Purpose: Customer-benefit aggregation component; collects IAS/KPS tx data and provides per-benefit aggregates.
Functions:
- Collect IAS/KPS transaction data
- Provide aggregate data per benefit type
Domain: customer benefit, aggregation, stats
Related: IAS, KPS
```

---

### CDM — Card Delivery Management (System)

**분류**: 카드 > 카드 관리 > 카드 배송

**한글 설명**

```
목적: 코나카드(웰컴/정책수당 등) 배송 관리 컴포넌트. 신청 정보를 코나C공장에 전달, 완료파일로 상태/카드번호 갱신. 단, 코나샵 카드 배송과는 무관.
주요 기능:
- 회원가입 시 신청 정보 공장 전달
- 공장 완료파일 읽어 상태/카드번호 업데이트
- 배송신청 데이터 조회 API 제공
- 비용부과/재발급 카드 비용 관리
도메인: 카드 배송, 웰컴카드, 정책수당카드, 재발급, 김포공장
연계: EDM, CALL, BIZ, 코나C공장
```

**English Description**

```
Purpose: Manages KonaCard (welcome/subsidy/etc.) delivery; sends applications to Kimpo factory and updates status/PAN from completion files. Excludes Kona Shop deliveries.
Functions:
- Forward signup info to factory
- Update status/PAN from factory completion files
- Provide delivery-request inquiry API
- Manage paid-card / reissue cost
Domain: card delivery, welcome card, subsidy card, reissue, Kimpo factory
Related: EDM, CALL, BIZ, Kimpo factory
```

---

### CIMS — Card Inventory Management Service

**분류**: 카드 > 카드 관리 > 카드 재고

**한글 설명**

```
목적: E2MAX와 연동하여 카드 재고를 관리하는 서비스.
주요 기능:
- E2MAX 연동 카드 재고 관리
도메인: 카드 재고, E2MAX, 재고 관리
```

**English Description**

```
Purpose: Card-inventory management service integrated with E2MAX.
Functions:
- Manage card inventory via E2MAX integration
Domain: card inventory, E2MAX, inventory mgmt
```

---

### CISS — Card Issuance Simulator Service

**분류**: 플랫폼 > OpenAPI > OpenAPI Mock

**한글 설명**

```
목적: OpenAPI 테스트용 카드 발급 시뮬레이터 서비스.
주요 기능:
- OpenAPI용 카드 발급 시뮬레이션
도메인: OpenAPI, Mock, 카드 발급, 시뮬레이터
연계: OpenAPI Center
```

**English Description**

```
Purpose: Card-issuance simulator for OpenAPI testing.
Functions:
- Simulate card issuance for OpenAPI tests
Domain: OpenAPI, mock, card issuance, simulator
Related: OpenAPI Center
```

---

### CLMK — Nice Mock Service

**분류**: 플랫폼 > OpenAPI > OpenAPI Mock

**한글 설명**

```
목적: OpenAPI 실명 인증용 NICE Mock 서비스.
주요 기능:
- 암복호화 토큰 요청
- 실명 인증 요청
도메인: OpenAPI, Mock, 실명 인증, NICE
연계: OpenAPI Center, NICE-core
```

**English Description**

```
Purpose: NICE Mock service for OpenAPI real-name verification.
Functions:
- Request encryption/decryption token
- Request real-name verification
Domain: OpenAPI, mock, real-name verification, NICE
Related: OpenAPI Center, NICE-core
```

---

### CLR — Clearing

**분류**: 거래 > 정산 > 정산

**한글 설명**

```
목적: 코나카드 정산 컴포넌트. 거래 데이터·계약서 기준으로 수수료/대금 확정, 지급 데이터 및 근거 자료 생성. 새벽 배치로 수행.
주요 기능:
- 거래 데이터 기반 수수료/대금 확정
- 확정 대금 지급 데이터 생성
- 지급 근거 자료 생성
- 새벽 시간 배치 실행
도메인: 정산, 수수료, 지급, 배치, 새벽
연계: IAS(원장), 컨트랙트
```

**English Description**

```
Purpose: KonaCard clearing component; computes fees/payments per contract from tx data and generates payout + evidence files (run as overnight batch).
Functions:
- Confirm fees and payment amounts from tx data
- Generate payout data
- Generate supporting evidence
- Runs as off-peak batch
Domain: clearing, fee, payout, batch, overnight
Related: IAS (ledger), contracts
```

---

### CLR_KT — Clearing Kotlin

**분류**: 거래 > 정산 > 정산

**한글 설명**

```
목적: CLR을 Spring Boot 3.2.3, JDK 21, Kotlin으로 업그레이드한 신규 정산 컴포넌트. 새벽 자동 처리.
주요 기능:
- 거래 데이터 기반 수수료/대금 계산
- 지급 데이터 생성
- Spring Boot 3 / JDK 21 / Kotlin 스택
- 새벽 시간 자동 정산
도메인: 정산, Kotlin, JDK21, 신규 스택, 배치
연계: CLR(legacy)
```

**English Description**

```
Purpose: Upgraded clearing component (Spring Boot 3.2.3, JDK 21, Kotlin) replacing CLR; runs automatically overnight.
Functions:
- Calculate fees and payments from tx data
- Generate payment data
- Spring Boot 3 / JDK 21 / Kotlin stack
- Automated overnight clearing
Domain: clearing, Kotlin, JDK21, modernized, batch
Related: CLR (legacy)
```

---

### CMS — Card Management System

**분류**: 카드 > 카드 관리 > 카드 원장

**한글 설명**

```
목적: 카드 원장 관리 컴포넌트. 카드 발급용 Raw 데이터 생성, PAN/PAR 관리, 라이프사이클·기명화·소득공제 지원.
주요 기능:
- 카드 발급 Raw 데이터 생성
- PAN/PAR 생성 및 관리
- 카드 라이프사이클 관리
- 기명화 처리
- 소득공제 지원
도메인: 카드 원장, PAN, PAR, 라이프사이클, 기명화, 소득공제
```

**English Description**

```
Purpose: Card-ledger management; generates raw issuance data and manages PAN/PAR, lifecycle, name registration, tax deduction.
Functions:
- Generate raw card-issuance data
- Generate and manage PAN/PAR
- Manage full card lifecycle
- Name-registration handling
- Income-tax deduction support
Domain: card ledger, PAN, PAR, lifecycle, name registration, tax deduction
```

---

### COPS — Co Payment Service

**분류**: 거래 > 결제 > 모아서 결제

**한글 설명**

```
목적: 모아서 결제(공동 결제) 서비스. 결제참여 요청·승인/거절, 모으기/취소, 모아서 결제 처리.
주요 기능:
- 결제참여 요청 및 승인/거절
- 모으기/모으기 취소
- 모아서 결제 실행
도메인: 공동결제, 모아서 결제, 더치페이
```

**English Description**

```
Purpose: Co-payment (collect-and-pay) service; participation request/approval/reject, collect/cancel, then pay.
Functions:
- Payment participation request, approve/reject
- Collect / cancel collect
- Execute collect-and-pay
Domain: co-payment, collect-and-pay, group pay
```

---

### CPG — Credit Payment Gateway

**분류**: 거래 > 결제 > 신용카드 결제

**한글 설명**

```
목적: EZPS 카드정보를 통해 신용카드 간편결제 거래를 신용카드사로 중계하는 게이트웨이. 정산데이터 제공.
주요 기능:
- EZPS 기반 신용카드 결제 중계
- 신용카드사 거래 전송
- 정산 데이터 제공
도메인: 신용카드, 결제 게이트웨이, 정산
연계: EZPS, 신용카드사
```

**English Description**

```
Purpose: Credit-card payment gateway routing simple-payment txs to credit-card companies via EZPS; provides settlement data.
Functions:
- Relay credit-card payment using EZPS data
- Forward txs to credit-card companies
- Provide settlement data
Domain: credit card, payment gateway, settlement
Related: EZPS, credit-card companies
```

---

### CRMS — Corporation Recharge Management Service

**분류**: 거래 > 충전 > 법인 충전

**한글 설명**

```
목적: 법인 계좌 출금이체 후 카드 충전 처리 컴포넌트. 쿠콘 출금이체 + 카드 충전 API 분리 제공.
주요 기능:
- 쿠콘 법인 계좌 출금이체
- 출금이체 후 카드 충전 요청
- 출금이체 API/충전 API/통합 API 분리 제공
도메인: 법인 충전, 쿠콘, 출금이체, 잔액 충전
상태: 실제 충전 서비스는 HOLD, 출금이체 요청만 운영
```

**English Description**

```
Purpose: Corporation recharge component; performs Coocon corporate-account withdrawal then card recharge (APIs separated).
Functions:
- Coocon corporate withdrawal
- Recharge card after withdrawal
- Separate APIs: withdrawal / recharge / combined
Domain: corp recharge, Coocon, withdrawal, balance
Status: recharge currently on hold, only withdrawal in use
```

---

### CRS — Customer Reward System

**분류**: 부가서비스 > 포인트·리워드 > 리워드 정책

**한글 설명**

```
목적: 리워드 정책 등록/업데이트/삭제 관리 및 활성 리워드 조건 검사 후 실시간 리워드 지급.
주요 기능:
- 리워드 정보 등록/수정/삭제
- 활성 리워드 조건 검사
- Point/Coupon 실시간 지급
- 회원가입/카드등록/결제·충전 시점 지급
도메인: 리워드, 포인트, 쿠폰, 실시간 지급
연계: KPS, KCPS
```

**English Description**

```
Purpose: Manages reward policy registration/update/deletion and grants real-time rewards after condition checks.
Functions:
- Register/update/delete reward info
- Run condition checks for active rewards
- Grant points/coupons in real time
- Trigger on signup, card register, payment/charge
Domain: reward, point, coupon, real-time grant
Related: KPS, KCPS
```

---

### CS — Charge Service

**분류**: 거래 > 충전 > 온라인 충전

**한글 설명**

```
목적: 은행계좌·신용카드 기반 온라인 충전 컴포넌트. 외부 PG 연동, 자동 충전(월별/하한) 지원.
주요 기능:
- 계좌주 실명 조회 및 ARS 인증
- 은행 계좌 등록 및 충전
- 외부 PG사 연동 출금이체
- 월별 자동 충전 / 하한 자동 충전
도메인: 충전, 은행계좌, 신용카드, PG, 자동충전
연계: 외부 PG
```

**English Description**

```
Purpose: Online charge component using bank account or credit card; integrates with external PG and supports auto-charging (monthly / threshold).
Functions:
- Real-name lookup and ARS verification
- Register bank account and charge from it
- Withdraw via external PG company
- Monthly or threshold-based auto charge
Domain: charge, bank account, credit card, PG, auto-charge
Related: external PG
```

---

### CSG — Call Service Gateway

**분류**: 모빌리티 > 택시 운영/자산 > 콜 게이트웨이

**한글 설명**

```
목적: 지역전화콜 시스템과 코나택시(MAS) 사이의 호출 서비스 중계.
주요 기능:
- 지역전화콜 ↔ 코나택시 호출 중계
도메인: 콜, 모빌리티, 게이트웨이
연계: MAS
```

**English Description**

```
Purpose: Routes call requests between local phone-call system and Kona Taxi (MAS).
Functions:
- Relay call service between local call system and Kona Taxi
Domain: call, mobility, gateway
Related: MAS
```

---

### CUBEONE AGENT — Cubeone Agent

**분류**: 플랫폼 > 보안 > DB 암호화

**한글 설명**

```
목적: DBMS 서버에 설치되어 중요한 데이터의 암/복호 초기화를 수행하는 에이전트.
주요 기능:
- DBMS 중요 데이터 암호화/복호화 초기화
도메인: DBMS, 암호화, CubeOne, 보안 에이전트
연계: CubeOne Policy
```

**English Description**

```
Purpose: Agent installed on DBMS servers; performs encryption/decryption initialization for sensitive data.
Functions:
- Initialize encryption/decryption of sensitive DB data
Domain: DBMS, encryption, CubeOne, security agent
Related: CubeOne Policy
```

---

### CUBEONE POLICY — Cubeone Policy

**분류**: 플랫폼 > 보안 > DB 암호화

**한글 설명**

```
목적: DBMS 보안 정책을 설정·배포하는 관리 컴포넌트.
주요 기능:
- DBMS 보안 정책 설정
- 보안 정책 배포
도메인: DBMS, 보안 정책, CubeOne
연계: CubeOne Agent
```

**English Description**

```
Purpose: Management component setting up and deploying DBMS security policies.
Functions:
- Set up DBMS security policies
- Deploy security policies
Domain: DBMS, security policy, CubeOne
Related: CubeOne Agent
```

---

### CVS — Certificate Verification Service

**분류**: 회원·인증 > 인증 > 신분증 인증

**한글 설명**

```
목적: 외부 신분증 인증 모듈. 주민등록증(정부24), 운전면허증(경찰청) 인증 제공. 소득공제·충전한도 상향 시 사용.
주요 기능:
- 주민등록증 인증(정부24)
- 운전면허증 인증(경찰청)
- 소득공제/충전한도 상향 시 신분증 인증
도메인: 신분증 인증, 주민등록증, 운전면허증, 정부24, 경찰청
```

**English Description**

```
Purpose: External certificate-verification module; resident-registration (Gov24) and driver's license (Police).
Functions:
- Resident-registration verification (Gov24)
- Driver's-license verification (Police)
- Used for tax deduction / charge limit upgrade
Domain: ID verification, RRN, driver license, Gov24, Police
```

---

### DAPA — Display Advertisment Platform Api

**분류**: 운영 > 광고/추천 > 광고

**한글 설명**

```
목적: 광고 플랫폼 API 컴포넌트. 광고 기능 중 API로 제공해야 할 기능 담당.
주요 기능:
- 광고 기능용 API 제공
도메인: 광고, API, 플랫폼
연계: DAPC, DAPM
```

**English Description**

```
Purpose: Display-Advertisement Platform API; serves the API-facing parts of ad functionality.
Functions:
- Provide API endpoints for advertising functions
Domain: advertising, API, platform
Related: DAPC, DAPM
```

---

### DAPC — Display Advertisment Platform Core

**분류**: 운영 > 광고/추천 > 광고

**한글 설명**

```
목적: 광고 플랫폼 코어. DAPM에서 받은 메시지를 광고 서비스용으로 가공/저장/집계.
주요 기능:
- DAPM 메시지 수신
- 광고 데이터 가공/저장
- 광고 데이터 집계
도메인: 광고, 코어, 데이터 가공, 집계
연계: DAPM, DAPA
```

**English Description**

```
Purpose: Display-Ad Platform core; receives DAPM messages and processes/stores/aggregates them for ad services.
Functions:
- Receive messages from DAPM
- Process and store ad data
- Aggregate ad metrics
Domain: advertising, core, processing, aggregation
Related: DAPM, DAPA
```

---

### DAPM — Display Advertisment Platform Messagebroker

**분류**: 운영 > 광고/추천 > 광고

**한글 설명**

```
목적: 광고 플랫폼 메세지 브로커. 광고 서비스 최전단에서 모든 요청을 받아 정규화 후 메시지 큐로 전달.
주요 기능:
- 광고 요청 수신
- 정규화 처리
- 메시지 큐 발행
도메인: 광고, 메시지 브로커, 큐
연계: DAPC, DAPA
```

**English Description**

```
Purpose: Display-Ad Platform message broker; ingests all ad requests, normalizes, and forwards to the message queue.
Functions:
- Ingest advertising requests
- Normalize requests
- Publish to message queue
Domain: advertising, message broker, queue
Related: DAPC, DAPA
```

---

### DBMT — Database Monitoring

**분류**: 운영 > 모니터링/도구 > DB 모니터링

**한글 설명**

```
목적: 데이터베이스 모니터링 API 서버. x7/x8/x9 DB CPU 부하 상태 API 제공.
주요 기능:
- x7/x8/x9 DB CPU 부하 상태 API
도메인: DB 모니터링, CPU 부하, 운영 API
```

**English Description**

```
Purpose: Database monitoring API server; exposes DB CPU load for x7/x8/x9.
Functions:
- Provide CPU-load API for x7/x8/x9 DBs
Domain: DB monitoring, CPU load, ops API
```

---

### DCP — Digital Card Platform

**분류**: 카드 > 카드 관리 > 모바일카드

**한글 설명**

```
목적: 모바일 카드 관리 컴포넌트. 토큰/라이프사이클/암호화 키 관리.
주요 기능:
- 모바일 카드 토큰 관리
- 라이프사이클(DELETE/ACTIVE/SUSPENDED)
- 모바일 거래 암호화 키 관리
도메인: 디지털 카드, HCE, 토큰, 라이프사이클, 키 관리
```

**English Description**

```
Purpose: Manages mobile (digital) cards: tokens, lifecycle, encryption keys.
Functions:
- Manage mobile-card tokens
- Manage lifecycle (DELETE/ACTIVE/SUSPENDED)
- Manage encryption keys for mobile transactions
Domain: digital card, HCE, token, lifecycle, key management
```

---

### DDA — Display Data Api

**분류**: 카드 > 카드 조회 > 데이터 전시

**한글 설명**

```
목적: 앱 전시 데이터 API 서비스 (데이터 표시 무관).
주요 기능:
- 앱 전시 데이터 API 제공
도메인: 전시 데이터, API, 앱
```

**English Description**

```
Purpose: API service providing exhibition (display) data for the app.
Functions:
- Serve display-data API for app
Domain: display data, API, app
```

---

### DDV — Display Data Webview

**분류**: 카드 > 카드 조회 > 데이터 전시

**한글 설명**

```
목적: 앱 전시 데이터 웹뷰 서비스 (데이터 표시 무관).
주요 기능:
- 앱 전시 데이터 웹뷰 제공
도메인: 전시 데이터, 웹뷰, 앱
```

**English Description**

```
Purpose: WebView service for the app's exhibition (display) data.
Functions:
- Serve display-data WebView for app
Domain: display data, webview, app
```

---

### EAS — External Alliance Service

**분류**: 카드 > 카드 관리 > 외부 제휴 카드

**한글 설명**

```
목적: 외부 제휴 서비스 컴포넌트. KB PLCC, CU 멤버십, 상품 서비스 코드 관리.
주요 기능:
- KB PLCC 카드 처리
- CU 멤버십 처리
- 서비스 코드 관리
도메인: 외부 제휴, PLCC, KB, CU, 멤버십
```

**English Description**

```
Purpose: External-alliance service; handles KB PLCC, CU membership, product service codes.
Functions:
- KB PLCC card handling
- CU membership handling
- Service code management
Domain: external alliance, PLCC, KB, CU, membership
```

---

### ECA — Easy Card Apply

**분류**: 카드 > 카드 관리 > 카드 신청

**한글 설명**

```
목적: 웹페이지를 통해 코나카드를 신청할 수 있는 사이트.
주요 기능:
- 웹 기반 코나카드 신청 접수
도메인: 카드 신청, 웹 신청, 가입
```

**English Description**

```
Purpose: Website where users can apply for a KonaCard.
Functions:
- Accept web-based KonaCard applications
Domain: card application, web apply, signup
```

---

### EDM — External Data Manager

**분류**: 플랫폼 > 외부 연계 > 외부 제휴

**한글 설명**

```
목적: 외부 서비스 제휴사 커뮤니케이션 컴포넌트. 제휴사 카드 등록 혜택, 충전, 은행계좌-제휴사 계좌 정보 연동 등 지원.
주요 기능:
- 제휴사 정보 수집 및 부가 서비스 제공
- 제휴사 카드 등록 시 혜택 부여
- 제휴사 충전 처리
- 은행 계좌 등록 시 제휴사 계좌 정보 제공
도메인: 외부 제휴, MODU, SKT, 통합콜, 농협, 충전, 카드 등록
연계: 모두, SKT, 통합콜, 아들에날린, 농협은행
```

**English Description**

```
Purpose: External-data manager handling communication with affiliate partners; provides registration benefits, charging, bank-account info exchange.
Functions:
- Collect partner info and offer add-on services
- Grant benefits on partner card registration
- Charge via partner
- Provide partner-account info on bank registration
Domain: external alliance, MODU, SKT, Unified Call, Nonghyup, charge, registration
Related: MODU, SKT, Unified Call, Nonghyup Bank
```

---

### EGS — External Gateway System

**분류**: 플랫폼 > 인프라/공통 > API 게이트웨이

**한글 설명**

```
목적: Portal·고객센터 등 외부 컴포넌트가 코어 API와 통신할 수 있도록 하는 게이트웨이.
주요 기능:
- Portal/고객센터 → 코어 API 라우팅
- 외부 컴포넌트 인증 및 매핑
도메인: 외부 게이트웨이, Portal, 코어 API
연계: etn, itn, map, ias, apigw, cdm, cardse, cms, kps, kcs, knotify, gs, kcps, crs, cs, rs, vvan, edm, tsp, bizs, kmp
```

**English Description**

```
Purpose: Gateway letting external components (Portal, Call Center, etc.) talk to core API.
Functions:
- Route Portal/Call Center traffic to core API
- Authenticate and map external components
Domain: external gateway, portal, core API
Related: etn, itn, map, ias, apigw, cdm, cardse, cms, kps, kcs, knotify, gs, kcps, crs, cs, rs, vvan, edm, tsp, bizs, kmp
```

---

### ELASTIC — Elastic Search

**분류**: 플랫폼 > 인프라/공통 > 검색/저장소

**한글 설명**

```
목적: 연계 지자체의 충전·결제·유저정보 빅데이터 처리 및 지자체 전송 역할.
주요 기능:
- 지자체 빅데이터 처리(충전/결제/유저)
- 지자체 데이터 전송
도메인: Elastic Search, 지자체, 빅데이터, 데이터 전송
```

**English Description**

```
Purpose: Big-data processing and transmission of charge/payment/user info for partner local governments.
Functions:
- Process partner-gov big data (charge/payment/user)
- Transmit data to local governments
Domain: Elastic Search, local gov, big data, data transmission
```

---

### EMS — Echo Mileage Service

**분류**: 부가서비스 > 포인트·리워드 > 마일리지

**한글 설명**

```
목적: 인천 서구 환경 마일리지 서비스. 걷기/자전거 파트너와 연계해 마일리지 적립.
주요 기능:
- 환경 마일리지 적립
- 걷기/자전거 파트너 연계
도메인: 환경 마일리지, 인천 서구, 걷기, 자전거
```

**English Description**

```
Purpose: Eco-mileage service for Seo-gu, Incheon; grants mileage via walking/cycling partners.
Functions:
- Accumulate eco-mileage
- Integrate with walking/cycling partners
Domain: eco mileage, Seo-gu Incheon, walking, cycling
```

---

### EPMS — External Portal Data Management Service

**분류**: 플랫폼 > 외부 연계 > 외부 포탈 데이터

**한글 설명**

```
목적: 외부 지자체 포탈의 데이터를 연동하여 App 전시 데이터로 활용.
주요 기능:
- 외부 지자체 포탈 데이터 수집
- App 전시 데이터 연동
도메인: 지자체 포탈, 외부 데이터, 전시 데이터
```

**English Description**

```
Purpose: Links data from external local-government portals; the data is used as in-app exhibition data.
Functions:
- Ingest data from external local-gov portals
- Feed into app display-data pipeline
Domain: local gov portal, external data, exhibition data
```

---

### ESIGN — Esign

**분류**: 가맹점 > 가맹점 관리 > 전자계약

**한글 설명**

```
목적: 코나카드 서비스 신청을 온라인 전자계약으로 진행하는 서비스. 가맹점주 사용.
주요 기능:
- 온라인 전자계약 처리
- 가맹점주 신청 지원
도메인: 전자계약, 가맹점, 신청, ESIGN
```

**English Description**

```
Purpose: Electronic contract service for online KonaCard service application (used by merchants).
Functions:
- Online e-contract processing
- Support merchant onboarding
Domain: e-contract, merchant, application, ESIGN
```

---

### ESP — Elastic Search Platform

**분류**: 모빌리티 > 택시 거래/관제 > 택시 데이터 적재

**한글 설명**

```
목적: 엘라스틱서치 기반 택시 정보 관리 컴포넌트.
주요 기능:
- 택시 정보 색인/검색
도메인: Elastic Search, 택시, 검색
연계: MAS, ETH
```

**English Description**

```
Purpose: Elasticsearch-based taxi-information management component.
Functions:
- Index and search taxi info
Domain: Elastic Search, taxi, search
Related: MAS, ETH
```

---

### ETH — Event To Hadoop

**분류**: 모빌리티 > 택시 거래/관제 > 택시 데이터 적재

**한글 설명**

```
목적: 택시 이벤트를 Hadoop에 저장하는 컴포넌트.
주요 기능:
- 택시 이벤트 Hadoop 적재
도메인: 택시, 이벤트, Hadoop, 빅데이터
연계: MAS
```

**English Description**

```
Purpose: Stores taxi events to Hadoop.
Functions:
- Persist taxi events to Hadoop
Domain: taxi, event, Hadoop, big data
Related: MAS
```

---

### ETM — Event To Mongo

**분류**: 모빌리티 > 택시 거래/관제 > 택시 데이터 적재

**한글 설명**

```
목적: 택시 이벤트를 MongoDB에 저장하는 컴포넌트.
주요 기능:
- 택시 이벤트 MongoDB 적재
도메인: 택시, 이벤트, MongoDB
연계: MAS
```

**English Description**

```
Purpose: Stores taxi events to MongoDB.
Functions:
- Persist taxi events to MongoDB
Domain: taxi, event, MongoDB
Related: MAS
```

---

### ETMS — Entry Ticket Management System

**분류**: 부가서비스 > 포인트·리워드 > 응모권

**한글 설명**

```
목적: 응모권 발급 시스템. 이벤트 발생/응모 정책에 따라 응모권 채번 및 어드민 응모권 발급.
주요 기능:
- 이벤트 조건 만족 시 응모권 발급
- 응모정책별 중복 없는 응모권번호 채번
- 어드민용 응모권 일괄 발급
도메인: 응모권, 이벤트, 채번, Admin
```

**English Description**

```
Purpose: Entry-ticket issuance for events; assigns ticket numbers per policy and supports admin issuance.
Functions:
- Issue entry tickets when event conditions met
- Generate unique ticket numbers per policy
- Issue admin entry tickets in bulk
Domain: entry ticket, event, ticket number, admin
```

---

### EWSM — External Web Service Manager

**분류**: 회원·인증 > 인증 > ARS 본인인증

**한글 설명**

```
목적: 외부 웹 서비스 연동 컴포넌트. MG신용정보를 통한 ARS 서비스 제공.
주요 기능:
- 수당 카드 등록 ARS
- 준준회원 가입 ARS
- 카드 분실/분실 해제 ARS
- 소득공제 신청 ARS
- 카드 잔액·포인트 조회 ARS
도메인: ARS, MG신용정보, 외부 웹 서비스, 수당
연계: MG신용정보(주)
```

**English Description**

```
Purpose: External web-service manager; provides ARS service via MG Credit Info.
Functions:
- Subsidy card registration via ARS
- Semi-member signup via ARS
- Card lost / lost-release via ARS
- Tax-deduction application via ARS
- Card balance/point inquiry via ARS
Domain: ARS, MG Credit Info, external web service, subsidy
Related: MG Credit Info Inc.
```

---

### EZPS — Easy Payment Service

**분류**: 거래 > 결제 > 신용카드 결제

**한글 설명**

```
목적: 신용카드 간편 결제 관리 서비스.
주요 기능:
- 신용카드 간편결제 관리
도메인: 신용카드, 간편결제, EZPS
연계: CPG
```

**English Description**

```
Purpose: Easy/simple credit-card payment management service.
Functions:
- Manage credit-card simple-payment flow
Domain: credit card, simple payment, EZPS
Related: CPG
```

---

### FDMS — Fds Management System

**분류**: 거래 > 결제 > 사기 탐지

**한글 설명**

```
목적: 마스터카드 해외결제 FDS 검증을 위해 매입사 KB와 연동하는 컴포넌트.
주요 기능:
- 마스터카드 해외결제 FDS 연동
- KB 매입사 데이터 교환
도메인: FDS, 해외결제, 마스터카드, KB
연계: KB
```

**English Description**

```
Purpose: Component that links with KB (acquirer) to verify Mastercard overseas FDS.
Functions:
- Link Mastercard overseas FDS
- Exchange data with KB acquirer
Domain: FDS, overseas payment, Mastercard, KB
Related: KB
```

---

### FDS — Fraud Detection System

**분류**: 거래 > 결제 > 사기 탐지

**한글 설명**

```
목적: 이상금융거래 탐지(FDS) 컴포넌트. 이상탐지·정책정의·이상조치 3대 업무 수행.
주요 기능:
- 사전 정의된 정책으로 이상거래 탐지
- 이상거래 정책 정의 및 운영
- 탐지된 거래에 대한 사용자 제재(정지/해제)
도메인: FDS, 이상거래, 정책, 사기 탐지
연계: A-safe(레거시), KFDS(신규)
```

**English Description**

```
Purpose: Fraud Detection System; performs detection, policy definition, and response.
Functions:
- Detect fraud transactions per defined policy
- Define and operate fraud policies
- Sanction users (stop/resume) per accumulated info
Domain: FDS, fraud, policy, fraud detection
Related: A-safe (legacy), KFDS (new)
```

---

### FEP — Front End Point

**분류**: 거래 > 거래 인프라 > 매입사 연동

**한글 설명**

```
목적: 외부 제휴사와 TCP 방식 거래를 수용해 KONA 형식으로 변환하는 프론트엔드 포인트 컴포넌트(BC 매입사 등).
주요 기능:
- 외부 TCP 거래 수용
- KONA 플랫폼 형식으로 변환
도메인: 외부 연계, TCP, BC 매입사, 변환
연계: 외부 매입사/제휴사
```

**English Description**

```
Purpose: Front End Point that accepts external TCP-based transactions (e.g., BC acquirer) and converts them to KONA platform format.
Functions:
- Accept external TCP transactions
- Convert to KONA platform format
Domain: external integration, TCP, BC acquirer, conversion
Related: external acquirers/partners
```

---

### FPS — Fee Policy System

**분류**: 거래 > 정산 > 과금

**한글 설명**

```
목적: 서비스 이용 과금 관리 시스템.
주요 기능:
- 서비스 이용 과금 산정
- 과금 청구 관리
도메인: 과금, 정산, Fee Policy
```

**English Description**

```
Purpose: Fee policy / billing management system for service usage.
Functions:
- Compute service-usage fees
- Manage billing
Domain: fee, billing, policy
```

---

### FTM — File Transfer Management

**분류**: 플랫폼 > 인프라/공통 > 파일 전송

**한글 설명**

```
목적: 파일 전송 관리 시스템.
주요 기능:
- 파일 송수신 관리
도메인: 파일 전송, FTM
```

**English Description**

```
Purpose: File-transfer management system.
Functions:
- Manage file transfers
Domain: file transfer, FTM
```

---

### FXS — Foreign Exchange Service

**분류**: 부가서비스 > 외환 > 외환

**한글 설명**

```
목적: 외환 관리 서비스. 외화 계좌·매입/매도 내역, 실시간 환율, 평단가, 정산 관리.
주요 기능:
- 외화 계좌 및 매입/매도 내역 관리
- 실시간 환율 조회
- 보유 외화 환율 평단가 관리
- 외화 매입/매도 정산
도메인: 외환, 환율, 외화 계좌, 매입, 매도, 정산
```

**English Description**

```
Purpose: Foreign-exchange management service: foreign-currency accounts, buy/sell, real-time rates, average price, settlement.
Functions:
- Manage FX accounts and buy/sell history
- Real-time exchange-rate lookup
- Manage average FX rate of held currency
- Settle FX buy/sell
Domain: FX, exchange rate, FX account, buy, sell, settlement
```

---

### GDIS — Gyeonggido Disaster Service

**분류**: 정책·지원금 > 재난지원금 > 신청 사이트

**한글 설명**

```
목적: 경기도 재난지원금 컴포넌트.
주요 기능:
- 경기도 재난지원금 처리
도메인: 경기도, 재난지원금
```

**English Description**

```
Purpose: Gyeonggi-do disaster-relief support component.
Functions:
- Process Gyeonggi-do disaster-relief funds
Domain: Gyeonggi, disaster relief
```

---

### GS — Gift Service

**분류**: 부가서비스 > 송금·기부·선물 > 송금/선물

**한글 설명**

```
목적: 카드 선물·쿠폰 선물·송금 관리 컴포넌트. 전송 상태 관리 및 송수신자 매개.
주요 기능:
- 사용자간 카드/쿠폰 선물
- 어드민 선물 서비스
- 사용자간 송금
- 카드로 직접 송금
- 선물/송금 상태 관리
도메인: 선물, 쿠폰, 송금, 카드 선물
```

**English Description**

```
Purpose: Manages card gifts, coupon gifts, and remittance; manages transfer status and matches sender/receiver.
Functions:
- User-to-user gift service
- Admin gift service
- User-to-user remittance
- Direct remittance to card
- Status tracking for gifts/remittance
Domain: gift, coupon, remittance, card gift
```

---

### IAS — Issuer Authorization System

**분류**: 거래 > 결제 > 거래 원장

**한글 설명**

```
목적: 카드 거래 원장(승인/지불/환불) 관리 및 승인 처리. ISO8583 가공, 거래내역 관리, 정산용 데이터 생성.
주요 기능:
- 거래 원장(승인/지불/환불) 관리
- 카드 잔액 및 서비스 상태 관리
- PP를 통한 ISO8583 데이터 가공·승인 처리
- 충전/지불/환불 거래내역 관리
- 정산용 거래 데이터 생성
- 월렛/콜센터/운영 UI에 거래 데이터 제공
도메인: 거래 원장, 승인, ISO8583, 충전, 지불, 환불, 정산
연계: PP, CLR, 월렛, 콜센터, CMS(카드 원장)
```

**English Description**

```
Purpose: Issuer authorization system; manages the transaction ledger (approval/payment/refund) and processes approvals. (Card ledger lives in CMS.)
Functions:
- Manage transaction ledger (approval/payment/refund)
- Manage card balance and service state
- Approve via ISO8583 processing through PP
- Manage charge/payment/refund history
- Generate tx data for clearing
- Feed Wallet, call center, ops UI
Domain: transaction ledger, approval, ISO8583, charge, pay, refund, clearing
Related: PP, CLR, Wallet, call center, CMS (card ledger)
```

---

### IBFA — Inbound Foreiner Api

**분류**: 운영 > 외국인 > 외국인 API

**한글 설명**

```
목적: 외국인 인바운드 API. 외국인 포탈 백엔드(여행사용/내부 기능).
주요 기능:
- 외국인 인바운드 백엔드 API
도메인: 외국인, 인바운드, 여행사, API
연계: IBFP
```

**English Description**

```
Purpose: Foreign inbound API; backend for foreigner portal (travel-agency / internal use).
Functions:
- Backend API for foreign inbound services
Domain: foreigner, inbound, travel agency, API
Related: IBFP
```

---

### IBFP — Inbound Foreigner Portal

**분류**: 운영 > 외국인 > 외국인 포탈

**한글 설명**

```
목적: 외국인 인바운드 포탈. 외국인 관광객 어드민 포탈로 사용.
주요 기능:
- 외국인 관광객 어드민 화면 제공
- 여행사 운영 화면 제공
도메인: 외국인, 인바운드, 코나트래블, 관광
연계: IBFA
```

**English Description**

```
Purpose: Foreign inbound portal; admin portal for foreign tourists / travel agencies.
Functions:
- Admin screens for foreign tourists
- Travel-agency operation screens
Domain: foreigner, inbound, Kona Travel, tourism
Related: IBFA
```

---

### ICMS — Integrated Cash Management System

**분류**: 플랫폼 > 외부 연계 > CMS 전문 송수신

**한글 설명**

```
목적: CMS 전문 방식의 외부 제휴사 파일 송수신 컴포넌트. 클라이언트(송신) + 서버(수신) 구성.
주요 기능:
- 외부 제휴사 파일 송신 클라이언트
- 외부 제휴사 파일 수신 서버
- CMS 전문 송수신 관리
도메인: CMS 전문, 파일 송수신, TCP, 외부 제휴사
```

**English Description**

```
Purpose: CMS TCP file-transfer component for external partners; consists of a sending client and receiving server.
Functions:
- File-sending client to partners
- File-receiving server from partners
- Manage CMS-format transfers
Domain: CMS, file transfer, TCP, external partner
```

---

### IEPS — Integrated Execution Processing System

**분류**: 정책·지원금 > 정책수당 > 통합 집행

**한글 설명**

```
목적: 정책지원금 통합집행처리 시스템. 지자체/공무원이 사용.
주요 기능:
- 정책지원금 통합 집행 처리
도메인: 정책지원금, 통합집행, 지자체, 공무원
```

**English Description**

```
Purpose: Integrated execution processing system for policy support funds (used by local govs / officials).
Functions:
- Integrated execution of policy support funds
Domain: policy subsidy, integrated execution, local gov
```

---

### IIS — Instant Issue Service

**분류**: 카드 > 카드 관리 > 즉시 발급

**한글 설명**

```
목적: 즉시 발급 서비스.
주요 기능:
- 카드 즉시 발급 처리
도메인: 카드 발급, Instant Issue
```

**English Description**

```
Purpose: Instant card-issuance service.
Functions:
- Instant card issuance
Domain: card issuance, instant issue
```

---

### IMCS — Integrated Mobility Clearing And Settlement

**분류**: 모빌리티 > 모빌리티 정산 > 교통 정산

**한글 설명**

```
목적: 교통정산 컴포넌트(Integrated Mobility Clearing and Settlement). 신용카드사 EDI 가맹점으로 교통 PG 역할.
주요 기능:
- 거래데이터 수집
- VAN/신용카드사 매입 요청
- 정산 대금 수령 후 택시 사업자에게 정산
- Online: 신용카드사 직연동
- Offline: VAN사 연동
도메인: 교통 PG, 정산, 신용카드, VAN, 택시
연계: 신용카드사, VAN, 택시 사업자
```

**English Description**

```
Purpose: Integrated Mobility Clearing and Settlement; acts as transportation PG (EDI affiliate of credit-card companies).
Functions:
- Collect transaction data
- Request acquirer (VAN or credit-card co.)
- Receive settlement and pay taxi operators
- Online: direct credit-card-company link
- Offline: VAN link
Domain: transportation PG, settlement, credit card, VAN, taxi
Related: credit-card co., VAN, taxi operator
```

---

### IMC_AGENT — Imc Agent

**분류**: 플랫폼 > 알림 > SMS Agent

**한글 설명**

```
목적: IMC(휴머스온) SMS Agent. SMS_core가 DB에 등록한 문자 내역을 중계서버로 전송하고 결과를 DB에 저장. 국내/해외 문자 전송 지원.
주요 기능:
- SMS_core가 DB에 등록한 문자 내역 조회
- IMC 중계서버로 문자 전송
- 전송 결과 DB 저장
- 국내/해외 SMS 전송
도메인: SMS, 문자 전송, IMC, 휴머스온, 국내/해외
연계: SMS-core, IMC(휴머스온)
```

**English Description**

```
Purpose: IMC (Humuson) SMS Agent; reads SMS records that SMS_core registered, sends to relay server, stores result. Supports domestic and overseas SMS.
Functions:
- Read SMS records registered by SMS_core
- Send SMS to IMC relay server
- Persist transmission result to DB
- Domestic and overseas SMS
Domain: SMS, message sending, IMC, Humuson, domestic/overseas
Related: SMS-core, IMC (Humuson)
```

---

### ITA(TMS) — Issuer Token Adapter

**분류**: 거래 > 결제 > 토큰화

**한글 설명**

```
목적: 크립토그램 검증 및 토큰 해제 어댑터. 거래 요청 수락 후 카드 브랜드/거래모드별 검증, ATC 정책 위반 시 디지털 카드 정보 삭제 요청, TSP와 통신해 토큰 해제.
주요 기능:
- 거래 요청 수락 및 카드 브랜드/모드 결정
- 크립토그램 검증
- ATC 값 범위 정책으로 거래 검증
- 부적격 시 디지털 카드 정보 삭제 요청
- TSP 통신을 통한 토큰 해제
도메인: TMS, 크립토그램, 토큰 해제, ATC, 비정상 거래
연계: TSP, DCP, IAS
```

**English Description**

```
Purpose: Issuer Token Adapter; validates cryptograms and de-tokenizes via TSP, manages anomalous transactions.
Functions:
- Accept tx, determine card brand/mode
- Validate cryptogram
- Validate ATC value within policy range
- Request digital-card info deletion on invalid result
- De-tokenize via TSP
Domain: TMS, cryptogram, de-tokenization, ATC, fraud
Related: TSP, DCP, IAS
```

---

### KAFKA — Apache Kafka

**분류**: 플랫폼 > 인프라/공통 > 메시징

**한글 설명**

```
목적: Apache Kafka. 발행-구독 모델 기반 분산 스트리밍 플랫폼. 고부하 환경에 적합한 대용량 데이터 처리, 수평 확장, 실시간 처리, 장기 보존, 다중 소비자 동시 읽기 지원.
주요 기능:
- 고부하 환경 대용량 데이터 처리
- 수평 확장 용이
- 데이터 무결성·가용성 보장
- 실시간 데이터 처리
- 발행-구독 모델로 시스템 결합도 감소
- 디스크 저장 장기 보존
- 다중 컨슈머 동시 읽기
- 커넥터·스트림 처리 확장
도메인: Kafka, 스트리밍, pub/sub, 분산, 메시지 큐, 인프라
```

**English Description**

```
Purpose: Apache Kafka; pub/sub-based distributed streaming platform suitable for high-load, horizontally scalable, real-time, durable, multi-consumer workloads.
Functions:
- Efficient processing in high-load environments
- Easy horizontal scaling
- Data integrity and availability
- Real-time data processing
- Pub/Sub model decouples systems
- Disk persistence for long-term retention
- Multiple consumers read concurrently
- Extensible via connectors and stream processing
Domain: Kafka, streaming, pub/sub, distributed, message queue, infrastructure
```

---

### KAS — Kona Address System

**분류**: 가맹점 > 가맹점 관리 > 주소/위치

**한글 설명**

```
목적: 주소 검색 시스템. 가맹점 위경도 채번, 도로명/지번/우편번호 변환 검색.
주요 기능:
- 가맹점 데이터 임포트 시 위경도 채번
- 주소 검색(도로명↔지번, 우편번호)
도메인: 주소, 위경도, 가맹점, 도로명, 지번, 우편번호
```

**English Description**

```
Purpose: Address-search system; assigns lat/lon to merchants and converts road↔Jibun↔ZIP.
Functions:
- Assign merchant lat/lon on data import
- Address search (road↔Jibun, ZIP)
Domain: address, lat/lon, merchant, road, Jibun, ZIP
```

---

### KBC_B — Kona Business Card Batch

**분류**: 카드 > 카드 관리 > 복지카드 배치

**한글 설명**

```
목적: 복지카드 배치 서비스. 복지카드 제휴사 배치 처리(외주 개발사 UX CUBE).
주요 기능:
- 복지카드 배치 처리
도메인: 복지카드, 배치, KBC
연계: KBC_P
```

**English Description**

```
Purpose: Welfare-card batch service (developed with UX CUBE).
Functions:
- Process welfare-card batches
Domain: welfare card, batch, KBC
Related: KBC_P
```

---

### KBC_P — Kona Business Card Portal

**분류**: 운영 > 운영 포탈 > 복지카드 포탈

**한글 설명**

```
목적: 복지카드 포탈 서비스(코나비즈포탈). 복지카드 제휴사 포탈로 사용.
주요 기능:
- 복지카드 제휴사 운영 포탈
도메인: 복지카드, 포탈, 코나비즈포탈
연계: KBC_B
```

**English Description**

```
Purpose: Welfare-card portal service (KonaBiz Portal); used by welfare-card affiliates.
Functions:
- Welfare-card affiliate ops portal
Domain: welfare card, portal, KonaBiz
Related: KBC_B
```

---

### KCMW — Kona Consultant Mobile Web

**분류**: 회원·인증 > 회원 > 모집인

**한글 설명**

```
목적: 코나카드 모집인의 회원가입/결제 실적을 모바일 환경에서 월별 조회할 수 있는 컴포넌트.
주요 기능:
- 모집인 월별 실적 조회
- 회원가입 및 결제 실적 통계
도메인: 모집인, 실적, 모바일웹, KCMW
연계: KCS
```

**English Description**

```
Purpose: Mobile web for KonaCard recruiters to view monthly sign-up and payment performance.
Functions:
- Monthly recruiter performance view
- Sign-up / payment statistics
Domain: recruiter, performance, mobile web, KCMW
Related: KCS
```

---

### KCPS — Kona Coupon System

**분류**: 부가서비스 > 포인트·리워드 > 쿠폰

**한글 설명**

```
목적: KonaCard 쿠폰 관리 시스템. 외부쿠폰/내부쿠폰 발행·발행 취소를 관리. 쿠폰 정책은 KOD가 관리.
주요 기능:
- 외부/내부 쿠폰 발행
- 발행 취소 처리
- CRS/Admin/쿠폰샵 요청 처리
- KOD에서 쿠폰 정책 조회
도메인: 쿠폰, 외부쿠폰, 내부쿠폰, 발행, 취소
연계: CRS, KOD, 쿠폰샵
```

**English Description**

```
Purpose: KonaCard coupon management; issues/cancels external and internal coupons (policies stored in KOD).
Functions:
- Issue external / internal coupons
- Cancel coupon issuance
- Handle CRS/Admin/Coupon-shop requests
- Fetch coupon policy from KOD
Domain: coupon, external coupon, internal coupon, issue, cancel
Related: CRS, KOD, coupon shop
```

---

### KCS — Kona Consultant Service

**분류**: 회원·인증 > 회원 > 모집인

**한글 설명**

```
목적: 코나카드 모집인 관리 컴포넌트. 모집 실적 산정, 수수료 내역/근거 자료 생성, 수수료 지급.
주요 기능:
- 모집인 정보 관리
- 추천인 코드 기반 모집 실적 판단
- 모집 수수료 내역/근거 자료 생성
- 수수료 지급 처리
도메인: 모집인, 추천인, 수수료, 회원 유치
연계: KCMW
```

**English Description**

```
Purpose: Recruiter management component; computes recruitment performance, generates commission records/evidence, and pays commissions.
Functions:
- Manage recruiter info
- Judge performance from referrer code
- Generate commission records/evidence
- Pay commissions
Domain: recruiter, referrer, commission, member acquisition
Related: KCMW
```

---

### KDS — Kona Delivery Service

**분류**: 모빌리티 > 배달 > 배달 대행

**한글 설명**

```
목적: 외부 배달 대행 서비스 라우팅. 배달 대행사 관리 및 외부 접수 연동.
주요 기능:
- 배달 대행사 관리
- 외부 배달 대행사 접수 연동
- 가맹점 ↔ 고객 배달 주문
도메인: 배달, 외부 대행사, 라우팅
연계: LOP
```

**English Description**

```
Purpose: External delivery routing service; manages delivery agencies and integrates with external order receiving.
Functions:
- Manage delivery agencies
- Integrate external delivery agency receiving
- Route delivery from merchant to customer
Domain: delivery, external agency, routing
Related: LOP
```

---

### KFDS — Kona Fraud Detection System

**분류**: 거래 > 결제 > 사기 탐지

**한글 설명**

```
목적: A-safe를 대체하는 신규 이상금융거래 탐지(FDS) 컴포넌트. 룰 관리 및 이상거래 탐지·정보 제공.
주요 기능:
- FDS 룰 관리
- 이상거래 탐지
- 탐지 결과 정보 제공
도메인: FDS, 신규, 이상거래, 룰 관리
연계: A-safe(레거시), FDS
```

**English Description**

```
Purpose: New fraud-detection (FDS) component replacing A-safe; manages rules, detects fraud, supplies info.
Functions:
- Manage FDS rules
- Detect fraud transactions
- Provide detection info
Domain: FDS, new, fraud, rule mgmt
Related: A-safe (legacy), FDS
```

---

### KFM — Kona File Manager

**분류**: 운영 > 모니터링/도구 > 파일 도구

**한글 설명**

```
목적: 코나카드의 대용량 엑셀 파일 다운로드 컴포넌트.
주요 기능:
- 대용량 엑셀 파일 다운로드 처리
도메인: 파일, 엑셀 다운로드, KFM
```

**English Description**

```
Purpose: Component that downloads large Excel files for KonaCard.
Functions:
- Download large Excel files
Domain: file, Excel download, KFM
```

---

### KMC — Konacard Multi Crm

**분류**: 운영 > 고객센터 > 콜센터

**한글 설명**

```
목적: 코나카드 고객센터 웹/콜센터 시스템. 고객·가맹점·비회원배송 등 조회 가능.
주요 기능:
- 고객 정보 조회
- 가맹점 정보 조회
- 비회원 배송 조회
- 고객 응대 기능 제공
도메인: 고객센터, 콜센터, CRM, 가맹점 조회
```

**English Description**

```
Purpose: KonaCard customer-center web / call-center system; enables inquiries on customers, merchants, non-member deliveries.
Functions:
- Customer inquiry
- Merchant inquiry
- Non-member delivery inquiry
- Customer support features
Domain: customer center, call center, CRM, merchant inquiry
```

---

### KMS — Key Management System

**분류**: 회원·인증 > 인증 > 키 관리

**한글 설명**

```
목적: HSM 등 암호화 처리 장비를 통해 키를 안전하게 관리하는 컴포넌트.
주요 기능:
- HSM 기반 키 관리
- 암호화/복호화 처리 중계
도메인: 키 관리, HSM, 암호화
연계: HSM
```

**English Description**

```
Purpose: Key-management service using HSMs; safely stores and uses keys.
Functions:
- HSM-based key management
- Bridge encryption/decryption operations
Domain: key management, HSM, encryption
Related: HSM
```

---

### KNOTIFY — Knotify

**분류**: 플랫폼 > 알림 > 알림 코어

**한글 설명**

```
목적: 코나카드 서비스의 알림(SMS/Push/E-Mail)을 담당. API 요청을 수신해 타입별로 발송.
주요 기능:
- SMS 알림 발송
- Push 알림 발송
- E-Mail 알림 발송
- 거래내역/장애/통보 알림
도메인: 알림, SMS, Push, E-Mail, Notification
```

**English Description**

```
Purpose: Handles notifications for Kona Card services (SMS / Push / Email) via API.
Functions:
- Send SMS notifications
- Send Push notifications
- Send Email notifications
- Cover tx/incident/notice alerts
Domain: notification, SMS, Push, Email
```

---

### KNOTIFY-DMZ — Knotify Dmz

**분류**: 플랫폼 > 알림 > 푸시 라우팅

**한글 설명**

```
목적: 푸시 서비스 공급자(FCM/APN) 라우팅 컴포넌트. knotify가 보낸 푸시를 전달.
주요 기능:
- FCM 라우팅
- APN 라우팅
도메인: 푸시, FCM, APN, DMZ
연계: KNOTIFY
```

**English Description**

```
Purpose: Routes push messages to FCM/APN providers; relays pushes sent by Knotify.
Functions:
- Route to FCM (Firebase)
- Route to APN (Apple Push)
Domain: push, FCM, APN, DMZ
Related: KNOTIFY
```

---

### KOD_ETN — Kona Operation Desk External

**분류**: 운영 > 운영 포탈 > 운영 데스크

**한글 설명**

```
목적: 외부용 코나 운영 데스크. 운영 포탈(플랫폼/파트너/비즈)에 시스템 정책·운영 정보·파트너/상품 정보를 제공.
주요 기능:
- 시스템 정책·운영 정보 설정/조회
- 파트너/상품 정보 제공
- 포탈에 내부 컴포넌트 정보 조합 제공
도메인: 운영 데스크, 포탈, 시스템 정책, 파트너/상품
```

**English Description**

```
Purpose: External Kona Operation Desk; serves system policy/ops info, partner/product info to Portal (platform/partner/biz).
Functions:
- Set and query system policy / ops info
- Provide partner/product info
- Aggregate internal-component info for Portal
Domain: ops desk, portal, system policy, partner/product
```

---

### KOD_ITN — Kona Operation Desk Internal

**분류**: 운영 > 운영 포탈 > 운영 데스크

**한글 설명**

```
목적: 내부용 코나 운영 데스크. Core 컴포넌트와 Wallet App 요청에 따라 상품·가맹점·정책·할인·쿠폰·결제 우선순위·수수료·정산 정보 제공.
주요 기능:
- 상품·가맹점·플레이어 정보 제공
- 시스템 설정·각종 정책 제공
- 할인(즉시할인/포인트 적립/단골 할인) 정보
- 쿠폰 정보, 결제 우선순위
- 결제/충전/환불 사용자 수수료 계산
- 정산 관련 설정 정보 제공
도메인: 운영 데스크, 정책, 할인, 수수료, 정산 설정
연계: Core 컴포넌트, Wallet App
```

**English Description**

```
Purpose: Internal Kona Operation Desk; serves product, merchant, policy, discount, coupon, fee, settlement info to core/Wallet.
Functions:
- Provide product, merchant, player info
- Provide system config and policies
- Discount info (instant / point accrual / regulars)
- Coupon info, payment priority
- Fee calc for pay/charge/refund
- Settlement-related config
Domain: ops desk, policy, discount, fee, settlement config
Related: core components, Wallet App
```

---

### KPF — Kona Private Funding

**분류**: 부가서비스 > 송금·기부·선물 > 펀딩

**한글 설명**

```
목적: 한국 전통 계 서비스. 모바일 앱 기반 비공개 그룹 펀딩.
주요 기능:
- 펀딩용 비공개 그룹 생성
- 그룹 라운드(멤버 수만큼) 운영
- 라운드별 수령자 선정
- 수령자 외 멤버 펀딩 납부
도메인: 계, 펀딩, 그룹, 한국 전통
```

**English Description**

```
Purpose: Kona Private Funding; mobile-app version of Korean traditional 'gye'.
Functions:
- Create private funding group
- Run rounds equal to member count
- Pick recipient per round
- Non-recipient members pay funding
Domain: private funding, gye, group, traditional
```

---

### KPG — Kona Payment Gateway

**분류**: 거래 > 결제 > 신용카드 결제

**한글 설명**

```
목적: NHN KCP를 통한 신용카드 기반 선불카드 충전 서비스.
주요 기능:
- NHN KCP 연동 신용카드 결제
- 신용카드로 선불카드 충전
도메인: 신용카드, 충전, NHN KCP, 선불카드
연계: NHN KCP
```

**English Description**

```
Purpose: Prepaid-card recharge via credit card through NHN KCP.
Functions:
- Integrate NHN KCP for credit-card payment
- Recharge prepaid card via credit card
Domain: credit card, recharge, NHN KCP, prepaid
Related: NHN KCP
```

---

### KPS — Kona Point System

**분류**: 부가서비스 > 포인트·리워드 > 포인트

**한글 설명**

```
목적: 포인트(캐시백) 관리 컴포넌트. 정책 기반 적립/사용/지급/차감 및 소멸 처리.
주요 기능:
- 혜택 적립
- 포인트 사용 / 자동사용 / 자동 복합 사용
- 인센티브 적립
- 고객센터 유저 포인트 지급/차감
- 수당 지급/회수, 복지포인트 지급
- 환불 시 포인트 차감
- 포인트 이용내역 조회
- 포인트 소멸(소멸일·사용분 계산)
도메인: 포인트, 캐시백, 적립, 사용, 소멸, 수당, 복지포인트
연계: CRS, IAS
```

**English Description**

```
Purpose: Point/cashback management; supports policy-based accrual, usage, payment, deduction, and expiration.
Functions:
- Benefit accrual
- Point usage / auto-use / combined auto-use
- Incentive accrual
- Customer-center user-point grant/deduct
- Subsidy grant/recall, welfare point grant
- Point deduction on refund
- Point usage history
- Expire points (date + used calculation)
Domain: point, cashback, accrual, usage, expiration, subsidy, welfare point
Related: CRS, IAS
```

---

### KS-BATCH — Ks Data Batch Server

**분류**: 운영 > 고객센터 > 콜센터

**한글 설명**

```
목적: KS(한국고용정보)의 CTI 데이터를 KONAI DB에 적재하고 실시간 조회 API 제공하는 고객센터 모니터링 배치.
주요 기능:
- KS CTI 데이터 일부 KONAI DB 적재
- 실시간 조회 API 제공
도메인: 고객센터, CTI, 배치, 모니터링
연계: KS, KONAI DB
```

**English Description**

```
Purpose: Batch server for customer-center monitoring; loads selected KS CTI data into KONAI DB and exposes a real-time API.
Functions:
- Load selected KS CTI data into KONAI DB
- Expose real-time KS data API
Domain: customer center, CTI, batch, monitoring
Related: KS, KONAI DB
```

---

### KSTS — Kona Stamp System

**분류**: 부가서비스 > 포인트·리워드 > 스탬프

**한글 설명**

```
목적: 스탬프 시스템. 결제이력 기준 적립/취소 및 적립 이력 기준 보상/취소.
주요 기능:
- 스탬프 정책 관리
- 결제 이력에 따른 적립/취소
- 적립 이력에 따른 보상/취소
도메인: 스탬프, 정책, 보상, 결제
```

**English Description**

```
Purpose: Stamp system; manages stamp policy, accrual/cancel based on payments, reward/cancel based on accrual.
Functions:
- Manage stamp policy
- Accrue/cancel by payment history
- Reward/cancel by accrual history
Domain: stamp, policy, reward, payment
```

---

### KTC — Kona Traffic Controller

**분류**: 플랫폼 > 인프라/공통 > 트래픽 제어

**한글 설명**

```
목적: 트레이서 대기열 솔루션을 내재화한 프로젝트. 특정 Zone 진입 시 N분당 M명 접속 허용 및 대기열 순번 제공.
주요 기능:
- Zone 진입 트래픽 제어
- 대기열 순번 제공
도메인: 대기열, 트래픽 제어, Zone, 트레이서
연계: KTCA
```

**English Description**

```
Purpose: Internalized tracer-queue solution project; admits M users per N min into a Zone and shows queue position.
Functions:
- Throttle traffic into Zones
- Provide queue position
Domain: queue, traffic control, zone, tracer
Related: KTCA
```

---

### KTCA — Kona Traffic Controller Api Server

**분류**: 플랫폼 > 인프라/공통 > 트래픽 제어

**한글 설명**

```
목적: KTC의 API 서버. Zone 정책 반영 및 실시간 Zone/대기열 시각화 데이터 제공.
주요 기능:
- Zone 정책 반영(N분당 M명)
- 실시간 Zone/대기열 데이터 제공
도메인: 대기열, API, 정책, Zone
연계: KTC
```

**English Description**

```
Purpose: API server for KTC; applies Zone policy and provides real-time Zone/queue visualization data.
Functions:
- Apply Zone policy (M per N min)
- Provide real-time Zone/queue data
Domain: queue, API, policy, zone
Related: KTC
```

---

### LBMS — Location Base Merchant Service

**분류**: 가맹점 > 가맹점 관리 > 가맹점 정보

**한글 설명**

```
목적: 위치 기반 가맹점 서비스. Elasticsearch에 가맹점 정보를 관리·조회.
주요 기능:
- 가맹점 정보 Elasticsearch 색인
- 위치 기반 가맹점 조회
도메인: 위치 기반, 가맹점, Elasticsearch
연계: Elasticsearch
```

**English Description**

```
Purpose: Location-based merchant service; manages and queries merchant info via Elasticsearch.
Functions:
- Index merchant info into Elasticsearch
- Location-based merchant query
Domain: location-based, merchant, Elasticsearch
Related: Elasticsearch
```

---

### LOP — Local Order Platform

**분류**: 모빌리티 > 배달 > 배달 코어

**한글 설명**

```
목적: 배달 서비스 컴포넌트. 배달 가맹점·메뉴·정책 관리 및 배달 결제 기능 제공.
주요 기능:
- 배달 가맹점(PLACE) 관리
- 메뉴 및 정책 관리
- 배달 결제 기능 제공
도메인: 배달, 가맹점, 메뉴, 결제
연계: LOP_EXT, LOP_DTS, LOP_RDS
```

**English Description**

```
Purpose: Delivery service component; manages delivery merchants, menus, policies, and provides payment.
Functions:
- Manage PLACE (delivery merchant)
- Manage menu and policy
- Provide payment functionality
Domain: delivery, merchant, menu, payment
Related: LOP_EXT, LOP_DTS, LOP_RDS
```

---

### LOP_DTS — Local Order Platform Data Transfer Service

**분류**: 모빌리티 > 배달 > 배달 데이터

**한글 설명**

```
목적: 배달 서비스 데이터 관리 컴포넌트.
주요 기능:
- 배달 데이터 관리/이관
도메인: 배달, 데이터 관리, DTS
연계: LOP
```

**English Description**

```
Purpose: Local Order Platform data-transfer service; manages delivery data.
Functions:
- Manage / transfer delivery data
Domain: delivery, data transfer, DTS
Related: LOP
```

---

### LOP_EXT — Local Order Platform Externel

**분류**: 모빌리티 > 배달 > 배달 외부 연동

**한글 설명**

```
목적: 배달 서비스 외부 연동 컴포넌트(재사용 용기 등).
주요 기능:
- 외부 시스템 연동(재사용 용기 등)
도메인: 배달, 외부 연동, 재사용 용기
연계: LOP
```

**English Description**

```
Purpose: Local Order Platform external-integration component (e.g., reusable containers).
Functions:
- External integration (e.g., reusable containers)
Domain: delivery, external integration, reusable container
Related: LOP
```

---

### LOP_RDS — Local Order Platform Realtime Dispatcher Service

**분류**: 모빌리티 > 배달 > 배달 실시간

**한글 설명**

```
목적: LOP 실시간 폴링 서비스(Realtime Dispatcher).
주요 기능:
- LOP 실시간 폴링/디스패치
도메인: 배달, 실시간, 폴링, 디스패치
연계: LOP
```

**English Description**

```
Purpose: Local Order Platform realtime polling/dispatch service.
Functions:
- Realtime LOP polling/dispatch
Domain: delivery, realtime, polling, dispatch
Related: LOP
```

---

### LSS — Luckyloco Support Service

**분류**: 플랫폼 > 외부 연계 > 외부 제휴

**한글 설명**

```
목적: 코나카드 플랫폼과 럭키로코 서비스 연계 지원 컴포넌트.
주요 기능:
- 럭키로코 연계 지원
도메인: 럭키로코, 외부 연계, 지원
연계: 럭키로코
```

**English Description**

```
Purpose: Support component bridging KonaCard platform and Luckyloco service.
Functions:
- Bridge with Luckyloco service
Domain: Luckyloco, integration, support
Related: Luckyloco
```

---

### MAP — Mobile Application Platform

**분류**: 회원·인증 > 회원 > 회원 관리

**한글 설명**

```
목적: 회원/약관/프로모션/추천인 관리 플랫폼. Wallet 인증, 디바이스, 등급(준준/준/정회원) 관리.
주요 기능:
- 회원 가입/일시중지/탈퇴 등 라이프사이클 관리
- 블랙리스트 관리
- Wallet 인증(Token, Password)
- Device 정보 관리
- 회원 등급(준준/준/정) 관리
- ASP별 약관 관리·동의 여부 관리
- 프로모션 코드 관리
- 추천인 코드/추천 정보 관리
도메인: 회원, 약관, 프로모션, 추천인, 인증, 디바이스, 등급
```

**English Description**

```
Purpose: Mobile Application Platform managing members, terms, promotions, recommenders; handles Wallet auth, device, member tiers.
Functions:
- Member lifecycle: join, suspend, withdraw
- Black-list management
- Wallet auth (token, password)
- Device info management
- Member-tier management (junior/semi/full)
- Per-ASP terms management and agreement
- Promotion code management
- Recommender code / referral info management
Domain: member, terms, promotion, recommender, auth, device, tier
```

---

### MAS — Mobility Application Service

**분류**: 모빌리티 > 택시 거래/관제 > 택시 코어

**한글 설명**

```
목적: 코나 모빌리티(택시) 컴포넌트.
주요 기능:
- 모빌리티/택시 서비스 제공
도메인: 모빌리티, 택시
연계: MAS-S, MAS-B, MAS-J
```

**English Description**

```
Purpose: Mobility application service (taxi) component.
Functions:
- Provide mobility/taxi service
Domain: mobility, taxi
Related: MAS-S, MAS-B, MAS-J
```

---

### MAS-B — Mobility Application Service Batch

**분류**: 모빌리티 > 택시 거래/관제 > 택시 통계/배치

**한글 설명**

```
목적: 모빌리티 통계 배치. 모빌리티 포탈에 택시 통계 API 제공, IAS 거래 데이터·CLR 정산 데이터 적재.
주요 기능:
- 택시 통계 데이터 조회 API
- IAS 실시간 거래 데이터 수신/적재
- CLR 정산 데이터 수신/적재
도메인: 모빌리티, 통계, 배치, 택시
연계: MAS, IAS, CLR
```

**English Description**

```
Purpose: Mobility statistics batch; serves taxi-stats API to Mobility portal and ingests IAS tx and CLR settlement.
Functions:
- Taxi-stats inquiry API
- Receive and store IAS realtime tx
- Receive and store CLR settlement
Domain: mobility, stats, batch, taxi
Related: MAS, IAS, CLR
```

---

### MAS-J — Mobility Application Service Job

**분류**: 모빌리티 > 택시 거래/관제 > 택시 통계/배치

**한글 설명**

```
목적: 모빌리티 통계/정산 배치 작업.
주요 기능:
- 모빌리티 통계/정산 배치 수행
도메인: 모빌리티, 배치, 잡
연계: MAS, MAS-B
```

**English Description**

```
Purpose: Mobility job runner; runs batch jobs for mobility stats/settlement.
Functions:
- Run mobility stats/settlement batch jobs
Domain: mobility, batch, job
Related: MAS, MAS-B
```

---

### MAS-S — Mobility Application Service Service

**분류**: 모빌리티 > 택시 거래/관제 > 택시 관제

**한글 설명**

```
목적: 모빌리티 실시간 관제. 실시간 택시 위치 트래킹 및 호출 현황 관제.
주요 기능:
- 실시간 택시 위치 Tracking
- 실시간 택시 Call 호출 현황 관제
도메인: 모빌리티, 관제, 실시간, 택시
연계: MAS, RDS
```

**English Description**

```
Purpose: Mobility realtime control; tracks taxi positions and call status in real time.
Functions:
- Realtime taxi-position tracking
- Realtime taxi-call status control
Domain: mobility, control, realtime, taxi
Related: MAS, RDS
```

---

### MASI — Mobility Application Service Interface

**분류**: 모빌리티 > 택시 거래/관제 > 택시 데이터 조회

**한글 설명**

```
목적: 모빌리티 택시 데이터 조회(Read 전용) 서비스. 포탈에서 사용.
주요 기능:
- 포탈용 모빌리티 데이터 Read API
도메인: 모빌리티, Read 전용, 인터페이스
연계: MASM, MASP
```

**English Description**

```
Purpose: Mobility taxi data inquiry service (read-only); used by portal.
Functions:
- Read-only data API for portal (masm, masp, ...)
Domain: mobility, read-only, interface
Related: MASM, MASP
```

---

### MASM — Mobility Application Service Management Portal

**분류**: 모빌리티 > 택시 운영/자산 > 모빌리티 포탈

**한글 설명**

```
목적: 코나 모빌리티 관리자 포탈.
주요 기능:
- 모빌리티 관리 포탈 화면 제공
도메인: 모빌리티, 관리자, 포탈
```

**English Description**

```
Purpose: Mobility management portal.
Functions:
- Provide mobility management portal screens
Domain: mobility, admin, portal
```

---

### MASP — Mobility Application Service Partner Portal

**분류**: 모빌리티 > 택시 운영/자산 > 모빌리티 포탈

**한글 설명**

```
목적: 코나 모빌리티 비지니스 파트너 포탈.
주요 기능:
- 모빌리티 파트너 포탈 화면 제공
도메인: 모빌리티, 파트너, 포탈
```

**English Description**

```
Purpose: Mobility business partner portal.
Functions:
- Provide mobility partner portal screens
Domain: mobility, partner, portal
```

---

### MASV — Mobility Application Service View Api

**분류**: 모빌리티 > 택시 거래/관제 > 택시 통계 API

**한글 설명**

```
목적: 코나 모빌리티 전시 API 서비스.
주요 기능:
- 모빌리티 전시 API 제공
도메인: 모빌리티, 전시, API
```

**English Description**

```
Purpose: Mobility view (display) API service.
Functions:
- Provide mobility display API
Domain: mobility, display, API
```

---

### MAS_VOP — Mobility Application Service Voucher Portal

**분류**: 모빌리티 > 모빌리티 바우처 > 김포 마마콜

**한글 설명**

```
목적: 코나모빌리티 바우처 관리 포탈(김포 마마콜).
주요 기능:
- 바우처 관리 포탈 제공(김포)
도메인: 모빌리티, 바우처, 김포, MamaCall
```

**English Description**

```
Purpose: Mobility Voucher management Portal (Kimpo / MamaCall).
Functions:
- Voucher management portal (Kimpo)
Domain: mobility, voucher, Kimpo, MamaCall
```

---

### MAS_VOS — Mobility Application Service Voucher Service Api

**분류**: 모빌리티 > 모빌리티 바우처 > 김포 마마콜

**한글 설명**

```
목적: 코나모빌리티 바우처 서비스 API(김포).
주요 기능:
- 바우처 서비스 API 제공(김포)
도메인: 모빌리티, 바우처, API, MamaCall
```

**English Description**

```
Purpose: Mobility Voucher Service API (Kimpo / MamaCall).
Functions:
- Voucher service API (Kimpo)
Domain: mobility, voucher, API, MamaCall
```

---

### MAS_VOV — Mobility Application Service Voucher View

**분류**: 모빌리티 > 모빌리티 바우처 > 김포 마마콜

**한글 설명**

```
목적: 코나모빌리티 바우처 전시(김포).
주요 기능:
- 바우처 전시 화면 제공(김포)
도메인: 모빌리티, 바우처, 전시, MamaCall
```

**English Description**

```
Purpose: Mobility Voucher View (Kimpo / MamaCall).
Functions:
- Voucher display (Kimpo)
Domain: mobility, voucher, view, MamaCall
```

---

### MDPS — Mobility Data Purge Service

**분류**: 모빌리티 > 택시 운영/자산 > 데이터 정리

**한글 설명**

```
목적: 모빌리티 데이터 삭제 서비스. ISMS-P 관련 데이터 삭제 및 익명화.
주요 기능:
- 모빌리티 데이터 삭제
- 데이터 익명화
도메인: ISMS-P, 데이터 삭제, 익명화, 모빌리티
```

**English Description**

```
Purpose: Mobility data-purge service; data deletion and anonymization for ISMS-P.
Functions:
- Delete mobility data
- Anonymize data
Domain: ISMS-P, data purge, anonymization, mobility
```

---

### MING — Mobileweb Into Native Group

**분류**: 거래 > 결제 > QR 결제

**한글 설명**

```
목적: 앱에서 QR을 표시하기 위한 웹 컴포넌트.
주요 기능:
- 앱 QR 표시용 웹 컴포넌트
도메인: QR, 웹뷰, 앱
```

**English Description**

```
Purpose: Mobile-web component used to render QR codes inside the app.
Functions:
- Render QR display in the app
Domain: QR, webview, app
```

---

### MIS — Mobility Integration Service

**분류**: 모빌리티 > 택시 운영/자산 > 외부 연계

**한글 설명**

```
목적: 모빌리티 연동 서비스. 코나모빌리티-제휴사 데이터 연동 지원.
주요 기능:
- 코나모빌리티-제휴사 데이터 연동
도메인: 모빌리티, 외부 연계, 제휴사
연계: 제휴사
```

**English Description**

```
Purpose: Mobility integration service; supports data integration between Kona Mobility and partners.
Functions:
- Bridge Kona Mobility ↔ partner data
Domain: mobility, integration, partner
Related: external partners
```

---

### MLS — Mileage Service

**분류**: 부가서비스 > 포인트·리워드 > 마일리지

**한글 설명**

```
목적: 마일리지 서비스. 적립/사용/취소/만료 기능 제공.
주요 기능:
- 마일리지 적립
- 마일리지 사용
- 마일리지 취소
- 마일리지 만료
도메인: 마일리지, 적립, 사용, 취소, 만료
```

**English Description**

```
Purpose: Mileage service; accrue, use, cancel, expire.
Functions:
- Accumulate mileage
- Use mileage
- Cancel mileage
- Expire mileage
Domain: mileage, accrue, use, cancel, expire
```

---

### MONGO — Mongo Db

**분류**: 플랫폼 > 인프라/공통 > 검색/저장소

**한글 설명**

```
목적: MongoDB. 다양한 형태의 데이터를 쉽게 저장·관리하는 NoSQL 데이터베이스. 대량 처리·수평 확장·복잡한 검색/분석/집계 지원.
주요 기능:
- 다양한 데이터 형태 저장/관리
- 대량 데이터 처리 및 수평 확장
- 복잡한 검색·분석·집계
- 다양한 언어 지원
도메인: MongoDB, NoSQL, 데이터베이스, 인프라
```

**English Description**

```
Purpose: MongoDB; NoSQL database easily storing/managing diverse data; suited for high-volume, horizontally scalable, complex query/analytics workloads.
Functions:
- Store and manage diverse data forms
- High-volume processing with horizontal scalability
- Complex search, analytics, aggregation
- Multi-language SDK support
Domain: MongoDB, NoSQL, database, infrastructure
```

---

### MONIS — Monitoring Interface Service

**분류**: 모빌리티 > 택시 거래/관제 > 택시 관제

**한글 설명**

```
목적: 관제(FMS) ↔ 택시 호출 시스템 연동 인터페이스.
주요 기능:
- 관제-택시호출 데이터 연동
도메인: 모빌리티, 관제, FMS, 인터페이스
연계: MAS
```

**English Description**

```
Purpose: Interface component between taxi system and FMS (fleet monitoring).
Functions:
- Bridge FMS and taxi-call data
Domain: mobility, control, FMS, interface
Related: MAS
```

---

### MOSP — Mobility Ota Service Portal

**분류**: 모빌리티 > 택시 운영/자산 > 모빌리티 OTA

**한글 설명**

```
목적: 모빌리티 OTA 서비스 포탈. 앱미터 OTA 관리 포탈.
주요 기능:
- 앱미터 OTA 관리 포탈
도메인: 모빌리티, OTA, 앱미터, 포탈
연계: AMM
```

**English Description**

```
Purpose: Mobility OTA service portal; AppMeter OTA management portal.
Functions:
- AppMeter OTA management portal
Domain: mobility, OTA, AppMeter, portal
Related: AMM
```

---

### MPT — Merchant Portal Two

**분류**: 가맹점 > 가맹점 포탈 > 가맹점 포탈

**한글 설명**

```
목적: KMP의 후속 가맹점주 전용 포탈. 거래내역/통계 조회, 거래 취소, 가맹점 소개 정보 관리.
주요 기능:
- 가맹점 거래내역/통계 조회
- 거래 취소
- 가맹점 소개 정보 입력/수정
도메인: 가맹점 포탈, 거래내역, 통계, 취소
연계: KMP(레거시)
```

**English Description**

```
Purpose: Successor merchant portal to KMP; merchants view tx history/stats and manage cancellations and intro info.
Functions:
- View merchant tx history/stats
- Cancel transactions
- Edit merchant intro info
Domain: merchant portal, tx history, stats, cancellation
Related: KMP (legacy)
```

---

### MSMA — Mobility Supply Chain Management Api Service

**분류**: 모빌리티 > 택시 운영/자산 > 모빌리티 자산

**한글 설명**

```
목적: 모빌리티 자산 관리 시스템 API 서비스.
주요 기능:
- 모빌리티 자산 관리 API
도메인: 모빌리티, 자산 관리, SCM, API
```

**English Description**

```
Purpose: Mobility supply-chain management API service.
Functions:
- Mobility supply-chain (asset) management API
Domain: mobility, asset management, SCM, API
```

---

### MSMW — Mobility Supply Chain Management Web

**분류**: 모빌리티 > 택시 운영/자산 > 모빌리티 자산

**한글 설명**

```
목적: 모빌리티 자산 관리 시스템 포탈(웹).
주요 기능:
- 모빌리티 자산 관리 포탈 화면
도메인: 모빌리티, 자산 관리, SCM, 포탈
```

**English Description**

```
Purpose: Mobility supply-chain management web portal.
Functions:
- Mobility asset-management portal screens
Domain: mobility, asset management, SCM, portal
```

---

### MYDG — My Data Gateway

**분류**: 운영 > 마이데이터 > 마이데이터

**한글 설명**

```
목적: 마이데이터 정보제공 서비스용 Gateway 컴포넌트.
주요 기능:
- 마이데이터 외부 연동 게이트웨이
도메인: 마이데이터, Gateway, 외부 연동
연계: MYDS
```

**English Description**

```
Purpose: Gateway component for the MyData information-provision service.
Functions:
- MyData gateway for external requests
Domain: MyData, gateway, external
Related: MYDS
```

---

### MYDS — My Data Service

**분류**: 운영 > 마이데이터 > 마이데이터

**한글 설명**

```
목적: 마이데이터 정보제공자 컴포넌트.
주요 기능:
- 마이데이터 정보 제공
도메인: 마이데이터, 정보제공자
연계: MYDG
```

**English Description**

```
Purpose: MyData information-provider component.
Functions:
- Provide MyData information
Domain: MyData, info provider
Related: MYDG
```

---

### NCS — Name Check Service

**분류**: 회원·인증 > 인증 > 본인인증

**한글 설명**

```
목적: KG이니시스 통합인증 연동 컴포넌트. APP에서 KG이니시스 통합인증 서비스를 사용하기 위한 컴포넌트.
주요 기능:
- KG이니시스 통합인증 연동
도메인: 통합 인증, KG이니시스, APP
연계: KG이니시스
```

**English Description**

```
Purpose: Name Check Service; component to integrate KG Inicis's unified authentication service from the APP.
Functions:
- Integrate KG Inicis unified-auth service
Domain: unified auth, KG Inicis, APP
Related: KG Inicis
```

---

### NICE-CORE — Nice Core

**분류**: 회원·인증 > 인증 > 본인인증

**한글 설명**

```
목적: NICE(KG Mobiliance 연동) 본인인증 서비스. 기기변경/실명/유저정보 변경/비밀번호/유저ID 확인 등에서 사용.
주요 기능:
- KG Mobiliance 연동 본인인증
- 기기변경/실명/유저정보 변경/비밀번호/유저ID 확인 본인인증
도메인: 본인인증, NICE, KG Mobiliance, 기기변경
연계: KG Mobiliance, CLMK
```

**English Description**

```
Purpose: NICE-core identity-verification service (linked with KG Mobiliance); used for device change, real-name, user-info/password/user-ID change.
Functions:
- Identity verification via KG Mobiliance
- Verification for device change, real-name, profile/password/user-ID change
Domain: identity verification, NICE, KG Mobiliance, device change
Related: KG Mobiliance, CLMK
```

---

### OAGW — Open Api Admin Panel Gateway

**분류**: 플랫폼 > OpenAPI > OpenAPI 게이트웨이

**한글 설명**

```
목적: OpenAPI Admin Panel Gateway. OpenAPI Admin Portal의 호출을 라우팅하는 게이트웨이.
주요 기능:
- OpenAPI Admin Portal 호출 라우팅
도메인: OpenAPI, Admin, 게이트웨이, 라우팅
연계: OCAP
```

**English Description**

```
Purpose: Gateway component routing calls from the OpenAPI Admin Portal.
Functions:
- Route calls from OpenAPI Admin Portal
Domain: OpenAPI, admin, gateway, routing
Related: OCAP
```

---

### OASG — Open Api Service Gateway

**분류**: 플랫폼 > OpenAPI > OpenAPI 게이트웨이

**한글 설명**

```
목적: Open API 게이트웨이.
주요 기능:
- OpenAPI 요청 게이트웨이
도메인: OpenAPI, 게이트웨이
```

**English Description**

```
Purpose: Gateway for Open API.
Functions:
- Gateway for OpenAPI requests
Domain: OpenAPI, gateway
```

---

### OASL — Open Api Service Layer

**분류**: 플랫폼 > OpenAPI > OpenAPI 외부 연동

**한글 설명**

```
목적: No HCE 기반 오픈 API 서비스 레이어. Kona Health, JADU, PINO 등.
주요 기능:
- Kona Health 연동
- JADU/PINO 등 No-HCE 서비스 처리
도메인: OpenAPI, No HCE, Kona Health, JADU, PINO
```

**English Description**

```
Purpose: Open API service layer for non-HCE services (Kona Health, JADU, PINO, ...).
Functions:
- Bridge Kona Health
- Handle non-HCE services like JADU, PINO
Domain: OpenAPI, No HCE, Kona Health, JADU, PINO
```

---

### OASP — Open Api Service Portal

**분류**: 플랫폼 > OpenAPI > OpenAPI 포탈

**한글 설명**

```
목적: 오픈 API 설정 포탈.
주요 기능:
- OpenAPI 설정/관리 포탈
도메인: OpenAPI, 포탈, 설정
```

**English Description**

```
Purpose: Portal for Kona Open API configuration.
Functions:
- OpenAPI configuration/management portal
Domain: OpenAPI, portal, configuration
```

---

### OASR — Open Api Service Route & Data Remapping Service

**분류**: 플랫폼 > OpenAPI > OpenAPI 라우팅

**한글 설명**

```
목적: Open API 서비스 라우팅 및 데이터 ReMapping. 웰컴/애큐온저축은행, 레몬트리, 코리엠소프트 등.
주요 기능:
- 요청 라우팅 + 데이터 재매핑
- 웰컴저축은행/애큐온저축은행/레몬트리/코리엠소프트 연동
도메인: OpenAPI, 라우팅, ReMapping, 외부 연동
연계: 웰컴저축은행, 애큐온저축은행, 레몬트리, 코리엠소프트
```

**English Description**

```
Purpose: Open API service route + data re-mapping; integrates with Welcome Bank, Acuon Bank, Lemontree, KORIEMSOFT.
Functions:
- Route requests + remap data
- Integrate with Welcome/Acuon/Lemontree/KORIEMSOFT
Domain: OpenAPI, routing, remapping, external
Related: Welcome, Acuon, Lemontree, KORIEMSOFT
```

---

### OCAP — Open Api Center Admin Portal

**분류**: 플랫폼 > OpenAPI > OpenAPI 포탈

**한글 설명**

```
목적: OpenAPI Center Admin Portal. 개발자 센터 관리자 UI. API 스펙 설정, 프로젝트/승인/사용자 관리.
주요 기능:
- API 스펙 설정
- 프로젝트 관리
- 승인 관리
- 사용자 관리
도메인: OpenAPI, Admin Portal, 관리자 UI
연계: OAGW, OCMS
```

**English Description**

```
Purpose: OpenAPI Center Admin Portal; developer-center admin UI for API spec, project, approval, user management.
Functions:
- API specification configuration
- Project management
- Approval management
- User management
Domain: OpenAPI, admin portal, admin UI
Related: OAGW, OCMS
```

---

### OCCMS — Open Api Center Content Management System

**분류**: 플랫폼 > OpenAPI > OpenAPI 콘텐츠

**한글 설명**

```
목적: OpenAPI Center Site의 콘텐츠 관리 시스템.
주요 기능:
- OpenAPI Center Site 콘텐츠 관리
도메인: OpenAPI, CMS, 콘텐츠 관리
연계: OCS
```

**English Description**

```
Purpose: Content Management System for OpenAPI Center Site.
Functions:
- Manage content for OpenAPI Center Site
Domain: OpenAPI, CMS, content management
Related: OCS
```

---

### OCDPS — Open Api Center Data Processor Service

**분류**: 플랫폼 > OpenAPI > OpenAPI 데이터

**한글 설명**

```
목적: OpenAPI Center 데이터 프로세서. 웹 크롤링, 데이터 스크래핑, Elasticsearch 적재.
주요 기능:
- 웹 크롤링
- 데이터 스크래핑
- Elasticsearch 적재
도메인: OpenAPI, 크롤링, 스크래핑, Elasticsearch
연계: ES, OCSE
```

**English Description**

```
Purpose: OpenAPI Center data processor; web crawling, scraping, and storing data into Elasticsearch.
Functions:
- Web crawling
- Data scraping
- Store data in Elasticsearch
Domain: OpenAPI, crawling, scraping, Elasticsearch
Related: ES, OCSE
```

---

### OCGW — Open Api Center Gateway

**분류**: 플랫폼 > OpenAPI > OpenAPI 게이트웨이

**한글 설명**

```
목적: OpenAPI Center Site의 호출을 라우팅하는 게이트웨이.
주요 기능:
- OpenAPI Center Site 호출 라우팅
도메인: OpenAPI, Center, 게이트웨이, 라우팅
연계: OCS
```

**English Description**

```
Purpose: Gateway component routing calls from the OpenAPI Center Site.
Functions:
- Route calls from OpenAPI Center Site
Domain: OpenAPI, center, gateway, routing
Related: OCS
```

---

### OCIS — Open Api Center Inquiry Service

**분류**: 플랫폼 > OpenAPI > OpenAPI 조회

**한글 설명**

```
목적: OpenAPI Center Inquiry Service. 조회·정책 검사·API 집계.
주요 기능:
- 조회 처리
- 정책 검사
- API 집계(aggregator)
도메인: OpenAPI, 조회, 정책, 집계
```

**English Description**

```
Purpose: OpenAPI Center Inquiry Service; inquiry, policy checking, API aggregator.
Functions:
- Handle inquiries
- Policy checking
- API aggregator
Domain: OpenAPI, inquiry, policy, aggregator
```

---

### OCMS — Open Api Center Management System

**분류**: 플랫폼 > OpenAPI > OpenAPI 운영

**한글 설명**

```
목적: OpenAPI Center 관리 시스템. 포탈 백엔드, 사용자/관리자/메뉴 권한, 승인, FAQ/공지/배너, UI 콘텐츠 설정.
주요 기능:
- 포탈 백엔드
- 공용/관리자 사용자 관리
- 메뉴 권한 및 역할 관리
- 승인 관리
- FAQ·공지·배너 관리
- UI 콘텐츠 설정
도메인: OpenAPI, 관리 시스템, 권한, 승인, 콘텐츠
```

**English Description**

```
Purpose: OpenAPI Center management system; portal backend covering user/admin, menu permissions, approval, FAQ/notice/banner, UI content.
Functions:
- Portal backend
- Public/admin user management
- Menu permissions and role management
- Approval management
- FAQ, notice, banner management
- UI content configuration
Domain: OpenAPI, management system, permission, approval, content
```

---

### OCPM — Open Api Center Project Management

**분류**: 플랫폼 > OpenAPI > OpenAPI 운영

**한글 설명**

```
목적: OpenAPI Center 프로젝트 관리. 프로젝트 CRUD, 자격증명, API 스펙, UAT, SandBox 테스트, 유즈케이스/카테고리 관리.
주요 기능:
- 프로젝트 CRUD
- 프로젝트 자격증명 관리
- API 스펙 관리
- UAT 관리
- SandBox 테스트 관리
- 유즈케이스/API 카테고리 관리
도메인: OpenAPI, 프로젝트 관리, UAT, SandBox
연계: OCAP, OINS
```

**English Description**

```
Purpose: OpenAPI Center project management; project CRUD, credentials, API spec, UAT, SandBox testing, usecase/category.
Functions:
- Project CRUD
- Project credential management
- API specification management
- UAT management
- SandBox testing management
- Usecase / API category management
Domain: OpenAPI, project mgmt, UAT, SandBox
Related: OCAP, OINS
```

---

### OCS — Open Api Center Site

**분류**: 플랫폼 > OpenAPI > OpenAPI 포탈

**한글 설명**

```
목적: OpenAPI Center 사이트(개발자 센터 UI). 유즈케이스/기능/API 관리, 사용자 온보딩, SandBox 테스트, 프로젝트 관리, UAT.
주요 기능:
- 유즈케이스/기능/API 관리 UI
- 사용자 온보딩
- SandBox API 테스트
- 프로젝트 관리 UI
- UAT 관리
도메인: OpenAPI, 개발자 센터, UI, SandBox, UAT
연계: OCGW
```

**English Description**

```
Purpose: OpenAPI Center Site (developer-center UI); usecase/feature/API management, onboarding, SandBox testing, project mgmt, UAT.
Functions:
- Usecase/feature/API management UI
- User onboarding
- SandBox API testing
- Project management UI
- UAT management
Domain: OpenAPI, developer center, UI, SandBox, UAT
Related: OCGW
```

---

### OCSE — Open Api Center Search Engine

**분류**: 플랫폼 > OpenAPI > OpenAPI 검색

**한글 설명**

```
목적: OpenAPI Center 검색 엔진.
주요 기능:
- 검색 처리
도메인: OpenAPI, 검색
연계: ES, OCDPS
```

**English Description**

```
Purpose: OpenAPI Center search engine.
Functions:
- Search processing
Domain: OpenAPI, search
Related: ES, OCDPS
```

---

### OGD — Onsite Grant Disbursement

**분류**: 정책·지원금 > 재난지원금 > 현장지급

**한글 설명**

```
목적: 현장지급 시스템(Onsite Grant Disbursement). 지급 등록/관리/통계 UI 제공.
주요 기능:
- 지급 등록/관리 UI
- 지급 통계 화면
도메인: 현장지급, 정책수당, 운영포탈
```

**English Description**

```
Purpose: Onsite Grant Disbursement; provides registration/management/stats UI for on-site payments.
Functions:
- Payment registration/management UI
- Statistics screen
Domain: on-site payment, subsidy, ops portal
```

---

### OINS — Open Api Inspector

**분류**: 플랫폼 > OpenAPI > OpenAPI 검사

**한글 설명**

```
목적: OpenAPI UAT(User Acceptance Test) 기능 제공.
주요 기능:
- OpenAPI UAT 기능 제공
도메인: OpenAPI, UAT, 검사
연계: OCPM
```

**English Description**

```
Purpose: Provides OpenAPI UAT (User Acceptance Test) function.
Functions:
- Provide OpenAPI UAT function
Domain: OpenAPI, UAT, validation
Related: OCPM
```

---

### OMCS — Open Api Mock Server

**분류**: 플랫폼 > OpenAPI > OpenAPI Mock

**한글 설명**

```
목적: OpenAPI Mock 서버. Mock API Content CRUD 및 Sandbox API Content 테스트 제공.
주요 기능:
- Mock API Content 등록/수정/삭제/조회
- Sandbox API Content 테스트
도메인: OpenAPI, Mock, Sandbox, API 컨텐츠
```

**English Description**

```
Purpose: OpenAPI Mock server; CRUD on mock API contents and Sandbox API content testing.
Functions:
- Create/update/delete/read mock API contents
- Sandbox API content testing
Domain: OpenAPI, mock, Sandbox, API content
```

---

### ONOTIFY — Open Api Notify

**분류**: 플랫폼 > OpenAPI > OpenAPI 알림

**한글 설명**

```
목적: OpenAPI 알림 컴포넌트(Email/Push/SMS).
주요 기능:
- Email 알림 발송
- Push 알림 발송
- SMS 알림 발송
도메인: OpenAPI, 알림, Email, Push, SMS
```

**English Description**

```
Purpose: OpenAPI notification component (Email / Push / SMS).
Functions:
- Send Email notifications
- Send Push notifications
- Send SMS notifications
Domain: OpenAPI, notification, Email, Push, SMS
```

---

### OPBO — Open Partner Back Office

**분류**: 플랫폼 > OpenAPI > OpenAPI 포탈

**한글 설명**

```
목적: OpenAPI 사용 제휴사를 위한 백오피스 시스템. API 사용량/통계 등 제공.
주요 기능:
- 제휴사 API 사용량/통계 대시보드
- 기타 백오피스 서비스
도메인: OpenAPI, 제휴사, 백오피스, 통계
```

**English Description**

```
Purpose: Back-office for OpenAPI partners; usage, statistics and other services.
Functions:
- Partner API usage/statistics dashboard
- Other back-office services
Domain: OpenAPI, partner, back-office, statistics
```

---

### ORS — Overseas Remittance Service

**분류**: 부가서비스 > 송금·기부·선물 > 해외 송금

**한글 설명**

```
목적: 해외 송금 서비스.
주요 기능:
- 해외 송금 처리
도메인: 해외 송금, ORS
```

**English Description**

```
Purpose: Overseas remittance service.
Functions:
- Manage overseas remittance
Domain: overseas remittance, ORS
```

---

### PARTNER PORTAL — Partner Portal

**분류**: 가맹점 > 가맹점 포탈 > 파트너 포탈

**한글 설명**

```
목적: 파트너(가맹점)가 거래/정산 내역 조회 및 상품 등록·관리하는 포탈.
주요 기능:
- 파트너 거래/정산 조회
- 상품 등록/관리
도메인: 파트너 포탈, 거래, 정산, 상품
```

**English Description**

```
Purpose: Portal where partners (merchants) inquire transactions/settlements and register/manage products.
Functions:
- Partner tx/settlement inquiry
- Product registration/management
Domain: partner portal, transaction, settlement, product
```

---

### PCS — Prepaid Card Service

**분류**: 카드 > 카드 조회 > 선불카드 서비스

**한글 설명**

```
목적: Wallet App향 선불카드 서비스 레이어. IAS/DCP/PCS/CS/CMS/CDM/KOD_ITN 정보를 조합해 카드 기준 정보 조회 및 라이프사이클 관리.
주요 기능:
- 유효기간/혜택/정책/웰컴카드 등 카드 기준 정보 조회
- 배송 관리, 재발급 신청, 다운로드, 삭제, 정지
도메인: 선불카드, Wallet, 라이프사이클, 카드 정보 조회
연계: IAS, DCP, CS, CMS, CDM, KOD_ITN
```

**English Description**

```
Purpose: Service layer for prepaid cards (Wallet App); aggregates info from IAS/DCP/PCS/CS/CMS/CDM/KOD_ITN to inquire and manage card lifecycle.
Functions:
- Inquire validity/benefits/policy/welcome-card info
- Manage delivery, reissue, download, delete, suspend
Domain: prepaid card, Wallet, lifecycle, card inquiry
Related: IAS, DCP, CS, CMS, CDM, KOD_ITN
```

---

### PCSI — Prepaid Card Service Inquiry

**분류**: 카드 > 카드 조회 > 선불카드 조회

**한글 설명**

```
목적: 월렛 조회용 서비스 컴포넌트. 사용자 카드 목록·계정 요약·혜택·실적·환불·거래내역·포인트 사용내역·상점 사용가능 카드 등 조회 제공.
주요 기능:
- 사용자 발급 카드 목록 제공
- 계정 요약(카드/쿠폰/계좌 등)
- 누적 혜택/카드 실적 정보
- 환불 진행 정보
- 카드 거래내역, 포인트 사용내역
- 상점에서 사용가능한 카드 목록
도메인: 선불카드 조회, 월렛, 거래내역, 포인트, 상점
연계: IAS, DCP, PCS, CardSE, CMS, CS, KPS, KOD_ITN, RS, GS, KCPS
```

**English Description**

```
Purpose: Inquiry-side service for Wallet; collates info from many core components for card list, account summary, benefits, performance, refunds, tx and point histories.
Functions:
- Cards issued to user
- Account summary (cards/coupons/linked accounts)
- Cumulative benefits / card performance
- Refund progress info
- Card tx history, point usage history
- Cards usable in a given store
Domain: prepaid inquiry, Wallet, tx history, points, store
Related: IAS, DCP, PCS, CardSE, CMS, CS, KPS, KOD_ITN, RS, GS, KCPS
```

---

### PIS — Prepaid Card Inquiry Service

**분류**: 카드 > 카드 조회 > 선불카드 조회

**한글 설명**

```
목적: 선불카드 조회 서비스 컴포넌트(신규). PCSI와 동일 정보를 제공하는 신규 채널.
주요 기능:
- 사용자 발급 카드 목록 제공
- 계정 요약, 누적 혜택, 카드 실적
- 환불 진행 정보, 거래내역, 포인트 사용내역
- 상점에서 사용가능한 카드 목록
도메인: 선불카드 조회, 신규, 월렛, 거래내역
연계: IAS, DCP, PCS, CS, CMS, RMS, PCSI
```

**English Description**

```
Purpose: New prepaid-card inquiry service; serves the same kind of info as PCSI through a new channel.
Functions:
- Cards issued to user
- Account summary, cumulative benefits, performance
- Refund progress, tx and point histories
- Cards usable in a given store
Domain: prepaid inquiry, new, Wallet, tx history
Related: IAS, DCP, PCS, CS, CMS, RMS, PCSI
```

---

### PLATFORM PORTAL — Platform Portal

**분류**: 운영 > 운영 포탈 > 플랫폼 포탈

**한글 설명**

```
목적: Partner 포탈 요청 상품·가맹점 검증/승인, 정산 정보, 코나 플랫폼 운영 기본 정보(ASP 약관/단말기/메시지 템플릿) 관리.
주요 기능:
- 상품/가맹점 검증·승인
- 정산 정보 관리
- ASP별 약관/단말기/메시지 템플릿 관리
도메인: 플랫폼 포탈, 검증, 승인, 정산, ASP
연계: Partner Portal
```

**English Description**

```
Purpose: Platform Portal manages verification/approval of products & merchants from Partner Portal, settlement info, and Kona platform base config (ASP terms, terminal, message templates).
Functions:
- Verify and approve products/merchants
- Manage settlement info
- Manage per-ASP terms / terminal / message templates
Domain: platform portal, verify, approve, settlement, ASP
Related: Partner Portal
```

---

### PLD — Personal Identifiable Information Leak Detection

**분류**: 플랫폼 > 보안 > 개인정보 유출 탐지

**한글 설명**

```
목적: 개인 정보 유출 탐지 컴포넌트. ISMS-P 인증용 개인정보 유출 탐지 기능 담당.
주요 기능:
- 개인정보 유출 탐지
- ISMS-P 인증 대응
도메인: 개인정보, 유출 탐지, ISMS-P
```

**English Description**

```
Purpose: Personal-information leak-detection component; supports ISMS-P certification.
Functions:
- Detect personal-information leaks
- Support ISMS-P certification
Domain: PII, leak detection, ISMS-P
```

---

### PMP — Payable Merchant Portal

**분류**: 가맹점 > 가맹점 관리 > 가맹점 검색

**한글 설명**

```
목적: 경기지역화폐 사용가능 매장 검색 서비스.
주요 기능:
- 경기지역화폐 매장 검색
도메인: 지역화폐, 가맹점 검색, 경기
```

**English Description**

```
Purpose: Service to find stores that accept Gyeonggi local currency.
Functions:
- Search stores accepting Gyeonggi local currency
Domain: local currency, merchant search, Gyeonggi
```

---

### PMS — Pocket Money Management Service

**분류**: 부가서비스 > 송금·기부·선물 > 용돈

**한글 설명**

```
목적: 용돈 관리 서비스.
주요 기능:
- 용돈 관리 기능 제공
도메인: 용돈, 관리, PMS
```

**English Description**

```
Purpose: Pocket-money management service.
Functions:
- Provide pocket-money management
Domain: pocket money, management, PMS
```

---

### PP — Payment Processor

**분류**: 거래 > 결제 > 결제 라우팅

**한글 설명**

```
목적: 코나카드의 충전/환불/잔액 이동/지불 등 모든 카드 거래 흐름을 제어하는 결제 프로세서. VAN의 ISO8583 메시지 게이트웨이.
주요 기능:
- VAN ISO8583 메시지 수신/검증
- TMS/CMS/IAS로 거래 라우팅
- TMS를 통한 크립토그램·DCVV 검증, 토큰 해제
- 토큰 해제 PAN을 IAS로 송신
- 오프라인 충전/환불 및 온/오프라인 지불 결과 푸시
도메인: 결제 프로세서, ISO8583, VAN, 토큰 해제, 푸시
연계: VAN, TMS, CMS, IAS, ITA(TMS), TSP, KNOTIFY
```

**English Description**

```
Purpose: Payment Processor controlling all card-related tx flow (charge/refund/balance/payment). Acts as ISO8583 gateway from VAN.
Functions:
- Receive/validate ISO8583 from VAN
- Route to TMS/CMS/IAS
- Cryptogram/DCVV validation and de-tokenization via TMS
- Send de-tokenized PAN to IAS
- Push notification for offline charge/refund and on/off-line pay result
Domain: payment processor, ISO8583, VAN, de-tokenization, push
Related: VAN, TMS, CMS, IAS, ITA(TMS), TSP, KNOTIFY
```

---

### PRM — Personal Information Access Record Management System

**분류**: 운영 > 모니터링/도구 > 개인정보 접근

**한글 설명**

```
목적: 개인정보 접근기록 관리 시스템. 플랫폼/고객센터/비즈포탈에서 사용자 정보 조회 시 접근 이력 기록.
주요 기능:
- 관리자 조회 시 접근 이력 기록
- 이력: 누가/언제/어떤 화면/누구를
도메인: 개인정보, 접근기록, 감사 로그, 컴플라이언스
```

**English Description**

```
Purpose: Privacy access-record management system; logs each operator access (who, when, which screen, whose data).
Functions:
- Log every operator access
- Capture who/when/where/what data accessed
Domain: PII, access log, audit, compliance
```

---

### PRS — Personalized Recommendation System

**분류**: 운영 > 광고/추천 > 추천

**한글 설명**

```
목적: 개인 맞춤형 추천 시스템. 사용자 활동 이력과 그룹 분석 기반으로 자주 사용하는 서비스 추천.
주요 기능:
- 활동 이력 기반 자주 사용 서비스 분석
- 성별/연령/지역 그룹화
- 그룹별 선호 서비스 분석
- 사용자 맞춤 서비스 추천
도메인: 추천, 개인화, 그룹 분석, 활동 이력
```

**English Description**

```
Purpose: Personalized Recommendation System; recommends frequently-used services based on activity and group preference analysis.
Functions:
- Analyze frequently-used services from activity
- Group users by gender/age/region
- Analyze preferred services per group
- Recommend personalized services
Domain: recommendation, personalization, group analysis, activity
```

---

### QRS — Query Running Service

**분류**: 플랫폼 > 인프라/공통 > 쿼리

**한글 설명**

```
목적: 쿼리 실행 서비스. 복잡한 쿼리식 기반 서비스를 빠르게 제공. 현재 타겟 푸시 서비스에 사용.
주요 기능:
- 쿼리 정책 저장/수정 (POST/PUT /query)
- 쿼리 정책 조회 (GET /query/{id})
- 쿼리 실행 (POST /query/{id}/run)
도메인: 쿼리 실행, 정책, 타겟 푸시, REST API
연계: KNOTIFY
```

**English Description**

```
Purpose: Query Running Service for fast delivery of complex-query-based services; currently used for targeted push.
Functions:
- Store/update query policy (POST/PUT /query)
- Read query policy (GET /query/{id})
- Run query (POST /query/{id}/run)
Domain: query, policy, targeted push, REST API
Related: KNOTIFY
```

---

### RDMT — Rundeck Monitoring

**분류**: 운영 > 모니터링/도구 > 런덱 모니터링

**한글 설명**

```
목적: Rundeck 모니터링 컴포넌트(API 서버). 런덱 구동 상태/스케쥴 진행 API 제공.
주요 기능:
- Rundeck 구동 상태 API
- 스케쥴 진행 상태 API
도메인: Rundeck, 모니터링, 스케쥴, 운영 API
```

**English Description**

```
Purpose: Rundeck monitoring component (API server); exposes Rundeck run-state and schedule status.
Functions:
- Rundeck run-state API
- Schedule progress API
Domain: Rundeck, monitoring, schedule, ops API
```

---

### RDS — Realtime Dispatcher Service

**분류**: 모빌리티 > 택시 거래/관제 > 택시 관제

**한글 설명**

```
목적: 택시 실시간 위치 트래킹 및 요청 전송 컴포넌트.
주요 기능:
- 택시 실시간 위치 트래킹
- 요청 전송
도메인: 택시, 실시간, 위치 트래킹
연계: MAS, MAS-S
```

**English Description**

```
Purpose: Realtime taxi-position tracking and request dispatcher.
Functions:
- Track taxi positions in realtime
- Send requests
Domain: taxi, realtime, position tracking
Related: MAS, MAS-S
```

---

### RFS — Request For Subsidy

**분류**: 정책·지원금 > 정책수당 > 보조금

**한글 설명**

```
목적: 보조금 24 (내게 맞는 정책수당 찾기) 서비스 컴포넌트.
주요 기능:
- 내게 맞는 정책수당 검색 서비스 제공
도메인: 보조금24, 정책수당, 검색
```

**English Description**

```
Purpose: Request For Subsidy; service that helps users find suitable policy subsidies.
Functions:
- Provide subsidy-search service for users
Domain: Subsidy 24, subsidy, search
```

---

### RFSP — Recommendation For Subsidy Portal

**분류**: 정책·지원금 > 정책수당 > 보조금

**한글 설명**

```
목적: 보조금 24 포탈. 공무원 지원용으로 만들었으나 내부/지자체 사용 안 함.
주요 기능:
- 보조금 24 운영 포탈
도메인: 보조금24, 포탈, 정책수당
상태: 종료된 컴포넌트
```

**English Description**

```
Purpose: 'Subsidy 24' portal for public officials; built but unused internally or by local govs.
Functions:
- Subsidy 24 ops portal
Domain: Subsidy 24, portal, subsidy
Status: deprecated / unused
```

---

### RPG — Remote Payment Gateway

**분류**: 거래 > 결제 > 온라인 PG

**한글 설명**

```
목적: 코나플랫폼 온라인 PG. 모바일/웹 온라인 결제 기능을 제공해 외부 가맹점 온라인 결제 관리. 비대칭/대칭 키 암호화 모두 지원, RPG-KM과 통신.
주요 기능:
- 온라인 거래 데이터 준비/검증/취소
- 외부 가맹점 암호화 통신(비대칭/대칭)
- 가맹점 주문 정보 저장
- VVAN과 통신해 거래 진행
도메인: 온라인 PG, 가맹점 결제, 암호화, RPG
연계: RPG-KM, VVAN
```

**English Description**

```
Purpose: KonaPlatform online PG; provides mobile/web online payment for external merchants. Supports both asymmetric and symmetric encryption; talks to RPG-KM.
Functions:
- Prepare/validate/cancel online tx data
- Encrypted comms with merchants (asym/sym)
- Store merchant order info
- Talk to VVAN to execute tx
Domain: online PG, merchant payment, encryption, RPG
Related: RPG-KM, VVAN
```

---

### RPG-KM — Remote Payment Gateway Key Management

**분류**: 플랫폼 > 보안 > 키 관리

**한글 설명**

```
목적: RPG 키 관리 컴포넌트. 외부 가맹점/RPG 요청에 의해 온라인 거래용 키를 생성·주기 관리.
주요 기능:
- 온라인 거래용 키 생성
- 키 라이프사이클 관리
도메인: RPG, 키 관리, 키 생성, 라이프사이클
연계: RPG
```

**English Description**

```
Purpose: RPG key management; produces, stores, and manages key lifecycle required by merchants/RPG.
Functions:
- Generate keys for online tx
- Manage key lifecycle
Domain: RPG, key management, key generation, lifecycle
Related: RPG
```

---

### RS — Refund Service

**분류**: 거래 > 환불 > 환불

**한글 설명**

```
목적: 환불 서비스. 카드 잔액 계좌 환불, 콜센터 환불, 잔액모으기/전환, 환불 계좌 관리 등 제공.
주요 기능:
- 카드 잔액 계좌 환불
- 콜센터 환불
- 잔액 모으기(코나머니 이동)
- 잔액 전환(개인 카드 간 이동)
- 환불 가능 여부/금액 조회
- 환불계좌 성명 인증/등록/변경/삭제
도메인: 환불, 잔액 이동, 환불 계좌 인증, 콜센터
연계: IAS, CS
```

**English Description**

```
Purpose: Refund service; account refund of card balance, call-center refund, balance collection/transfer, refund-account management.
Functions:
- Refund card balance to account
- Call-center refund
- Collect balance (move to KonaMoney)
- Transfer balance between user's cards
- Inquire refundability and amount
- Refund-account name auth, register/update/delete
Domain: refund, balance transfer, refund account, call center
Related: IAS, CS
```

---

### SAS — Statistics Analysis System

**분류**: 운영 > 통계 > 통계

**한글 설명**

```
목적: 통계 컴포넌트. 코나카드 거래 데이터를 가공해 도표/그래프로 시각화. 인입경로/성별/연령/주 사용시간 등 기반 프로모션·운영 의사결정에 활용.
주요 기능:
- 거래 데이터 누적/일별 시각화
- 고객 속성 통계 산출
- 마케팅·운영 의사결정 자료 제공
도메인: 통계, 시각화, 거래, 마케팅, 운영
```

**English Description**

```
Purpose: Statistics analysis component; visualizes accumulated and daily transactions and customer-attribute info to drive marketing and operations.
Functions:
- Visualize accumulated/daily tx
- Compute customer-attribute stats
- Feed marketing/ops decisions
Domain: stats, visualization, transaction, marketing, ops
```

---

### SCC — Spring Cloud Config

**분류**: 플랫폼 > 인프라/공통 > 설정

**한글 설명**

```
목적: OpenAPI 관련 컴포넌트 설정 정보 통합 관리. TGS 설정 변경 시 무중단으로 API를 통해 실시간 반영.
주요 기능:
- TGS 설정 정보 통합 관리
- 무중단 실시간 반영 API
- 필요 시 통합 관리 설정 추가
도메인: Spring Cloud Config, 설정 관리, OpenAPI, 무중단
```

**English Description**

```
Purpose: Spring Cloud Config component; centrally manages OpenAPI-related configs (e.g., TGS) and applies changes live without restart.
Functions:
- Manage TGS configs centrally
- Apply changes live via API without restart
- Add new components' configs as needed
Domain: Spring Cloud Config, configuration, OpenAPI, live reload
```

---

### SDTS — Secure Document Transfer System

**분류**: 플랫폼 > 외부 연계 > 전자문서

**한글 설명**

```
목적: 솔리데오 PINO 전자문서지갑 서비스 제공.
주요 기능:
- 전자문서지갑 서비스 제공
도메인: 전자문서, PINO, 솔리데오
```

**English Description**

```
Purpose: Provides Solideo PINO secure-document wallet service.
Functions:
- Provide secure-document wallet service
Domain: secure document, PINO, Solideo
```

---

### SMS-CORE — Sms Core

**분류**: 플랫폼 > 알림 > SMS 코어

**한글 설명**

```
목적: 문자 발송 중계 서비스. 문자 발송 요청을 SMS Agent(BGF Networks, IMC 휴머스온)로 전달.
주요 기능:
- 문자 발송 요청 수신
- BGF/IMC SMS Agent로 요청 전달
도메인: SMS, 문자 발송, 중계, BGF, IMC
연계: BIG_AGENT, imc_agent
```

**English Description**

```
Purpose: SMS-core; relays SMS-send requests to SMS Agents in use (BGF Networks, IMC Humuson).
Functions:
- Receive SMS-send requests
- Forward to BGF / IMC SMS Agents
Domain: SMS, message sending, relay, BGF, IMC
Related: BIG_AGENT, imc_agent
```

---

### SPS — Secure Phonenumber Service

**분류**: 회원·인증 > 인증 > 안심번호

**한글 설명**

```
목적: 안심번호 제공 서비스.
주요 기능:
- 안심번호 발급/관리
도메인: 안심번호, Secure Phone
```

**English Description**

```
Purpose: Secure phone-number service.
Functions:
- Issue and manage secure phone numbers
Domain: secure phone, anonymized number
```

---

### STT — Speech To Text

**분류**: 운영 > 고객센터 > 음성

**한글 설명**

```
목적: 음성파일을 텍스트로 변환하는 기능 제공.
주요 기능:
- 음성→텍스트 변환
도메인: STT, 음성 인식, 변환
연계: VAS, AICC
```

**English Description**

```
Purpose: Speech-to-Text conversion service.
Functions:
- Convert voice files to text
Domain: STT, speech recognition, conversion
Related: VAS, AICC
```

---

### SYSTEM PORTAL — System Portal

**분류**: 운영 > 운영 포탈 > 시스템 포탈

**한글 설명**

```
목적: 코나카드 발급용 전문 생성 및 코나카드시스템 운영 마스터 데이터 관리. Processing실 사용.
주요 기능:
- 코나카드 발급 전문 생성
- 운영용 마스터 데이터 관리(시스템 디폴트 정보 등)
도메인: 운영 포탈, 마스터 데이터, 발급 전문, Processing실
```

**English Description**

```
Purpose: System portal that creates communications for KonaCard issuance and registers master data for ops (default info, etc.). Used by Processing team.
Functions:
- Generate KonaCard issuance communications
- Register ops master data (defaults, etc.)
Domain: ops portal, master data, issuance, Processing team
```

---

### TBOS — Total Back Office Service

**분류**: 운영 > 운영 포탈 > 통합 백오피스

**한글 설명**

```
목적: 차세대 포탈 서비스. 내부에서 사용(통계/집계/정산 포함).
주요 기능:
- 차세대 포탈(Platform Portal) 제공
도메인: 차세대 포탈, 내부, 통계, 정산
연계: TBOSB, TBOST, TBOS_A, TBOS_AB, TBOS_AM
```

**English Description**

```
Purpose: Total BackOffice Service; next-generation portal (internal; includes stats/aggregation/settlement).
Functions:
- Provide next-generation Platform Portal
Domain: next-gen portal, internal, stats, settlement
Related: TBOSB, TBOST, TBOS_A, TBOS_AB, TBOS_AM
```

---

### TBOSB — Total Back Office Service Batch

**분류**: 운영 > 운영 포탈 > 통합 백오피스

**한글 설명**

```
목적: 차세대 포탈 서비스 제공을 위한 배치 서비스(UI 없음, 백엔드).
주요 기능:
- 차세대 포탈용 배치 작업 수행
도메인: 차세대 포탈, 배치, 백엔드
연계: TBOS
```

**English Description**

```
Purpose: Batch service supporting the next-generation portal (no UI, backend only).
Functions:
- Run batch jobs for next-gen portal
Domain: next-gen portal, batch, backend
Related: TBOS
```

---

### TBOST — Total Back Office Service Third Party

**분류**: 운영 > 운영 포탈 > 통합 백오피스

**한글 설명**

```
목적: 차세대 포탈 ThirdParty DB 데이터 제공 서비스. UI 없음, 백엔드(3rd Party 연결).
주요 기능:
- 3rd Party DB 데이터 제공
도메인: 차세대 포탈, 3rd Party, 백엔드
연계: TBOS
```

**English Description**

```
Purpose: Service providing third-party DB data for next-gen portal (no UI, backend).
Functions:
- Provide 3rd-party DB data
Domain: next-gen portal, 3rd party, backend
Related: TBOS
```

---

### TBOS_A — Total Back Office Service Account

**분류**: 운영 > 운영 포탈 > 통합계정

**한글 설명**

```
목적: 차세대 포탈 통합계정 신청 서비스(회원가입+권한신청+개인정보수정).
주요 기능:
- 통합계정 회원가입
- 권한 신청
- 개인정보 수정
도메인: 통합계정, 회원가입, 권한, 개인정보
연계: TBOS, TBOS_AB, TBOS_AM
```

**English Description**

```
Purpose: Total BackOffice integrated-account application service (signup + permission request + profile edit).
Functions:
- Integrated-account signup
- Permission request
- Profile edit
Domain: integrated account, signup, permission, profile
Related: TBOS, TBOS_AB, TBOS_AM
```

---

### TBOS_AB — Total Back Office Service Account Api

**분류**: 운영 > 운영 포탈 > 통합계정

**한글 설명**

```
목적: 차세대 포탈 통합계정 인증 서비스(API).
주요 기능:
- 통합계정 인증 API 제공
도메인: 통합계정, 인증, API
연계: TBOS_A
```

**English Description**

```
Purpose: Total BackOffice integrated-account authentication service (API).
Functions:
- Integrated-account auth API
Domain: integrated account, auth, API
Related: TBOS_A
```

---

### TBOS_AM — Total Back Office Service Account Management

**분류**: 운영 > 운영 포탈 > 통합계정

**한글 설명**

```
목적: 차세대 포탈 통합계정 관리 서비스(관리자용 API).
주요 기능:
- 통합계정 관리(관리자용)
도메인: 통합계정, 관리, 관리자, API
연계: TBOS_A
```

**English Description**

```
Purpose: Total BackOffice integrated-account management service (admin API).
Functions:
- Manage integrated accounts (admin)
Domain: integrated account, management, admin, API
Related: TBOS_A
```

---

### TCS — Transaction Compare System

**분류**: 거래 > 정산 > 거래 대사

**한글 설명**

```
목적: VAN과 거래 대사(對使) 파일 송수신 및 검증 컴포넌트. 정산 대상 거래의 유효성을 한 번 더 확인.
주요 기능:
- VAN 별 전문 양식 파일 파싱
- 집계 및 집계 파일 검증
- VAN으로 대사 파일 전송
- 거래 유효성 검증으로 정산 신뢰도 향상
도메인: VAN, 대사 파일, 정산, 거래 유효성
연계: VAN, CLR
```

**English Description**

```
Purpose: Transaction-compare system; sends/receives reconciliation files with VANs and re-verifies tx validity for clearing.
Functions:
- Parse per-VAN specialized files
- Aggregate and verify aggregation files
- Send reconciliation files to VAN
- Boost data trust for clearing
Domain: VAN, reconciliation, settlement, validity
Related: VAN, CLR
```

---

### TDIS — Business Portal Total Disaster

**분류**: 정책·지원금 > 재난지원금 > 신청 사이트

**한글 설명**

```
목적: 신규 긴급재난 지원금 신청 사이트. 지자체 공무원·내부·신청자 모두 사용.
주요 기능:
- 긴급재난 지원금 신청 처리
도메인: 재난지원금, 포탈, 통합
```

**English Description**

```
Purpose: New emergency disaster-relief application site (used by local-gov officials, internal, and applicants).
Functions:
- Process new emergency disaster-relief applications
Domain: disaster relief, portal, integrated
```

---

### TGS — Tall Gate Service

**분류**: 플랫폼 > OpenAPI > OpenAPI 게이트웨이

**한글 설명**

```
목적: Open API용 인증/인가 및 API Gateway 서비스(Tall Gate Service).
주요 기능:
- OpenAPI 인증/인가
- OpenAPI 게이트웨이
도메인: OpenAPI, 인증, 인가, 게이트웨이
연계: SCC, OAGW, OCGW
```

**English Description**

```
Purpose: Tall Gate Service; authentication/authorization and API gateway for Open API.
Functions:
- OpenAPI authentication/authorization
- OpenAPI gateway
Domain: OpenAPI, auth, authorization, gateway
Related: SCC, OAGW, OCGW
```

---

### TSP — Token Service Provider

**분류**: 거래 > 결제 > 토큰화

**한글 설명**

```
목적: 토큰 서비스 제공자(TSP). 카드 번호 토큰화/해제/재토큰화/대량 토큰화 및 BIN 관리.
주요 기능:
- 새 토큰 발급 / 토큰 해제 / 재토큰화
- 대량 토큰화
- PAN BIN 생성·관리, 토큰 BIN 관리
- PAN BIN ↔ 토큰 BIN 매핑
도메인: 토큰화, BIN, PAN, 토큰 관리
연계: ITA(TMS), DCP, IAS
```

**English Description**

```
Purpose: Token Service Provider; tokenizes/de-tokenizes/re-tokenizes/bulk-tokenizes card numbers and manages BINs.
Functions:
- Issue new token / detokenize / retokenize
- Bulk tokenization
- Manage PAN BIN and token BIN
- Map PAN BIN ↔ token BIN
Domain: tokenization, BIN, PAN, token mgmt
Related: ITA(TMS), DCP, IAS
```

---

### TSS — Transfer(Take-over) Support Service

**분류**: 회원·인증 > 회원 > 회원 이관

**한글 설명**

```
목적: 타사 서비스로부터 회원/잔액/체크카드/거래내역을 이관 지원하는 서비스.
주요 기능:
- 회원 정보 이관
- 잔액 정보 이관
- 체크 카드 연동 정보 이관
- 거래 내역 정보 이관
도메인: 이관, 회원, 잔액, 체크카드, 거래내역
```

**English Description**

```
Purpose: Take-over support service; migrates user, balance, debit-card, and tx data from another company's service.
Functions:
- Transfer user info
- Transfer balance info
- Transfer debit-card info
- Transfer transaction info
Domain: take-over, user, balance, debit card, tx history
```

---

### TTS — Taxi Transaction System

**분류**: 모빌리티 > 모빌리티 정산 > 택시 거래

**한글 설명**

```
목적: 택시 거래 시스템. 앱미터기 전문 연동 후 VAN을 통해 신용카드 거래 중계, 거래 수집, 정산파일 제공.
주요 기능:
- 앱미터기 전문 연동
- VAN을 통한 신용카드 거래 중계
- 거래 수집
- 정산파일 제공
도메인: 택시, 앱미터, VAN, 신용카드 결제, 정산
연계: VAN, AMM
```

**English Description**

```
Purpose: Taxi transaction system; relays credit-card transactions through VANs after AppMeter integration, collects them, and provides settlement files.
Functions:
- Integrate with AppMeter terminals
- Relay credit-card txs via VAN
- Collect relayed transactions
- Provide settlement files
Domain: taxi, AppMeter, VAN, credit-card pay, settlement
Related: VAN, AMM
```

---

### UIS — User Identification Service

**분류**: 회원·인증 > 인증 > 신분증 인증

**한글 설명**

```
목적: 코나카드 사용자의 신분증 진위 확인을 검증.
주요 기능:
- 사용자 신분증 진위 확인
도메인: 신분증, 진위 확인, UIS
```

**English Description**

```
Purpose: Verifies authenticity of the KonaCard user's ID.
Functions:
- Verify user-ID authenticity
Domain: ID, authenticity, UIS
```

---

### USER PORTAL — User Portal

**분류**: 운영 > 운영 포탈 > 사용자 포탈

**한글 설명**

```
목적: 코나카드 서비스 홈페이지(konacard.co.kr). 상품/가맹점 정보 조회.
주요 기능:
- 상품/가맹점 정보 조회
- 지역화폐 홈페이지
도메인: 홈페이지, 상품 조회, 가맹점, 지역화폐
```

**English Description**

```
Purpose: KonaCard service homepage (konacard.co.kr); inquire products and merchants.
Functions:
- Inquire products/merchants
- Local-currency homepage
Domain: homepage, product inquiry, merchant, local currency
```

---

### USERSITE — User Site

**분류**: 회원·인증 > 회원 > 사용자 사이트

**한글 설명**

```
목적: 앱이 없는 사용자가 회원가입/카드배송/이용내역확인 등을 수행하는 사용자 사이트. 거래 내역 실시간 조회 등 제공.
주요 기능:
- 회원가입
- 카드 배송 신청
- 이용내역(거래내역) 실시간 조회
도메인: 사용자 사이트, 회원가입, 카드 배송, 거래 조회
```

**English Description**

```
Purpose: Site for users without the app to sign up, request card delivery, and view usage/tx history in real time.
Functions:
- User signup
- Card delivery request
- Realtime usage/tx history
Domain: user site, signup, card delivery, tx inquiry
```

---

### VAM — Virtual Account Management

**분류**: 부가서비스 > 송금·기부·선물 > 가상계좌

**한글 설명**

```
목적: 가상 계좌 매핑 및 관리 서비스.
주요 기능:
- 가상 계좌 매핑/관리
도메인: 가상 계좌, VAM
```

**English Description**

```
Purpose: Virtual Account Management service.
Functions:
- Map and manage virtual accounts
Domain: virtual account, VAM
```

---

### VAS — Voice Assistant Service

**분류**: 운영 > 고객센터 > 음성

**한글 설명**

```
목적: 음성 비서 서비스(STT/TTS).
주요 기능:
- 음성→텍스트(STT)
- 텍스트→음성(TTS)
도메인: 음성, STT, TTS, 비서
연계: STT, AICC
```

**English Description**

```
Purpose: Voice Assistant Service (STT + TTS).
Functions:
- Speech-to-Text
- Text-to-Speech
Domain: voice, STT, TTS, assistant
Related: STT, AICC
```

---

### VCC — Visible Chatbot Core

**분류**: 운영 > 고객센터 > AI 챗봇 코어

**한글 설명**

```
목적: 보이는 챗봇 코어 서비스. VCF 메시지를 인덱스 기반으로 가이드, AI 코어 서비스로 전달. 인덱스(기획자 정의) 관리.
주요 기능:
- VCF로부터 메시지 수신 후 인덱스 기반 가이드
- AI 코어 서비스로 메시지 전달
- 기획자 정의 인덱스 관리
도메인: 보이는 챗봇, 코어, AI, 인덱스 관리
연계: VCF
```

**English Description**

```
Purpose: Visible Chatbot Core; receives messages from VCF, guides via indexes, forwards to AI core, manages PM-defined indexes.
Functions:
- Receive VCF messages and guide via indexes
- Forward messages to AI core service
- Manage indexes defined by PMs
Domain: visible chatbot, core, AI, index mgmt
Related: VCF
```

---

### VCF — Visible Chatbot Front

**분류**: 운영 > 고객센터 > AI 챗봇 UI

**한글 설명**

```
목적: 보이는 챗봇 프론트(웹UI). 사용자 메시지를 인덱스 기반으로 가이드 후 AI 코어로 전달.
주요 기능:
- 사용자에게 챗봇 UI 제공
- 사용자 메시지 → AI 코어 전달
- 고객센터용 챗봇 UI
도메인: 보이는 챗봇, 프론트, UI, 고객센터
연계: VCC
```

**English Description**

```
Purpose: Visible Chatbot Front (web UI); guides user messages by indexes and sends to AI core; AI chatbot UI for customer center.
Functions:
- Provide chatbot UI to users
- Forward user messages to AI core
- Used as CRM AI chatbot UI
Domain: visible chatbot, front, UI, customer center
Related: VCC
```

---

### VVAN — Virtual Value Addition Network

**분류**: 거래 > 거래 인프라 > VAN/단말기 검증

**한글 설명**

```
목적: 가맹점/단말기 검증 및 VAN사 역할 대행. 단말기 개통/정보 수정, 단말기·가맹점 검증, 온/오프라인 결제 거래 검증(ISO8583, 결제 로직).
주요 기능:
- van사 역할 대행
- 단말기 개통 및 정보 수정
- 단말기 및 가맹점 검증
- 온/오프라인 결제 거래 검증
- ISO8583 형식 검증
- 거래 검증 및 결제 로직 수행 (코나샵/캐시비)
도메인: VAN, 가맹점 검증, 단말기, ISO8583, 결제 검증, 코나샵, 캐시비
연계: RPG, IAS, PP
```

**English Description**

```
Purpose: Acts as virtual VAN; verifies merchants/terminals and online/offline payment transactions (ISO8583, payment logic).
Functions:
- Act as VAN proxy
- Open and edit terminal info
- Verify terminals and merchants
- Verify online/offline payment txs
- ISO8583 format validation
- Run tx verification + payment logic (KonaShop/Cashbee)
Domain: VAN, merchant verify, terminal, ISO8583, payment verify, KonaShop, Cashbee
Related: RPG, IAS, PP
```

---

### YBAT — Konays Batch Service

**분류**: 운영 > 모니터링/도구 > KonaYs

**한글 설명**

```
목적: KonaYs 배치 서비스.
주요 기능:
- KonaYs 프로젝트 배치 작업
도메인: KonaYs, 배치
```

**English Description**

```
Purpose: KonaYs batch service.
Functions:
- Run KonaYs batch jobs
Domain: KonaYs, batch
```

---

### YSTORE — Konays Store Service

**분류**: 운영 > 모니터링/도구 > KonaYs

**한글 설명**

```
목적: KonaYs 데이터 수집 저장 서비스.
주요 기능:
- KonaYs 프로젝트용 데이터 수집
도메인: KonaYs, 데이터 수집, 저장
```

**English Description**

```
Purpose: KonaYs data-collection store service.
Functions:
- Collect data for the KonaYs project
Domain: KonaYs, data collection, store
```

---
