# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workspace 범위

이 CLAUDE.md는 **D:\da\migration_dashboard 한 폴더에만** 적용된다. 부모 `D:\da` 아래의 다른 폴더(pilot/, ttp_workflow/, query_diff/, v1/ 등)는 **별개 워크스페이스**다.

- 다른 폴더의 코드를 **import 하지 않는다** (pilot/CLAUDE.md가 교차 참조를 금지). 필요한 로직(예: xlsx 읽기)은 이 폴더 안에 자체 구현한다.
- 외부 데이터(`ttp_workflow/*.sql`, `pilot/components.xlsx`)는 **읽기 전용 입력**으로만 사용한다. `ttp_workflow`는 `parse_ttp_sql.py`의 입력, `components.xlsx`는 사본(`data/components.csv`)으로 재공급한다.
- 모든 경로는 `Path(__file__).parent` 기반으로 도출한다. 절대경로 하드코딩 금지.

## Purpose

운영계 DB → 분석계 DB **이관 현황 대시보드**를 만든다. 운영계/분석계 스키마(컴포넌트·테이블·컬럼) CSV를 비교해 무엇이 이관됐고/안 됐는지, 안 됐다면 사유가 무엇인지를 **단독 실행 HTML** 하나로 보여준다.

대시보드는 **항상 최신 데이터만** 반영한다(날짜별 아카이브 없음 — 산출물 `dashboard.html`을 덮어씀).

## Common commands

```bash
# 1) 샘플 분석계 CSV 생성 (ttp_workflow SQL 파싱)
python parse_ttp_sql.py --ttp-root ../ttp_workflow

# 2) 샘플 운영계 / 사유 CSV 생성 (데모용, 고정 seed)
python gen_sample_op_schema.py
python gen_sample_reasons.py

# 3) (선택) Hue(Hive Metastore) → 컬럼 한글 설명 + 순서 캐시 동기화 (읽기 전용)
python sync_hue_comments.py --full        # hue_config.md 필요. README의 안전 규칙 준수. 증분/--table 지원

# 4) 대시보드 빌드 (data/*.csv → dashboard.html)
python build_dashboard.py

# 의존성: 빌드/파서/샘플은 표준 라이브러리(csv)만. Hue 동기화만 playwright 필요.
```

## 데이터 흐름

```
ttp_workflow/*.sql ──parse_ttp_sql.py──► data/an_schema.csv      (분석계: 이관된 것)
(향후 운영계 추출)  ──사용자 제공──────► data/op_schema.csv      (운영계: 모집단)
(사용자 제공)       ───────────────────► data/reasons.csv        (미이관 사유 매핑)
pilot/components.xlsx ─사본───────────► data/components.csv     (컴포넌트 역할)
Hue/Hive Metastore (테이블 상세 Comment) ─sync(읽기전용)► data/column_comments.csv (컬럼 설명+순서)
                                          │
                            build_dashboard.py
                                          │
                                   dashboard.html (단독 실행)
```

CSV 4종의 정확한 컬럼 명세와 집계 규칙은 `README.md` 참조.
