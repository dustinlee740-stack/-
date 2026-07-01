"""샘플 생성기 공용 — 결정론적 버킷팅 / 합성 설명 / PII 컬럼 사전.

실제 운영계 CSV가 없는 설계 단계라, ttp_workflow에서 추출한 분석계 컬럼을 모집단의
'이관된 부분'으로 두고, 그 위에 '미이관/개인정보/요청없음' 컬럼을 인위로 주입해
대시보드의 모든 상태를 데모로 보여준다. 모든 주입은 이름 해시 기반이라 재현 가능(고정).
"""
from __future__ import annotations

import hashlib

# 데모용 개인정보 컬럼 (운영계엔 있으나 이관 제외 대상) — 테이블당 일부에 주입
PII_COLUMNS = [
    ("CUST_NM", "VARCHAR", "고객 성명"),
    ("RRNO", "VARCHAR", "주민등록번호"),
    ("TEL_NO", "VARCHAR", "연락처(전화번호)"),
    ("BANK_ACCT_NO", "VARCHAR", "은행 계좌번호"),
    ("EMAIL_ADDR", "VARCHAR", "이메일 주소"),
    ("HOME_ADDR", "VARCHAR", "주소"),
]

# 데모용 미이관(요청 없음/부적합) 일반 컬럼
EXTRA_COLUMNS = [
    ("RMK_CN", "VARCHAR", "비고 내용"),
    ("BATCH_SEQ", "BIGINT", "배치 일련번호"),
    ("LEGACY_FLAG", "CHAR", "레거시 구분 플래그"),
    ("INTERNAL_MEMO", "VARCHAR", "내부 메모"),
    ("TMP_WORK_VAL", "VARCHAR", "임시 작업값"),
]


def bucket(name: str, n: int) -> int:
    """이름 해시 → 0..n-1 (Python 해시 시드와 무관하게 결정론적)."""
    h = hashlib.md5(name.encode("utf-8")).hexdigest()
    return int(h, 16) % n


def guess_type(col: str) -> str:
    c = col.upper()
    if c.endswith(("DTTM", "DT")) or "DATE" in c:
        return "TIMESTAMP"
    if c.endswith(("AMT", "NO", "SNO", "CNT", "QTY")) or "AMOUNT" in c:
        return "BIGINT"
    if c.endswith("YN"):
        return "CHAR"
    return "VARCHAR"


def guess_desc(col: str) -> str:
    """컬럼명 관례로 합성 설명(데모용 — 실데이터는 운영계 CSV의 column_desc 사용)."""
    c = col.upper()
    rules = [
        ("DTTM", "일시"), ("DT", "일자"), ("AMT", "금액"), ("YN", "여부"),
        ("CD", "코드"), ("NM", "명"), ("NO", "번호"), ("SNO", "일련번호"),
        ("ID", "식별자"), ("CN", "내용"), ("CNT", "건수"), ("ST", "상태"),
    ]
    for suf, ko in rules:
        if c.endswith(suf):
            return f"{col} ({ko})"
    return f"{col} 항목"
