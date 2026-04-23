SELECT
    LIST.PTN_ID
    , AL_MC_MAPNG_CD
    , PLAYER_NAME
    , PARTNER_NAME
    , MC_UPPER_NM
    , MC_DMC_ID
    , BIZ_LICENSE_NUMBER
    , POR_REPP_NAME
    , ZIP_CODE
    , ADDR
    , PLAYER_STATE_CD
    , REG_DT
    --, COUNT(*) OVER() AS TOTAL_CNT
FROM (
    SELECT
        PLAYER.PTN_ID                                                                       /* 파트너 ID */
        , (SELECT DISTINCT RL.AL_MC_MAPNG_CD
           FROM PORTAL.`ROLE` RL
           WHERE RL.USE_YN = 'Y'
             AND RL.PTN_ID = PLAYER.PTN_ID
             AND RL.PTN_ROLE_DV_CD IN ('0200','0300')
             AND RL.AL_MC_MAPNG_CD IS NOT NULL
          ) AL_MC_MAPNG_CD                                                                  /* 제휴사 코드 */
        , PLAYER.BYRL_PTN_NM                                                                /* 사업자명 */
        , PLAYER.PTN_ALS_NM                                                                  /* 파트너명 */
        , (SELECT FN_GET_PLAYER_INFO('ROLE_NAME', RC_ROLE.PTN_ID, RC_ROLE.PTN_ROLE_DV_CD)    /* ※ Hive UDF 등록 필요 */
           FROM PORTAL.`ROLE` UPPER_ROLE, PORTAL.`ROLE` RC_ROLE
           WHERE UPPER_ROLE.PTN_ROLE_DV_CD = '0200'
             AND UPPER_ROLE.UPPER_NO = RC_ROLE.PTN_ID
             AND RC_ROLE.PTN_ROLE_DV_CD = '0200'
             AND UPPER_ROLE.PTN_ID = PLAYER.PTN_ID
          ) MC_UPPER_NM                                                                     /* 대표가맹점 */
        , (SELECT RL.DMC_ID
           FROM PORTAL.`ROLE` RL
           WHERE RL.USE_YN = 'Y'
             AND RL.PTN_ID = PLAYER.PTN_ID
             AND RL.PTN_ROLE_DV_CD = '0200'
          ) MC_DMC_ID                                                                       /* 가맹점 ID */
        , PLAYER.BZNO                                                                       /* 사업자번호 */
        , POR_REPP.POR_REPP_NAME                                                            /* 대표자명 */
        , PLAYER.PSNO                                                                       /* 우편번호 */
        /* [변경] || → CONCAT, NULL 안전 처리를 위해 COALESCE 적용 */
        , CONCAT(COALESCE(PLAYER.PST_ADDR, ''), ' ', COALESCE(PLAYER.DTL_ADDR, '')) ADDR    /* 주소 */
        , FN_GET_PLAYER_INFO('NM', PLAYER.ASP_NO, '0100') AS ASP_NM                         /* 소속 ASP명, ※ Hive UDF 등록 필요 */
        /* [변경] DECODE → CASE WHEN */
        , CASE PLAYER_STATE_CD
            WHEN 'A' THEN '정상'
            WHEN 'C' THEN '중지'
            WHEN 'B' THEN '해지'
          END AS PLAYER_STATE_CD                                                             /* 가맹점 상태 */
        , PLAYER.SYS_CRE_DTTM                                                               /* 등록일시 */
        , (
            /* [변경] 중첩 DECODE → CASE WHEN (NULL 비교는 IS NULL로 변환) */
            SELECT
              CASE
                WHEN MERCHANT_TYPE_CD = '2' THEN '02'
                WHEN UPPER_NO IS NULL THEN '01'
                ELSE '03'
              END
            FROM PORTAL.`ROLE` RL
            WHERE RL.PTN_ROLE_DV_CD = '0200'
              AND RL.PTN_ID = PLAYER.PTN_ID
          ) MC_TYPE_CD                                                                       /* MC 가맹점 분류 코드 */
        , (SELECT UPPER_NO
           FROM PORTAL.`ROLE` RL
           WHERE RL.PTN_ROLE_DV_CD = '0200'
             AND RL.PTN_ID = PLAYER.PTN_ID
          ) UPPER_NO
    FROM PORTAL.PLAYER PLAYER
    LEFT OUTER JOIN (
        SELECT
            PTN_ID
            /* [변경] || → CONCAT */
            , MAX(CONCAT(REQUEST_DETAIL.PTN_RQS_SNO, REQUEST_DETAIL.DETAIL_NO)) PTN_RQS_SNO
        FROM PORTAL.REQUEST_PARTNER POR_PTN_RQS
        LEFT OUTER JOIN PORTAL.REQUEST_DETAIL REQUEST_DETAIL
            ON POR_PTN_RQS.PTN_RQS_SNO = REQUEST_DETAIL.PTN_RQS_SNO
        WHERE REQUEST_DETAIL.RQS_APV_ST_CD = '0300'
        GROUP BY PTN_ID
    ) REQUEST_DETAIL ON PLAYER.PTN_ID = REQUEST_DETAIL.PTN_ID
    LEFT OUTER JOIN (
        /* [변경] || → CONCAT */
        SELECT PTN_ID, REPP_NM, CONCAT(FNST_MPH_NO, BPOS_MPH_NO) AS HP
        FROM PORTAL.POR_REPP
        WHERE POR_REPP_NO = '1'
    ) POR_REPP ON PLAYER.PTN_ID = POR_REPP.PTN_ID
    WHERE 1 = 1
        AND ENTP_GV_YN = 'N'
        /* [변경] TO_DATE(... || ..., format) → CAST AS TIMESTAMP */
        AND PLAYER.SYS_CRE_DTTM >= CAST('2026-01-14 00:00:00' AS TIMESTAMP)
        AND PLAYER.SYS_CRE_DTTM <= CAST('2026-04-14 23:59:59' AS TIMESTAMP)
) LIST
WHERE LIST.MC_TYPE_CD = '03'
    AND LIST.UPPER_NO IN (
        SELECT PTN_ID
        FROM PORTAL.`ROLE`
        WHERE PTN_ROLE_DV_CD = '0200'
          AND DMC_ID IN ('410513818590201')
    ) /* 여기에 필요한 대표가맹점 ID 넣어주시면 됩니다. */
ORDER BY LIST.SYS_CRE_DTTM DESC
;
