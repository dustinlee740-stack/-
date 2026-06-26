-- meta3_mapping_checks.sql
-- meta3.table_col_mapping 을 No.3 스키마 매핑(운영 asis ↔ 분석 tobe) 소스로 쓸 때의
-- 데이터 적합성·품질 재검증 쿼리 모음.
-- 실행 대상: MCP `meta3-db` (PostgreSQL). 모든 식별자는 대문자로 조회한다.
-- 결과 해석은 ../../meta3_mapping_verification.md 참조.
-- 갱신(매핑 재적재) 시 재실행하여 보고서 수치를 재현/갱신한다.

-- ============================================================
-- A. 축·구조 / 값 변환 규칙 제공 여부
--   기대: col_mapping_type, mapping_biz_condition 전수 NULL/빈값
--   (= meta3는 컬럼 대응만 제공, 값 변환식은 미제공)
-- ============================================================
SELECT
  count(*)                                                            AS total_rows,
  count(*) FILTER (WHERE col_mapping_type IS NOT NULL)                AS has_mapping_type,
  count(*) FILTER (WHERE coalesce(mapping_biz_condition,'') <> '')    AS has_biz_condition
FROM meta3.table_col_mapping;

-- ============================================================
-- B-1. 운영계 컴포넌트 커버리지 (asis_db -> tobe_db, 행수/테이블수)
--   확인: IAS/RS/CS/CMS/KODASP(KOD)/KCPS(KCP) 등 핵심 컴포넌트 존재,
--   db_id 리네이밍(KODASP->KOD 등) 식별
-- ============================================================
SELECT asis_db_id, tobe_db_id,
       count(*)                       AS n,
       count(DISTINCT asis_table_id)  AS asis_tbls
FROM meta3.table_col_mapping
GROUP BY asis_db_id, tobe_db_id
ORDER BY n DESC;

-- ============================================================
-- B-2. v_oltp = identity(운영=분석) 집합 분류 (No.3 매핑 해석의 2단계)
--   해석 알고리즘:
--     1) table_col_mapping(asis)에 있으면 -> 리네임(운영≠분석), 매핑 사용
--     2) 없고 v_oltp에 있으면(std_yn='Y') -> 운영=분석 identity
--     3) 둘 다 없으면 -> meta3 미커버
--   v_oltp는 운영(asis) 명명과 정렬됨(match_asis >> match_tobe 확인용).
-- ============================================================
WITH o AS (SELECT db_id, tbl_id, col_id, std_yn FROM meta3.v_oltp_table_columns)
SELECT
  count(*) AS oltp_total,
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM meta3.table_col_mapping m
       WHERE upper(m.asis_db_id)=upper(o.db_id) AND upper(m.asis_table_id)=upper(o.tbl_id) AND upper(m.asis_col_id)=upper(o.col_id)))
                                                                        AS match_asis,   -- 리네임 대상
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM meta3.table_col_mapping m
       WHERE upper(m.tobe_db_id)=upper(o.db_id) AND upper(m.tobe_table_id)=upper(o.tbl_id) AND upper(m.tobe_col_id)=upper(o.col_id)))
                                                                        AS match_tobe,
  count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM meta3.table_col_mapping m
       WHERE (upper(m.asis_db_id)=upper(o.db_id) AND upper(m.asis_table_id)=upper(o.tbl_id) AND upper(m.asis_col_id)=upper(o.col_id))
          OR (upper(m.tobe_db_id)=upper(o.db_id) AND upper(m.tobe_table_id)=upper(o.tbl_id) AND upper(m.tobe_col_id)=upper(o.col_id))))
                                                                        AS match_neither -- 매핑 불요
FROM o;

-- B-2b. 매핑에 없는(둘 다 미매칭) v_oltp 컬럼의 std_yn 분포
--   std_yn='Y' = 표준화 완료 = 운영=분석 identity / 'N' = identity 단정 보류(확인 필요)
WITH o AS (SELECT db_id, tbl_id, col_id, std_yn FROM meta3.v_oltp_table_columns)
SELECT std_yn, count(*) n
FROM o
WHERE NOT EXISTS (SELECT 1 FROM meta3.table_col_mapping m
     WHERE (upper(m.asis_db_id)=upper(o.db_id) AND upper(m.asis_table_id)=upper(o.tbl_id) AND upper(m.asis_col_id)=upper(o.col_id))
        OR (upper(m.tobe_db_id)=upper(o.db_id) AND upper(m.tobe_table_id)=upper(o.tbl_id) AND upper(m.tobe_col_id)=upper(o.col_id)))
GROUP BY std_yn ORDER BY n DESC;

-- B-2c. identity 집합 표본 (매핑에 없고 v_oltp std_yn='Y'). 컴포넌트는 :db 로 교체.
WITH o AS (
  SELECT v.db_id, v.tbl_id, v.col_id, v.col_nm, v.std_yn,
    NOT EXISTS (SELECT 1 FROM meta3.table_col_mapping m
       WHERE (upper(m.asis_db_id)=upper(v.db_id) AND upper(m.asis_table_id)=upper(v.tbl_id) AND upper(m.asis_col_id)=upper(v.col_id))
          OR (upper(m.tobe_db_id)=upper(v.db_id) AND upper(m.tobe_table_id)=upper(v.tbl_id) AND upper(m.tobe_col_id)=upper(v.col_id))) AS not_in_map
  FROM meta3.v_oltp_table_columns v
)
SELECT db_id, tbl_id, col_id, col_nm
FROM o WHERE not_in_map AND std_yn='Y' AND db_id='IAS'
ORDER BY tbl_id, col_id LIMIT 12;

