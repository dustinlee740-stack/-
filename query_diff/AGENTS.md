# AGENTS.md — query_diff 분석 규칙

이 문서는 query_diff 워크스페이스에서 **분석계 스키마를 식별하고 계보를 판단할 때**
따라야 할 규칙을 정의한다. 코드가 아직 자동화하지 않은 판단(스키마 매핑·차이 귀인)을
사람/에이전트가 수행할 때의 기준선이다.

## 용어 / 망 구분

- **A쿼리 = 운영계(Oracle)**, **B쿼리 = 분석계(Hive)**. 자세한 흐름은 `query_diff/flow.md` 참조.
- 분석계 ↔ 운영계 테이블·컬럼 매핑의 (미래) 코드 소비처는
  `query_diff/structure_diff/schema_mapping.py` 다. 현재는 `IdentitySchemaMapping`
  (이름이 같으면 동일)만 구현돼 있고, flow.md No.3 매핑 모듈로 교체될 예정이다.
- 아래 규칙은 그 매핑(No.3)과 차이 귀인(No.6, "분석계 미적재 데이터" 판정)에서
  분석계 식별·계보 판단의 기준으로 사용한다.

## 규칙 ① 분석계 메타데이터 출처 = meta3 DB

> **분석계의 컴포넌트·테이블·컬럼 정보는 meta3 DB에서 참조한다.**

- 동명 추정이나 부분 문자열 매칭으로 분석계 객체를 판정하지 말고, meta3 DB를
  **권위 있는 출처**로 사용한다.
- 접근 수단: MCP 서버 **`meta3-db`** (PostgreSQL). 접속 정보는 사용자 스코프 MCP
  설정에 등록되어 있으므로 **이 문서나 코드에 자격증명을 적지 않는다** — 서버
  이름(`meta3-db`)으로만 참조한다.
- 조회 전 해당 MCP 서버 도구가 현재 세션에 연결돼 있는지 먼저 확인한다. 연결이
  안 보이면 Claude Code 세션 재시작 후 다시 시도한다(서버는 user 스코프로 등록됨).

## 규칙 ② 분석계 쿼리의 ODS 컴포넌트 참조 = 집계쿼리 역추적

> **분석계 쿼리가 ODS 컴포넌트(`ods.*` 테이블)를 참조하는 경우, 그 테이블을 ODS로
> 귀속시키지 말고 `D:\da\ttp_workflow\ODS\ODS_<TABLE>.sql` 집계 쿼리를 읽어 실제
> 원천 컴포넌트로 판단한다.**

- 근거: `ods.*` 테이블은 그 자체가 컴포넌트가 아니라 **파생/집계 결과물**이다.
  각 적재 쿼리의 `FROM`/`JOIN` 절이 실제 원천(운영계 등)을 가리킨다.
- 절차:
  1. 참조된 `ods.<table>` 에 대해 `ttp_workflow/ODS/ODS_<TABLE 대문자>.sql` 을 연다.
  2. 최상위 `FROM`/`JOIN` 의 **스키마 접두사**(`schema.table` 의 `schema`)로 원천
     컴포넌트를 귀속한다.
  3. 원천이 다시 `ods.*` 인 경우(ODS→ODS 중첩) **비-ODS 운영계 원천에 도달할
     때까지 재귀**한다.
- 예시 — `ODS_ACUM_MBR_BYDT_AGG.sql` (`ods.acum_mbr_bydt_agg`):
  - `FROM mapk.wallet_user` → `mapk` 컴포넌트
  - `INNER JOIN kod.contract` → `kod`(정책) 컴포넌트
  - `FROM ODS.asp_svc_ka_mpng` → 또 다른 ODS 테이블이므로
    `ODS_ASP_SVC_KA_MPNG.sql` 로 한 단계 더 역추적
  - 결론: 이 분석계 테이블의 원천 컴포넌트는 ODS가 아니라 `mapk` / `kod` 등이다.

## 범위 메모

- 이 문서는 **판단 규칙**만 정의한다. `schema_mapping.py` 등 코드 자동화는 별도
  작업(No.3 매핑 모듈)에서 이 규칙을 구현한다.
- `ttp_workflow/`는 **읽기 전용 입력**으로만 사용한다.
