"""Wiki(Confluence) 페이지에서 SQL 블록을 추출하는 서비스"""

from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from query_diff.models import WikiBlock


# --- SSRF 방어 ---

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def _validate_url_not_internal(url: str) -> None:
    """사용자 입력 URL이 내부 네트워크를 가리키지 않는지 검증 (SSRF 방어)"""
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"유효하지 않은 URL입니다: {url}")

    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"허용되지 않는 스키마입니다: {parsed.scheme}")

    try:
        resolved = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        raise ValueError(f"호스트를 해석할 수 없습니다: {hostname}")

    for family, _, _, _, sockaddr in resolved:
        ip = ipaddress.ip_address(sockaddr[0])
        for network in _BLOCKED_NETWORKS:
            if ip in network:
                raise ValueError(
                    f"내부 네트워크 주소로의 요청은 차단됩니다: {hostname} -> {ip}"
                )


@dataclass
class _RawBlock:
    code: str
    language: str


def _extract_sql_from_html(html: str) -> list[_RawBlock]:
    """HTML 본문에서 SQL 코드 블록을 추출"""
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[_RawBlock] = []

    # 1) Confluence 코드 매크로: <ac:structured-macro ac:name="code">
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": "code"}):
        body = macro.find("ac:plain-text-body")
        if body and body.string:
            lang = "sql"
            lang_param = macro.find("ac:parameter", attrs={"ac:name": "language"})
            if lang_param and lang_param.string:
                lang = lang_param.string.strip().lower()
            blocks.append(_RawBlock(code=body.string.strip(), language=lang))

    # 2) 표준 <pre><code> 블록
    for pre in soup.find_all("pre"):
        code_tag = pre.find("code")
        text = code_tag.get_text(strip=True) if code_tag else pre.get_text(strip=True)
        if not text:
            continue
        lang = "sql"
        if code_tag:
            classes = code_tag.get("class", [])
            for cls in classes:
                if cls.startswith("language-"):
                    lang = cls.replace("language-", "")
        blocks.append(_RawBlock(code=text, language=lang))

    # 3) 마크다운 코드 펜스 (``` 블록) — Wiki HTML 내에 마크다운이 그대로 남아있는 경우
    raw_text = soup.get_text()
    fence_pattern = re.compile(r"```(\w*)\s*\n(.*?)```", re.DOTALL)
    for match in fence_pattern.finditer(raw_text):
        lang = match.group(1).strip().lower() or "sql"
        code = match.group(2).strip()
        if code:
            blocks.append(_RawBlock(code=code, language=lang))

    return blocks


def _looks_like_sql(code: str) -> bool:
    """코드 블록이 SQL인지 간이 판별"""
    sql_keywords = re.compile(
        r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|WITH|MERGE)\b",
        re.IGNORECASE,
    )
    return bool(sql_keywords.search(code))


_SQL_LANGUAGES = ("sql", "plsql", "hive", "oracle")


def _filter_sql_blocks(raw_blocks: list[_RawBlock]) -> list[tuple[WikiBlock, str]]:
    """_RawBlock 목록을 SQL 필터링 + WikiBlock 변환 (공통 헬퍼)"""
    results: list[tuple[WikiBlock, str]] = []
    idx = 0
    for block in raw_blocks:
        if block.language not in _SQL_LANGUAGES and not _looks_like_sql(block.code):
            continue

        lines = block.code.count("\n") + 1
        preview = block.code[:80].replace("\n", " ")
        if len(block.code) > 80:
            preview += "..."

        wb = WikiBlock(
            index=idx,
            preview=preview,
            lines=lines,
            language=block.language if block.language != "" else "sql",
        )
        results.append((wb, block.code))
        idx += 1

    return results


def extract_sql_blocks_from_html(html: str) -> list[WikiBlock]:
    """HTML에서 SQL 블록을 추출하여 WikiBlock 목록 반환"""
    raw_blocks = _extract_sql_from_html(html)
    return [wb for wb, _ in _filter_sql_blocks(raw_blocks)]


def fetch_confluence_page(url: str, token: str | None = None) -> str:
    """Confluence URL에서 HTML 본문을 가져옴"""
    _validate_url_not_internal(url)

    parsed = urlparse(url)
    # /wiki/spaces/SPACE/pages/PAGEID 형식에서 page_id 추출
    page_id_match = re.search(r"/pages/(\d+)", parsed.path)
    if not page_id_match:
        raise ValueError(f"URL에서 page ID를 추출할 수 없습니다: {url}")

    page_id = page_id_match.group(1)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    api_url = f"{base_url}/rest/api/content/{page_id}?expand=body.storage"

    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    resp = requests.get(api_url, headers=headers, timeout=30)
    resp.raise_for_status()

    data = resp.json()
    return data["body"]["storage"]["value"]


def extract_sql_from_url(url: str, token: str | None = None) -> tuple[list[WikiBlock], list[str]]:
    """
    Wiki URL에서 SQL 블록 추출.
    Returns: (blocks, full_sql_list) — blocks는 UI 표시용, full_sql_list는 원본 SQL 목록
    """
    html = fetch_confluence_page(url, token)
    raw_blocks = _extract_sql_from_html(html)
    pairs = _filter_sql_blocks(raw_blocks)
    wiki_blocks = [wb for wb, _ in pairs]
    full_sqls = [code for _, code in pairs]
    return wiki_blocks, full_sqls