-- ============================================================
-- B-3. 분석계 실재 대조 표본: ODS가 참조하는 KOD.CONTRACT 컬럼이 tobe에 있는가
--   (ODS_ACUM_MBR_BYDT_AGG.sql 의 kc.ptn_id / kc.ptn_nm 와 대조)
-- ============================================================
SELECT tobe_col_id, tobe_col_name, asis_col_id, asis_col_name, tobe_pk, tobe_data_type
FROM meta3.table_col_mapping
WHERE tobe_db_id='KOD' AND tobe_table_id='CONTRACT'
  AND upper(tobe_col_id) IN ('PTN_ID','PTN_NM')
ORDER BY tobe_col_id;

-- ============================================================
-- C. 카디널리티 / 무결성
--   중복행 / 1:N / N:1 / 테이블·DB·컬럼ID·논리명 변경 비율
-- ============================================================
WITH base AS (SELECT * FROM meta3.table_col_mapping)
SELECT
  (SELECT count(*) FROM base) AS total_rows,
  (SELECT count(*) FROM (
     SELECT asis_db_id,asis_table_id,asis_col_id,tobe_db_id,tobe_table_id,tobe_col_id
     FROM base GROUP BY 1,2,3,4,5,6 HAVING count(*)>1) d)             AS dup_full_rows,
  (SELECT count(*) FROM (
     SELECT asis_db_id,asis_table_id,asis_col_id FROM base
     GROUP BY 1,2,3
     HAVING count(DISTINCT tobe_db_id||'.'||tobe_table_id||'.'||tobe_col_id)>1) x)
                                                                       AS asis_to_many_tobe, -- 1:N
  (SELECT count(*) FROM (
     SELECT tobe_db_id,tobe_table_id,tobe_col_id FROM base
     GROUP BY 1,2,3
     HAVING count(DISTINCT asis_db_id||'.'||asis_table_id||'.'||asis_col_id)>1) y)
                                                                       AS tobe_from_many_asis, -- N:1
  count(*) FILTER (WHERE asis_table_id <> tobe_table_id)              AS table_id_changed,
  count(*) FILTER (WHERE asis_db_id <> tobe_db_id)                    AS db_id_changed,
  count(*) FILTER (WHERE asis_col_id <> tobe_col_id)                  AS col_id_changed,
  count(*) FILTER (WHERE coalesce(asis_col_name,'') <> coalesce(tobe_col_name,'')) AS col_name_changed
FROM base;

-- C-detail. N:1 병합 표본 (복수 운영컬럼 -> 단일 분석컬럼)
SELECT tobe_db_id, tobe_table_id, tobe_col_id, tobe_col_name,
       count(*) AS asis_n,
       string_agg(asis_db_id||'.'||asis_table_id||'.'||asis_col_id, ' | ') AS asis_sources
FROM meta3.table_col_mapping
GROUP BY tobe_db_id, tobe_table_id, tobe_col_id, tobe_col_name
HAVING count(DISTINCT asis_db_id||'.'||asis_table_id||'.'||asis_col_id) > 1
ORDER BY asis_n DESC;

-- C-pk. PK 매핑 일관성 (No.5 Row diff 매칭 키 신뢰성)
SELECT
  count(*) FILTER (WHERE asis_pk='Y')                              AS asis_pk_y,
  count(*) FILTER (WHERE tobe_pk='Y')                              AS tobe_pk_y,
  count(*) FILTER (WHERE asis_pk='Y' AND tobe_pk='Y')              AS both_pk,
  count(*) FILTER (WHERE asis_pk='Y' AND coalesce(tobe_pk,'')<>'Y') AS asis_pk_only,
  count(*) FILTER (WHERE coalesce(asis_pk,'')<>'Y' AND tobe_pk='Y') AS tobe_pk_only
FROM meta3.table_col_mapping;

-- ============================================================
-- D. 데이터 품질: 빈 ID, 타입 변환
-- ============================================================
SELECT
  count(*) FILTER (WHERE coalesce(asis_col_id,'')='') AS asis_col_id_empty,
  count(*) FILTER (WHERE coalesce(tobe_col_id,'')='') AS tobe_col_id_empty,
  count(*) FILTER (WHERE upper(coalesce(asis_data_type,'')) <> upper(coalesce(tobe_data_type,''))) AS data_type_diff,
  count(DISTINCT asis_data_type) AS asis_dtypes,
  count(DISTINCT tobe_data_type) AS tobe_dtypes
FROM meta3.table_col_mapping;

-- D-detail. 타입 변환 패턴 상위 (값 비교 시 정규화 필요 구간 식별)
SELECT asis_data_type, tobe_data_type, count(*) AS n
FROM meta3.table_col_mapping
WHERE upper(coalesce(asis_data_type,'')) <> upper(coalesce(tobe_data_type,''))
GROUP BY asis_data_type, tobe_data_type
ORDER BY n DESC;
