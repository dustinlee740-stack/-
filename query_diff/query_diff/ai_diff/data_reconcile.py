"""2차 판단(실데이터 샘플 대조) — 헤드리스 `claude -p` + **Kona-hue MCP** 로 B(분석계) 쿼리를
Hue 에서 실제 실행해, 사용자 제공 A(운영계) 샘플 CSV 와 대조한다.

1차(`cli_runner.compare_via_cli`)는 MCP 를 끄고(`--strict-mcp-config`) 정적 판정만 한다.
2차는 그 반대로 **MCP 를 켠다**:
  - `--strict-mcp-config`/빈 mcp-config 를 **넣지 않아** 사용자 스코프 MCP(Kona-hue 포함) 자동 로드.
  - **`--permission-mode default` 를 명시**(생략 시 서브프로세스가 plan 모드로 기동해 `--allowedTools`
    와 무관하게 전 툴이 차단됨 — 스파이크로 확인).
  - `--allowedTools` 로 Kona-hue 툴만 허용.

프롬프트(stdin): B쿼리 + 바인드값 + A샘플 CSV + op↔an 컬럼 힌트 + 절차/판정/캐비엇 규칙.
구조화 출력(`AiDataReconcile`) → `DataReconcileDiff`. 모든 실패는 `UNVERIFIABLE` 로 반환.

**주의(수용된 트레이드오프)**: A샘플과 B실행결과 표본이 서브프로세스 컨텍스트(=Claude 구독 API)로
전송된다. 비교는 LLM 판단이라 비결정적이다. 2차는 **참고 신호**이지 동치 증명이 아니다.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

from query_diff.ai_diff.cli_runner import (
    _extract_structured,
    _find_claude,
)
from query_diff.ai_diff.schema import AI_DATA_RECONCILE_SCHEMA, AiDataReconcile
from query_diff.models import (
    Attribution,
    Confidence,
    DataReconcileDiff,
    Dialect,
    FinalVerdict,
    ReconcileStatus,
)

_DEFAULT_TIMEOUT = 420          # 초 — 라이브 쿼리 + 도구 오케스트레이션(QD_RECON_TIMEOUT)
_DEFAULT_MODEL = "claude-sonnet-5"
_DEFAULT_EFFORT = "medium"
_SAMPLE_LIMIT = 1000            # B 유계 표본 LIMIT(컨텍스트 폭주 방지)
_A_CSV_CAP = 20000              # A 샘플 CSV 임베드 총량 캡(문자)
_COL_HINTS_CAP = 120            # op↔an 컬럼 힌트 줄 수 캡

# Kona-hue MCP 툴 화이트리스트(공백 구분 단일 인자).
_HUE_TOOLS = (
    "mcp__Kona-hue-MCP__hue_run_query "
    "mcp__Kona-hue-MCP__hue_download_query "
    "mcp__Kona-hue-MCP__hue_describe_table "
    "mcp__Kona-hue-MCP__hue_list_tables"
)

# Hue 스타일 변수: ${name} 또는 ${name=default}
_BIND_RE = re.compile(r"\$\{([A-Za-z_]\w*)(?:=([^}]*))?\}")


def _unverifiable(headline: str, error: str = "", **kw) -> DataReconcileDiff:
    return DataReconcileDiff(
        status=ReconcileStatus.UNVERIFIABLE,
        headline=headline,
        error=error or headline,
        **kw,
    )


def _final_from_base(base: dict | None) -> dict:
    """AI 대조가 불가한(UNVERIFIABLE) 상황에서 1차 정적 판정을 결정적으로 승계한 종합 필드.

    → 2차가 못 돌아도 프런트 '종합 판정' 배너가 비지 않게 한다.
    """
    v = (base or {}).get("verdict")
    if v == "EQUIVALENT":
        fv = FinalVerdict.SAME
    elif v == "DIVERGENT":
        fv = FinalVerdict.DIFFERENT
    else:
        fv = FinalVerdict.INCONCLUSIVE
    return {
        "final_verdict": fv,
        "final_confidence": Confidence.LOW,
        "final_reason": "실데이터 미검증 — 1차 정적 판정을 승계했습니다.",
        "attribution": Attribution.UNKNOWN,
    }


def _resolve_binds(sql: str, provided: dict[str, str] | None) -> dict[str, str]:
    """B쿼리의 `${var[=default]}` 를 수집해 provided 로 override. provided 우선 > 비어있지 않은 default > ''.

    같은 변수가 default 있는 형(`${x=v}`)과 없는 형(`${x}`)으로 함께 나올 수 있으므로,
    **비어있지 않은 default 를 우선**하고 뒤 등장이 앞의 좋은 값을 '' 로 덮어쓰지 않게 한다.
    """
    provided = {k: str(v) for k, v in (provided or {}).items()}
    binds: dict[str, str] = {}
    for m in _BIND_RE.finditer(sql or ""):
        name, default = m.group(1), m.group(2)
        if name in provided:
            binds[name] = provided[name]
            continue
        if default:                     # 비어있지 않은 default → 아직 좋은 값이 없을 때만 채택
            if not binds.get(name):
                binds[name] = default
        else:                           # bare `${x}` 또는 `${x=}` → 기존 값 보존
            binds.setdefault(name, "")
    for k, v in provided.items():       # SQL 에 없던 사용자 지정값도 보존
        binds.setdefault(k, v)
    return binds


def _column_map_hints(op_an, sql_b: str, cap: int = _COL_HINTS_CAP) -> list[str]:
    """op↔an 컬럼명이 **다른** 항목 중 B SQL 에 등장하는 것만 추려 정렬 힌트로 제공(best-effort)."""
    if op_an is None:
        return []
    text = (sql_b or "").upper()
    hints: list[str] = []
    for op_key, ent in getattr(op_an, "columns", {}).items():
        ent = ent or {}
        an_col = ent.get("an_col", "") or ""
        op_col = op_key.split(".")[-1]
        if not an_col or an_col.upper() == op_col.upper():
            continue                    # 동일명 = 정렬에 도움 안 됨
        if an_col.upper() in text or op_col.upper() in text:
            an_table = ent.get("an_table", "") or ""
            rhs = f"{an_table}.{an_col}" if an_table else an_col
            hints.append(f"운영 {op_key} ↔ 분석 {rhs}")
            if len(hints) >= cap:
                break
    return hints


def _build_argv(claude_path: str, schema_json: str) -> list[str]:
    argv = [
        claude_path, "-p",
        "--output-format", "json",
        "--json-schema", schema_json,
        # MCP 켬: --strict-mcp-config 를 넣지 않아 사용자 스코프 MCP(Kona-hue) 자동 로드.
        # permission-mode 를 반드시 default 로(미지정 시 plan 모드 → 전 툴 차단).
        "--permission-mode", "default",
        "--allowedTools", _HUE_TOOLS,
        "--model", os.environ.get("QD_RECON_MODEL", _DEFAULT_MODEL),
        "--effort", os.environ.get("QD_RECON_EFFORT", _DEFAULT_EFFORT),
    ]
    if os.name == "nt" and claude_path.lower().endswith((".cmd", ".bat")):
        argv = ["cmd", "/c", *argv]
    return argv


def _format_base(base: dict | None) -> str:
    """1차(정적) 판정 요약을 프롬프트용 텍스트로. base 는 cli_runner._compact 형태(dict) 또는 None."""
    if not base:
        return "(1차 정적 판정 없음)"
    lines = [f"판정(verdict): {base.get('verdict', '?')}"]
    reason = (base.get("reason") or "").strip()
    if reason:
        lines.append(f"요약: {reason.splitlines()[0]}")
    for d in base.get("dimensions") or []:
        mark = "⚠제한" if d.get("limited") else ("✓일치" if d.get("matched") else "✗불일치")
        exp = (d.get("explanation") or "").strip()
        lines.append(f"- {d.get('dimension')}: {mark}"
                     + (f" · {exp.splitlines()[0]}" if exp else ""))
    lims = base.get("limitations") or []
    if lims:
        lines.append("정규화 제한: " + "; ".join(str(x) for x in lims[:3]))
    return "\n".join(lines)


def _build_prompt(
    sql_b: str,
    dialect_b: str,
    sample_a_csv: str,
    a_sample_name: str | None,
    binds: dict[str, str],
    col_hints: list[str],
    b_csv_path: str,
    base_summary: str = "",
) -> str:
    a_csv = (sample_a_csv or "").strip()
    a_truncated = len(a_csv) > _A_CSV_CAP
    if a_truncated:
        a_csv = a_csv[:_A_CSV_CAP]
    has_a = bool(a_csv)

    bind_lines = "\n".join(f"  - {k} = {v!r}" for k, v in binds.items()) or "  (없음)"
    hint_lines = "\n".join(f"  - {h}" for h in col_hints) or "  (제공된 매핑 힌트 없음 — 필요 시 hue_describe_table 로 컬럼 확인)"

    parts = [
        "너는 query_diff 의 **2차 판단(실데이터 샘플 대조)** 검토자다. 1차(정적 AST 비교)는 이미 끝났다.\n",
        "목표: 분석계 B쿼리를 Hue 에서 실제로 실행한 표본과, 사용자가 제공한 운영계 A쿼리 실행 샘플을 "
        "대조해 **관측 근거**를 만들고, 1차(정적)와 2차(실데이터)를 **종합한 단일 최종 판정**을 낸다.\n\n",

        f"[1차 정적 판정 요약]\n{base_summary}\n\n",

        f"[B 쿼리 — 분석계 / {dialect_b}]\n{sql_b}\n\n",

        "[바인드값] — 아래 값을 B쿼리의 `${{...}}` 자리(또는 해당 필터)에 **그대로 치환**해 "
        "Impala 가 이해하는 완성 SQL 을 만든 뒤 실행하라. A샘플을 뽑은 조건과 동일해야 의미가 있다.\n"
        f"{bind_lines}\n\n",

        "[운영 op ↔ 분석 an 컬럼 힌트] — A(운영명) 컬럼을 B(분석명) 컬럼에 정렬할 때 참고.\n"
        f"{hint_lines}\n\n",
    ]

    if has_a:
        parts.append(
            f"[운영 A 샘플 CSV{' (앞부분만·잘림)' if a_truncated else ''}"
            f"{(' · ' + a_sample_name) if a_sample_name else ''}]\n{a_csv}\n\n"
        )
    else:
        parts.append(
            "[운영 A 샘플] 제공되지 않음. → 대조 불가. B만 실행해 결과 표본을 확인하고 "
            "status=UNVERIFIABLE 로, headline 에 '운영 샘플 미제공 — B측 실행 결과만 표시' 를 남겨라.\n\n"
        )

    parts.extend((
        "[절차]\n"
        "1) 바인드 치환한 완성 SQL 을 준비한다.\n"
        f"2) `hue_download_query`(dialect=impala, format=csv, outputPath=\"{b_csv_path}\") 로 B 전량을 "
        "로컬 CSV 로 저장한다(아티팩트). 성공하면 그 경로를 b_csv_path 에 echo 한다.\n"
        f"3) 컨텍스트 대조용으로 `hue_run_query`(dialect=impala) 로 **키 정렬 + LIMIT {_SAMPLE_LIMIT}** "
        "표본을 받는다. 이미 집계되어 행이 적으면 그대로. LIMIT 로 잘릴 수 있으면 sample_bounded=true.\n"
        "   - 필요하면 `hue_describe_table` 로 B 출력 테이블 컬럼/타입을 먼저 확인해도 된다.\n"
        "4) 컬럼 힌트로 A↔B 컬럼을 정렬하고, 키 컬럼(비측정·차원 컬럼)으로 행을 매칭한다.\n"
        "5) 3-way 로 분류: 값 일치 / A만 존재 / B만 존재 / 양쪽 존재·값 상이.\n"
        "6) 값 불일치는 추정 원인을 분류: 집계 그레인 차이 · NULL/'' 처리 · 날짜 포맷/타입 · "
        "반올림·정밀도 · 조인 카디널리티 · 순수 데이터 차이(분석계 미적재 등).\n\n",

        "[판정 status]\n"
        "- MATCH: 대응되는 모든 행·값이 일치.\n"
        "- MISMATCH: 핵심/다수 불일치.\n"
        "- PARTIAL: 일부만 일치.\n"
        "- UNVERIFIABLE: A샘플 없음 · B 조회 실패 · 정렬키 불명확 등 대조 불가.\n\n",

        "[필수 캐비엇 — caveats 에 반드시 포함(비대칭)]\n"
        "- '샘플 일치는 두 쿼리의 동치를 증명하지 않는다(표본 우연 일치 가능).'\n"
        "- '샘플 불일치는 실제 결과 차이의 강한 근거다.'\n"
        "- 표본이 LIMIT 로 유계인지, 집계 그레인이 정합되었는지 명시.\n\n",

        "[종합 판정(final_*) — 1차(정적)+2차(실데이터)를 함께 추론해 단일 결론]\n"
        "비대칭 원칙(일치=약한 신호·불일치=강한 근거)을 지켜 final_verdict/final_confidence/attribution/final_reason 을 정한다.\n"
        "- 2차 MATCH(일치): 1차 EQUIVALENT→ SAME/HIGH. 1차 LIMITED→ SAME/MEDIUM(참고—우연 일치 가능). "
        "**1차 DIVERGENT→ INCONCLUSIVE/LOW**(구조 차이가 있으므로 이 표본 일치는 우연일 수 있음 — SAME 단정 금지).\n"
        "- 2차 MISMATCH/PARTIAL(불일치): DIFFERENT/HIGH. attribution = 1차 DIVERGENT→ QUERY(쿼리 차이 기인) · "
        "1차 EQUIVALENT→ DATA(원천 데이터 차이 기인) · 1차 LIMITED→ 근거로 판단.\n"
        "- 2차 UNVERIFIABLE(대조 불가): 1차 승계 — EQUIVALENT→SAME, DIVERGENT→DIFFERENT, LIMITED→INCONCLUSIVE. "
        "confidence LOW~MEDIUM. final_reason 에 '실데이터 미검증' 명시.\n"
        "- attribution 은 final_verdict=DIFFERENT 일 때만 QUERY/DATA, 그 외엔 UNKNOWN.\n"
        "- final_reason: 1차 근거와 2차 관측을 한두 줄로 연결해 사람에게 설명"
        "(예: '구조는 동치인데 BANK02 합계가 달라 원천 데이터 차이로 판단').\n\n",

        "[출력] 반드시 **AiDataReconcile 구조화 JSON 하나만** 출력하라. 설명·마크다운·코드펜스 금지.",
    ))
    return "".join(parts)


async def reconcile_via_cli(
    sql_b: str,
    dialect_b: Dialect,
    sample_a_csv: str | None,
    sample_a_name: str | None,
    binds: dict[str, str] | None,
    op_an=None,
    out_dir: str | None = None,
    base_semantic: dict | None = None,
) -> DataReconcileDiff:
    """B(분석계)를 Hue 에서 실행해 A(운영계) 샘플과 대조하고, 1차(정적)와 종합해 단일 최종 판정을 낸다.

    `base_semantic` 은 1차 결과의 compact dict(`cli_runner._compact`). 실패는 모두 UNVERIFIABLE 로 반환.
    """
    base_final = _final_from_base(base_semantic)  # AI 불가 시 1차 승계용(종합 배너 비지 않게)
    claude_path = _find_claude()
    if not claude_path:
        return _unverifiable("2차 대조 사용 불가 — claude CLI 미설치(또는 PATH에 없음)", **base_final)

    resolved_binds = _resolve_binds(sql_b, binds)
    col_hints = _column_map_hints(op_an, sql_b)

    art_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp(prefix="qd_recon_art_"))
    try:
        art_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    b_csv_path = str(art_dir / "b_sample.csv")

    prompt = _build_prompt(
        sql_b, dialect_b.value, sample_a_csv or "", sample_a_name,
        resolved_binds, col_hints, b_csv_path, _format_base(base_semantic),
    )
    schema_json = json.dumps(AI_DATA_RECONCILE_SCHEMA, ensure_ascii=False)
    argv = _build_argv(claude_path, schema_json)

    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # 구독 강제(1차와 동일)

    cwd = tempfile.mkdtemp(prefix="qd_recon_")   # 중립 cwd(프로젝트 스킬/CLAUDE.md 미로드)
    timeout_s = int(os.environ.get("QD_RECON_TIMEOUT", str(_DEFAULT_TIMEOUT)))
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
            return _unverifiable("2차 대조 시간 초과", f"{timeout_s}s 초과",
                                 binds_used=resolved_binds, a_sample_name=sample_a_name, **base_final)

        if proc.returncode != 0:
            err = (stderr_b or b"").decode("utf-8", "replace")[:500]
            return _unverifiable("claude -p(2차) 실행 실패", f"exit={proc.returncode} {err}",
                                 binds_used=resolved_binds, a_sample_name=sample_a_name, **base_final)

        stdout = (stdout_b or b"").decode("utf-8", "replace")
        try:
            envelope = json.loads(stdout)
        except json.JSONDecodeError as e:
            return _unverifiable("2차 대조 출력 파싱 실패", f"{e}: {stdout[:300]}",
                                 binds_used=resolved_binds, a_sample_name=sample_a_name, **base_final)
        if not isinstance(envelope, dict):
            return _unverifiable("2차 대조 출력 형식 오류", str(type(envelope)),
                                 binds_used=resolved_binds, a_sample_name=sample_a_name, **base_final)

        structured = _extract_structured(envelope)
        if structured is None:
            snippet = str(envelope.get("result", ""))[:300]
            return _unverifiable(
                "2차 대조가 구조화 결과를 반환하지 못했습니다.",
                f"is_error={envelope.get('is_error')} stop={envelope.get('stop_reason')} "
                f"result={snippet}",
                binds_used=resolved_binds, a_sample_name=sample_a_name,
            )

        ai = AiDataReconcile.model_validate(structured)
        dr = ai.to_data_reconcile(binds=resolved_binds, a_sample_name=sample_a_name)
        # B CSV 다운로드 링크는 **서버가 지정한 경로에 실제로 파일이 생성된 경우에만** 노출.
        # (AI 가 프롬프트에 echo 한 경로는 신뢰하지 않는다 — 헛경로/누락 방지.)
        dr.b_csv_path = b_csv_path if Path(b_csv_path).exists() else None
        return dr
    except Exception as e:
        return _unverifiable("2차 대조 중 예기치 못한 오류가 발생했습니다.", str(e),
                             binds_used=resolved_binds, a_sample_name=sample_a_name, **base_final)
    finally:
        try:
            os.rmdir(cwd)
        except OSError:
            pass
