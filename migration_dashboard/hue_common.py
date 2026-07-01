"""Hue 연동 공용 — 설정 파싱 / 안전(오토컴플리트 전용) 가드.

🔒 안전 원칙(필수): 읽기 전용. Hue의 **메타데이터 읽기 API(autocomplete)만** 호출한다.
- 허용: GET, 그리고 POST는 오직 `/notebook/api/autocomplete/...` (컬럼 설명·순서 메타데이터 읽기).
- 금지: 쿼리 실행/Sample/Invalidate/새로고침/notebook 생성/job/가져오기/삭제/저장 등 그 외 모든 요청.
- SPA를 로드하지 않고 autocomplete만 직접 호출하므로 다른 요청은 발생하지 않는다.
"""
from __future__ import annotations

import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG = BASE_DIR / "hue_config.md"
AUTH_STATE = BASE_DIR / "hue_auth.json"

AUTOCOMPLETE_PREFIX = "/notebook/api/autocomplete"


def load_config() -> dict:
    """hue_config.md의 KEY=VALUE만 추출(주석/펜스/인용 무시)."""
    if not CONFIG.exists():
        raise SystemExit(f"{CONFIG} 없음 — 템플릿을 채워주세요.")
    cfg = {}
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("```") or s.startswith(">"):
            continue
        m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.*)$", s)
        if m:
            cfg[m.group(1)] = m.group(2).strip()
    return cfg


def assert_safe_autocomplete(base: str, url: str) -> None:
    """이 URL이 같은 호스트의 autocomplete 엔드포인트인지 확인(아니면 즉시 중단)."""
    if not url.startswith(base.rstrip("/") + AUTOCOMPLETE_PREFIX):
        raise SystemExit(f"🔒 안전위반 차단: autocomplete 외 URL 호출 시도 → {url}")
