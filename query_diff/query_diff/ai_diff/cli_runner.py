"""헤드리스 `claude -p`(구독)로 **의미 비교 판정만** — Python이 변환·ODS정의를 전부 선제공.

개인·로컬 전용. 느림의 원인이던 "Claude의 agentic 정보 탐색(meta3 MCP·파일 hunting)"을 없앤다:
  1) `compare_semantic`(정적 op↔an 맵)으로 정규화 base diff 생성(빠름·무료)
  2) 쿼리가 `ods.*` 를 읽으면 그 정의 SQL(`ODS_<T>.sql`)을 파일에서 읽어 선로딩
  3) base + 원본 SQL + ODS 정의를 프롬프트(stdin)에 임베드해 `claude -p --json-schema` 를
     **MCP·도구·스킬 없이 단일-샷** 호출 → Claude 는 판정만
  4) 구조화 출력(`structured_output`) → `SemanticDiff`

인증=구독(자식 env 에서 `ANTHROPIC_API_KEY` 제거 → metered 과금 방지). 프롬프트는 커질 수 있어
**stdin** 으로 전달(Windows 커맨드라인 길이 제한 회피). 모든 실패는 `SemanticDiff(LIMITED)` 로 반환.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from query_diff.ai_diff.schema import AI_SEMANTIC_DIFF_SCHEMA, AiSemanticDiff
from query_diff.models import Dialect, SemanticDiff, SemanticVerdict
from query_diff.semantic_diff import compare_semantic

_DEFAULT_TIMEOUT = 300  # 초 (QD_AI_TIMEOUT 로 재정의)
_DEFAULT_MODEL = "claude-sonnet-5"
_ODS_REF_RE = re.compile(r"\bods\.([A-Za-z_]\w*)", re.IGNORECASE)
_ODS_MAX_FILES = 12
_ODS_MAX_CHARS = 48000  # ODS 정의 임베드 총량 캡(다단계 ODS→ODS 계보 수용)


def _limited(reason: str, error: str = "") -> SemanticDiff:
    return SemanticDiff(verdict=SemanticVerdict.LIMITED, reason=reason, error=error or reason)


def _find_claude() -> str | None:
    return shutil.which("claude") or shutil.which("claude.cmd")


def _compact(base: SemanticDiff) -> dict:
    """SemanticDiff → AiSemanticDiff 와 동일 형태로 축약(plan_a/b·structure 제거)."""
    return {
        "verdict": base.verdict.value,
        "reason": base.reason,
        "issues": list(base.issues),
        "limitations": list(base.limitations),
        "dimensions": [
            {
                "dimension": d.dimension.value,
                "matched": d.matched,
                "limited": d.limited,
                "only_in_a": list(d.only_in_a),
                "only_in_b": list(d.only_in_b),
                "shared": list(d.shared),
                "explanation": d.explanation,
                "caveat": d.caveat,
            }
            for d in base.dimensions
        ],
    }


def _ods_context(sql_a: str, sql_b: str) -> tuple[dict[str, str], bool]:
    """두 SQL이 참조하는 ODS 집계 테이블의 정의 SQL 텍스트 수집(재귀·캡).

    `QD_ODS_DIR` 미설정/파일 없음 → ({}, False)(무해). 정의 내부의 추가 `ods.*` 는 재귀로 따라간다
    (참조 스캔은 **원본 전체**로 하고, 임베드 텍스트만 캡). 반환 2번째 = 길이/개수 캡으로 **잘림 여부**.
    """
    try:
        from query_diff.semantic_diff.ods_lineage import ods_registry
    except Exception:
        return {}, False
    reg = ods_registry()
    if not reg:
        return {}, False
    out: dict[str, str] = {}
    seen: set[str] = set()
    frontier = [m.group(1).lower() for s in (sql_a, sql_b) for m in _ODS_REF_RE.finditer(s)]
    total = 0
    truncated = False
    while frontier and len(out) < _ODS_MAX_FILES:
        name = frontier.pop(0)
        if name in seen:
            continue
        seen.add(name)
        path = reg.get(name)
        if not path:
            continue
        try:
            full = Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
        text = full
        if total + len(text) > _ODS_MAX_CHARS:
            text = text[: max(0, _ODS_MAX_CHARS - total)]
            truncated = True
        if not text:
            truncated = True
            break
        out[name] = text
        total += len(text)
        # 참조 스캔은 원본 전체로 → 임베드가 잘려도 하위 계보는 계속 따라간다
        frontier += [m.group(1).lower() for m in _ODS_REF_RE.finditer(full)]
    # 파일수 캡에 걸려 아직 따라갈 ODS 가 남은 경우도 잘림
    if len(out) >= _ODS_MAX_FILES and any(n not in seen and reg.get(n) for n in frontier):
        truncated = True
    return out, truncated


def _build_prompt(sql_a, sql_b, dia_a, dia_b, compact, ods_defs, ods_truncated=False) -> str:
    parts = [
        "너는 운영계(A)↔분석계(B) SQL 마이그레이션의 **의미 비교 판정자**다. 아래는 파이썬 엔진이 "
        "op↔an 정적 매핑(meta3 파생)으로 A를 변환한 뒤 낸 base 비교 결과와 원본 쿼리다. "
        "**외부 조회 없이** 주어진 정보로만 판정하라.\n\n",
        f"[A dialect] {dia_a}\n[B dialect] {dia_b}\n\n",
        "[BASE DIFF — 이미 op↔an 정규화됨] (JSON)\n"
        + json.dumps(compact, ensure_ascii=False, indent=2) + "\n\n",
        "[A SQL]\n" + sql_a.strip() + "\n\n",
        "[B SQL]\n" + sql_b.strip() + "\n\n",
    ]
    if ods_defs:
        chain = " → ".join(ods_defs.keys())
        parts.append(f"[ODS 정의 SQL — B가 읽는 ods.* 집계 테이블의 적재 정의. 계보(의존순): {chain}]\n")
        parts.append("각 단계는 또 다른 ods.* 를 읽을 수 있으니(다단계 집계) 아래 정의를 끝까지 따라가 "
                     "**최종 운영계 원천과 각 단계의 적재 필터·집계 단위(GROUP BY)** 를 확인하라.\n")
        if ods_truncated:
            parts.append("(주의: 일부 하위 ODS 정의가 길이 제한으로 축약됨 — 축약분은 적재 필터·집계 "
                         "단위 위주로 판단하고, 불확실하면 caveat로 '확인 필요' 표기.)\n")
        for name, text in ods_defs.items():
            parts.append(f"-- ODS: {name}\n{text.strip()}\n\n")
    parts.append(
        "[판정 절차 — 반드시 이 순서·규칙대로. 같은 관찰은 항상 같은 verdict 로 수렴해야 한다]\n"
        "\n"
        "1단계) 각 차원을 아래 셋 중 **정확히 하나**로 분류하라:\n"
        "   (a) 동치·매칭 — 무해한 LEFT 조인·동치 술어·표기차 포함, 결과 불변\n"
        "   (b) 데이터-의존 위험(제한) — 결과가 달라질 수 '있으나' SQL만으로는 확정 불가\n"
        "   (c) 확정 실차이 — 계보 전체를 봐도 결과가 확실히 달라짐\n"
        "\n"
        "2단계) verdict 는 아래 **상호배타 규칙**으로 기계적으로 결정하라(1단계 분류와 모순 금지):\n"
        "   - 모든 차원이 (a) 이고 위험 없음                → EQUIVALENT\n"
        "   - 한 차원이라도 (c) 확정 실차이                 → DIVERGENT\n"
        "   - (c) 없고 (b) 데이터-의존 위험이 ≥1           → LIMITED\n"
        "   - 정규화 불가 구문이 커서 비교 자체가 부분적      → LIMITED\n"
        "\n"
        "[위험 vs 확정차이 분류 기준 — 헷갈리면 이 목록으로 못박아라]\n"
        "- **데이터-의존 위험 → (b), verdict 는 LIMITED (DIVERGENT 아님):**\n"
        "  · ODS 적재의 INNER/LEFT JOIN 매칭률에 따른 행 누락·증가\n"
        "  · nvl·coalesce 등 NULL→기본값(0) 치환\n"
        "  · 증분·upsert(bf_dt·af_dt 윈도우) 커버리지 vs 전체 스캔\n"
        "  · 이름만 다른 미확인 잔여 매핑\n"
        "  → 해당 차원 `limited=true` + `caveat` 에 '실데이터 대사 필요'. only_in_* 로 확정차이처럼 쓰지 마라.\n"
        "- **확정 실차이 → (c), verdict 는 DIVERGENT:**\n"
        "  · 한쪽 계보 전체에 명백히 부재/상이한 WHERE·HAVING 술어\n"
        "  · 다른 집계 함수 / 다른 GROUP BY 단위(grain) / 행 집합을 확실히 바꾸는 테이블 가감\n"
        "  → 해당 차원 `only_in_*` 를 채우고 matched=false.\n"
        "\n"
        "[차원 플래그 귀속 규칙 — 위험을 매번 다른 차원에 붙이지 마라]\n"
        "- ODS **적재 파이프라인** 위험(INNER JOIN·증분·nvl)은 **BASE_TABLES(읽는 테이블)** 차원에 귀속.\n"
        "- **JOIN_GRAPH(조인 그래프)** 는 *비교 대상 쿼리 자체*의 조인만 반영한다. 최상위 쿼리에 조인이 "
        "없으면(적재 정의 안의 조인이 있어도) 이 차원은 **매칭**이다.\n"
        "- nvl·NULL→0 은 **PROJECTIONS(비집계 출력)** 차원의 위험으로 귀속(caveat + limited=true).\n"
        "- **ODS 집계 단위**: B가 읽는 ods.* 집계본의 세는 단위(GROUP BY grain)가 A 원천과 다르면 (c) 확정 "
        "실차이, 같은데 매칭률만 걸리면 (b) 위험 — BASE_TABLES/AGGREGATES 차원에 귀속.\n"
        "\n"
        "[차원 매칭(✓) vs 제한(⚠) 플래그 — 이 값도 규칙으로 고정하라. 뱃지가 실행마다 흔들리면 안 된다]\n"
        "- 한 차원은 **자기 차원이 직접 떠안는 데이터-의존 위험이 있을 때만** `limited=true`(⚠).\n"
        "  차원 내용이 계보상 동치이고 잔여 위험이 *다른 차원 소관*이면 `matched=true`·`limited=false`(✓)로 "
        "두고 `caveat` 엔 '위험은 <그 차원> 참조'만 남겨라. **caveat 가 있다고 무조건 ⚠ 아님 — 위험의 소유 "
        "차원이 기준이다.**\n"
    )
    # ODS 전용 '고정 결과'는 B가 실제로 ods.* 를 경유할 때(=위 [ODS 정의 SQL] 섹션 존재)만 적용.
    # 비-ODS 직접조회 쿼리에 조인 매칭률·증분·nvl·파이프라인 위험을 지어내지 못하게 게이팅한다.
    if ods_defs:
        parts.append(
            "- **B가 ODS 집계본을 경유**하므로(위 [ODS 정의 SQL] 참조) 아래 **고정 결과** 적용.\n"
            "  ⚠️ **단, 이 고정 ✓/⚠ 는 base 가 그 차원에 확정 실차이를 남기지 않은 경우에만 적용한다.** base 가 "
            "op↔an·ODS 계보 흡수 후에도 **다른 집계식·다른 GROUP/출력 라벨·다른 조인 대상이나 키·계보 전체에 "
            "부재한 필터** 를 `only_in_a`/`only_in_b` 로 남긴 차원은 그것이 **확정 실차이** 이므로 "
            "**✗(matched=false)** 로 두고 ODS 위험은 **caveat 로만 병기**(고정 ✓/⚠ 로 덮지 마라). 이 종속 규칙을 "
            "override 하는 단 하나의 예외는 **BASE_TABLES 의 ODS-스파인 테이블 치환**(아래)뿐이다.\n"
            "  · **BASE_TABLES(읽는 테이블)**: A 원천이 그 ods.* 집계본의 스파인이면(계보로 확인) 테이블명 차이는 "
            "확정차이 아님 → 조인 매칭률·증분 커버리지 위험 보유 → **⚠**(limited=true). (base 의 테이블 ✗ 를 "
            "여기서만 ⚠ 로 완화한다.)\n"
            "  · **PREDICATES(필터)**: 필터 '값'이 계보상 동치인 것은 흡수 → 그것만 남으면 **✓**(증분 윈도우 "
            "커버리지 위험은 PREDICATES 소관이 아니라 BASE_TABLES 소관). 그러나 **계보를 끝까지 봐도 대응이 없는 "
            "필터**(base only_in_a 잔존)는 B 결과집합을 넓히는 **확정 실차이 ✗** — '확인 필요 ⚠'로 낮추지 마라. "
            "⚠ 는 ODS 정의가 길이제한으로 축약됐거나 매핑이 실제로 불명일 때만.\n"
            "  · **PROJECTIONS(비집계 출력)**: 출력 컬럼·라벨이 그 외엔 동치이면 nvl·NULL→0 은 출력 '값'이 "
            "달라질 수 있는 **자기 차원 위험** → **⚠**(limited=true). 그러나 base 가 **출력 식/라벨 자체 차이**"
            "(예: 리터럴 '파주 외' vs '파주시 외')를 남겼으면 **✗ 우선**, nvl 은 caveat 에 병기. GROUP_KEYS 와 "
            "같은 라벨차는 **같은 판정으로 수렴**하라.\n"
            "  · **JOIN_GRAPH**: 최상위 조인 구조가 동치일 때만 ✓. base 가 **조인 대상 테이블/키 차이**(다른 "
            "relation·ON 에 섞인 추가 필터)를 남겼으면 그대로 **✗** — 테이블 치환을 BASE 로 재귀속해 ✓ 로 올리지 "
            "마라.\n"
            "  · **GROUP_KEYS / AGGREGATES**: 자기 위험 없음 → base 판정 유지(실차이 있으면 ✗, 없으면 ✓).\n"
        )
    else:
        parts.append(
            "- **이 비교는 ODS 경유가 아니다**(위 [ODS 정의 SQL] 섹션 없음 = A·B 모두 테이블 직접조회). 따라서 "
            "조인 매칭률·증분 커버리지·nvl·적재 파이프라인 같은 **ODS 위험을 BASE_TABLES 등에 지어내지 마라**. "
            "읽는 테이블이 동일하면 BASE_TABLES 는 **✓**(base 판정 신뢰). 각 차원의 위험은 그 차원이 비교 대상 "
            "SQL에서 **실제로 떠안는 것만** 인정한다.\n"
        )
    parts.append(
        "\n"
        "[NULL/빈 문자열('') 처리 — base 가 이미 결정적으로 판정함, 그대로 relay]\n"
        "- **NULL≡'' 동치:** 운영/Oracle `col IS NULL` ≡ 분석/Hive `col = ''`(및 `IS NOT NULL` ≡ `!= ''`)은 "
        "**값 로직 동치로 간주**한다. base 엔진이 이 매칭을 이미 처리했고, 분석계 NULL/빈문자 **혼재** 가능성 "
        "때문에 해당 차원(PREDICATES·JOIN_GRAPH)에 **`limited=true`(⚠) + caveat** 를 결정적으로 달아 둔다"
        "(날짜범위 caveat 과 동일 방식).\n"
        "- 너는 base 가 그 차원에 준 **`limited` 값과 caveat 를 그대로 유지·relay** 하라. 값 로직은 동치이니 "
        "**하드 차이/DIVERGENT 로 올리지 말고**, 동시에 base 가 `limited=true`+caveat 로 준 것을 **clean ✓ 로 "
        "낮추거나 '무해한 표기차'로 드롭하지도 마라**(원본 SQL 표기만 보고 임의 재판정 금지).\n"
        "- 널/빈문자 무관하게 한정자차·op↔an 이름차만 다른 경우는 그냥 matched(✓).\n"
        "- **base 신뢰:** base 가 `matched` 로 낸 술어·ON 차이는 base 가 정규화·흡수한 결과다. 재판정(하드 "
        "차이) 대상은 base 가 `only_in_a`/`only_in_b` 로 **실제 남긴 항목**뿐이다.\n"
        "\n"
        "[기타]\n"
        "- base 는 이미 op↔an 정규화됨. 확신 없으면 DIVERGENT 로 단정하지 말고 그 차원 `limited=true` + "
        "`caveat` '확인 필요' 로 남기고 verdict 는 LIMITED. 근거 없는 추측 금지.\n"
        "- 반드시 **AiSemanticDiff 구조화 출력(JSON)** 으로만 답하라. 설명·마크다운 코드블록 없이 "
        "**오직 JSON 객체 하나만** 출력하라."
    )
    return "".join(parts)


def _build_argv(claude_path: str, schema_json: str) -> list[str]:
    argv = [
        claude_path, "-p",
        "--output-format", "json",
        "--json-schema", schema_json,
        "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',  # MCP 끔
        "--model", os.environ.get("QD_AI_MODEL", _DEFAULT_MODEL),
        # 판정만 하면 되는데 기본 adaptive thinking 이 런어웨이(수분+ 사고)로 타임아웃 유발 →
        # effort 를 낮춰 바로 출력하게 한다(QD_AI_EFFORT 로 재정의).
        "--effort", os.environ.get("QD_AI_EFFORT", "low"),
    ]
    if os.name == "nt" and claude_path.lower().endswith((".cmd", ".bat")):
        argv = ["cmd", "/c", *argv]
    return argv


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _parse_json_loose(text: str) -> dict | None:
    """모델 텍스트에서 JSON 객체를 견고하게 추출: ①직접 → ②```펜스 → ③첫 균형 {…}(문자열 인지)."""
    text = (text or "").strip()
    if not text:
        return None
    try:  # ① 직접
        o = json.loads(text)
        if isinstance(o, dict):
            return o
    except json.JSONDecodeError:
        pass
    m = _JSON_FENCE_RE.search(text)  # ② 코드펜스 안
    if m:
        try:
            o = json.loads(m.group(1))
            if isinstance(o, dict):
                return o
        except json.JSONDecodeError:
            pass
    start = text.find("{")  # ③ 첫 균형 {…} 블록
    if start != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        o = json.loads(text[start : i + 1])
                        if isinstance(o, dict):
                            return o
                    except json.JSONDecodeError:
                        pass
                    break
    return None


def _extract_structured(envelope: dict) -> dict | None:
    so = envelope.get("structured_output")
    if isinstance(so, dict):
        return so
    result = envelope.get("result")
    if isinstance(result, str):
        return _parse_json_loose(result)
    return None


async def compare_via_cli(
    sql_a: str,
    dialect_a: Dialect,
    sql_b: str,
    dialect_b: Dialect,
    op_an=None,
) -> SemanticDiff:
    claude_path = _find_claude()
    if not claude_path:
        return _limited("AI 비교 사용 불가 — claude CLI 미설치(또는 PATH에 없음)")

    # 1) Python 변환+diff (동기, 빠름·무료)
    try:
        base = compare_semantic(sql_a, dialect_a, sql_b, dialect_b, op_an=op_an)
    except Exception as e:
        return _limited("base 비교(파이썬) 실패", str(e))

    compact = _compact(base)
    ods_defs, ods_truncated = _ods_context(sql_a, sql_b)
    prompt = _build_prompt(
        sql_a, sql_b, dialect_a.value, dialect_b.value, compact, ods_defs, ods_truncated
    )
    schema_json = json.dumps(AI_SEMANTIC_DIFF_SCHEMA, ensure_ascii=False)
    argv = _build_argv(claude_path, schema_json)

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # 구독 강제

    cwd = tempfile.mkdtemp(prefix="qd_ai_")  # 중립 cwd(프로젝트 스킬/CLAUDE.md 미로드 → 시작 비용↓)
    timeout_s = int(os.environ.get("QD_AI_TIMEOUT", str(_DEFAULT_TIMEOUT)))
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(input=prompt.encode("utf-8")), timeout=timeout_s
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
            return _limited("AI 비교 시간 초과", f"{timeout_s}s 초과")

        if proc.returncode != 0:
            err = (stderr_b or b"").decode("utf-8", "replace")[:500]
            return _limited("claude -p 실행 실패", f"exit={proc.returncode} {err}")

        stdout = (stdout_b or b"").decode("utf-8", "replace")
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as e:
            return _limited("AI 비교 출력 파싱 실패", f"{e}: {stdout[:300]}")
        if not isinstance(envelope, dict):
            return _limited("AI 비교 출력 형식 오류", str(type(envelope)))

        structured = _extract_structured(envelope)
        if structured is None:
            snippet = str(envelope.get("result", ""))[:300]
            return _limited(
                "AI 비교가 구조화 결과를 반환하지 못했습니다.",
                f"is_error={envelope.get('is_error')} stop={envelope.get('stop_reason')} "
                f"result={snippet}",
            )
        return AiSemanticDiff.model_validate(structured).to_semantic_diff()
    except Exception as e:
        return _limited("AI 비교 중 예기치 못한 오류가 발생했습니다.", str(e))
    finally:
        try:
            os.rmdir(cwd)
        except OSError:
            pass
