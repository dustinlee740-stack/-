"""ODS 집계 테이블 리니지 해소 — "B가 ODS 집계 경유 → 원천 귀속 + 대사 필요 지점" 리포트용.

목적: 운영 데이터가 폐쇄망이라 **데이터 대사가 불가**한 환경에서, 분석계(B) 쿼리가 ODS 집계 테이블
(`ods.*`)을 읽을 때 그 정의 쿼리(`ttp_workflow/ODS/ODS_<T>.sql`)를 읽어
  ① 구동 스파인 원천 테이블(조인 제외, CTE/서브쿼리 관통, ODS→ODS 재귀)
  ② 집계에 박힌 **대사 필요 지점**(적재 필터·조인·집계 기준)
을 뽑는다. base_tables 비교가 "완전히 다른 테이블 ✗" 대신 **"동일 원천 귀속 + 대사 필요(제한적)"**로
표기하게 한다.

**엄격 게이트**: 오직 정의 파일이 있는 ODS 테이블에만 발동. 경로 미설정(`QD_ODS_DIR`)·파일 없음·파싱
실패·스파인 모호 → **None**(무동작). 일반 쿼리·미설정 환경엔 사이드이펙트 0.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache

import sqlglot
from sqlglot import exp

# ODS 정의 DML 접두사(`upsert/insert into [overwrite] table <name>`) 제거용.
_DML_PREFIX_RE = re.compile(
    r"^\s*(?:upsert|insert)\s+(?:into\s+|overwrite\s+)?table\s+\S+\s*", re.IGNORECASE
)
_MAX_DEPTH = 12


@dataclass
class OdsLineage:
    """ODS 집계 테이블 한 건의 리니지."""
    table: str                                   # ODS 테이블명(lower)
    spine: frozenset[str] = frozenset()          # 구동 스파인 원천 base 테이블(lower, 비-ODS). 빈=모호
    chain: list[str] = field(default_factory=list)   # 표시용 경로(ODS→…→원천)
    sources: list[str] = field(default_factory=list) # 정의 내 비-CTE 소스 테이블(조인 포함)
    joins: list[str] = field(default_factory=list)   # "table(inner|left)" 요약
    filters: list[str] = field(default_factory=list) # 적재/필터 조건(원문 근사)
    aggregated: bool = False                          # GROUP BY 존재


def _ods_dir() -> str | None:
    """ODS 정의 폴더 — env `QD_ODS_DIR`. 미설정/폴더 없음 → None(기능 비활성)."""
    d = os.environ.get("QD_ODS_DIR")
    return d if d and os.path.isdir(d) else None


def ods_registry() -> dict[str, str]:
    """ODS 테이블명(lower) → 정의 파일 경로. 폴더 없으면 빈 dict(=비활성)."""
    d = _ods_dir()
    if not d:
        return {}
    reg: dict[str, str] = {}
    try:
        for fn in os.listdir(d):
            m = re.fullmatch(r"ODS_(.+)\.sql", fn, re.IGNORECASE)
            if m:
                reg[m.group(1).lower()] = os.path.join(d, fn)
    except OSError:
        return {}
    return reg


def is_ods_table(name: str) -> bool:
    return name.lower() in ods_registry()


def _parse_def(path: str) -> exp.Expression | None:
    """ODS 정의 SQL 로드 → DML 언랩 → 전처리 → sqlglot(hive) 파싱. 실패 시 None."""
    from query_diff.validation_service import _preprocess_sql

    try:
        raw = open(path, encoding="utf-8").read()
    except OSError:
        return None
    body = _DML_PREFIX_RE.sub("", raw, count=1)
    try:
        body = _preprocess_sql(body)
        return sqlglot.parse_one(body, dialect="hive")
    except Exception:
        return None


def _cte_map(node: exp.Expression) -> dict[str, exp.Expression]:
    """node(Select/Union)의 WITH CTE → {별칭: 정의}. WITH 는 Union 노드에 붙기도 함."""
    m: dict[str, exp.Expression] = {}
    with_ = node.args.get("with_") or node.args.get("with")  # sqlglot 버전별 키
    if with_:
        for cte in with_.expressions:
            m[cte.alias_or_name.lower()] = cte.this
    return m


def _from_anchor(select: exp.Select) -> exp.Expression | None:
    frm = select.args.get("from_") or select.args.get("from")  # sqlglot 버전별 키
    if frm is None:
        return None
    anchor = frm.this  # 구동 소스(조인은 args['joins']에 별도)
    if anchor is None:
        exprs = frm.args.get("expressions")
        anchor = exprs[0] if exprs else None
    return anchor


def _spine(
    node: exp.Expression, cte: dict[str, exp.Expression], visited: set[str], depth: int
) -> frozenset[str] | None:
    """node(Select/Union/…)의 구동 스파인 비-ODS base 테이블 집합. 모호/실패 시 None."""
    if depth > _MAX_DEPTH or node is None:
        return None
    if isinstance(node, exp.Union):
        cte = {**cte, **_cte_map(node)}   # WITH 가 Union 에 붙는 경우
        left = _spine(node.left, cte, visited, depth + 1)
        right = _spine(node.right, cte, visited, depth + 1)
        if left is None or right is None:
            return None
        return left | right
    if isinstance(node, exp.Subquery):
        inner = node.this
        return _spine(inner, {**cte, **_cte_map(inner)}, visited, depth + 1)
    if not isinstance(node, exp.Select):
        return None
    cte = {**cte, **_cte_map(node)}
    anchor = _from_anchor(node)
    if anchor is None:
        return None
    if isinstance(anchor, exp.Subquery):
        return _spine(anchor, cte, visited, depth + 1)
    if isinstance(anchor, exp.Table):
        name = anchor.name.lower()
        if name in cte:                          # CTE 참조 → 정의로 하강
            return _spine(cte[name], cte, visited, depth + 1)
        if name in ods_registry():               # 또 ODS → 재귀
            if name in visited:
                return None                       # 사이클
            sub = _resolve(name, visited | {name}, depth + 1)
            return sub.spine if (sub and sub.spine) else None
        return frozenset({name})                 # 비-ODS 종단 base = 스파인
    return None


def _collect_report(tree: exp.Expression, cte_names: set[str]) -> tuple[list[str], list[str], list[str], bool]:
    """정의 트리에서 (소스 테이블, 조인 요약, 필터 조건, 집계 여부) 근사 추출(표시용)."""
    sources: list[str] = []
    for t in tree.find_all(exp.Table):
        nm = t.name.lower()
        if nm not in cte_names and nm not in sources:
            sources.append(f"{(t.db + '.') if t.db else ''}{nm}")
    joins: list[str] = []
    for j in tree.find_all(exp.Join):
        jt = j.this
        if isinstance(jt, exp.Table) and jt.name.lower() not in cte_names:
            side = (j.args.get("side") or ("inner" if not j.args.get("kind") else j.args.get("kind"))) or "join"
            joins.append(f"{jt.name.lower()}({str(side).lower()})")
    filters: list[str] = []
    for w in tree.find_all(exp.Where):
        for part in _split_and(w.this):
            try:
                s = part.sql(dialect="hive")
            except Exception:
                continue
            s = re.sub(r"\s+", " ", s).strip()
            if s and s != "1 = 1" and s not in filters:
                filters.append(s)
    return sources, joins, filters[:8]


def _split_and(node: exp.Expression) -> list[exp.Expression]:
    if isinstance(node, exp.And):
        return _split_and(node.left) + _split_and(node.right)
    if isinstance(node, exp.Paren):
        return _split_and(node.this)
    return [node]


def _path_has_group(
    node: exp.Expression, cte: dict[str, exp.Expression], visited: set[str], depth: int
) -> bool:
    """**구동(스파인) 경로**상 Select 에 GROUP BY 가 있으면 True — 즉 ODS 출력 입도가 원장보다 굵음.

    `_spine` 과 동일 경로 규칙(FROM 앵커 → CTE/서브쿼리 하강, ODS 재귀; **조인 브랜치 제외**).
    옆다리 LEFT/INNER JOIN 으로 붙는 lookup CTE 의 집계는 경로 밖이라 무시(입도 오탐 방지)."""
    if depth > _MAX_DEPTH or node is None:
        return False
    if isinstance(node, exp.Union):
        cte = {**cte, **_cte_map(node)}
        return _path_has_group(node.left, cte, visited, depth + 1) or _path_has_group(
            node.right, cte, visited, depth + 1
        )
    if isinstance(node, exp.Subquery):
        inner = node.this
        return _path_has_group(inner, {**cte, **_cte_map(inner)}, visited, depth + 1)
    if not isinstance(node, exp.Select):
        return False
    cte = {**cte, **_cte_map(node)}
    if node.args.get("group") or node.args.get("group_"):   # 이 Select 자체가 GROUP BY
        return True
    anchor = _from_anchor(node)
    if isinstance(anchor, exp.Subquery):
        return _path_has_group(anchor, cte, visited, depth + 1)
    if isinstance(anchor, exp.Table):
        name = anchor.name.lower()
        if name in cte:
            return _path_has_group(cte[name], cte, visited, depth + 1)
        if name in ods_registry() and name not in visited:
            sub = _resolve(name, visited | {name}, depth + 1)
            return bool(sub and sub.aggregated)
    return False


def _resolve(name: str, visited: set[str], depth: int) -> OdsLineage | None:
    reg = ods_registry()
    path = reg.get(name.lower())
    if not path or depth > _MAX_DEPTH:
        return None
    return _resolve_path(path, name.lower(), tuple(sorted(visited)), depth)


@lru_cache(maxsize=256)
def _resolve_path(path: str, name: str, visited_key: tuple[str, ...], depth: int) -> OdsLineage | None:
    tree = _parse_def(path)
    if tree is None:
        return None
    visited = set(visited_key) | {name}
    cte = _cte_map(tree)
    spine = _spine(tree, cte, visited, depth)
    sources, joins, filters = _collect_report(tree, set(cte.keys()))
    aggregated = _path_has_group(tree, cte, visited, depth)   # 구동 경로 집계만(옆다리 lookup 제외)
    chain = [name] + sorted(spine) if spine else [name]
    return OdsLineage(
        table=name,
        spine=spine or frozenset(),
        chain=chain,
        sources=sources,
        joins=joins,
        filters=filters,
        aggregated=aggregated,
    )


def resolve_ods_lineage(table: str) -> OdsLineage | None:
    """ODS 테이블 → 리니지. 비-ODS/미설정/실패/모호 → None(무동작)."""
    name = table.lower()
    if name not in ods_registry():
        return None
    return _resolve(name, set(), 0)


def _lineage_caveat(table: str, lin: OdsLineage, reconciled: bool) -> str:
    """base_tables 차원 caveat(대사 필요 지점) 문구 구성."""
    head = (
        "ODS 집계 경유 — 목적(대상) 동일 추정 · 실데이터 대사 필요"
        if reconciled
        else "ODS 집계 테이블 — 다중/비대응 원천, 실데이터 대사 필요"
    )
    lines = [head]
    if lin.spine:
        lines.append(f"원천 스파인: {', '.join(sorted(s.upper() for s in lin.spine))}")
    lines.append(f"경로: {' → '.join(c.upper() for c in lin.chain)}")
    # 대사 필요 지점 — 섹션([라벨]) + 항목별 `·` 줄로 펼쳐 스캔이 쉽게 한다.
    # (프런트 amber 박스는 white-space:pre-line — 들여쓰기는 접히므로 줄바꿈·글리프로만 계층 표기.)
    sections: list[tuple[str, list[str]]] = []
    if lin.filters:
        sections.append(("적재/필터", list(lin.filters[:5])))
    if lin.joins:
        sections.append(("조인", [
            ", ".join(lin.joins),
            "INNER=매칭 안 되는 행이 빠질 수 있음 · LEFT=대상이 여러 건이면 행이 늘 수 있음",
        ]))
    if lin.aggregated:
        sections.append(("집계 단위 차이", [
            "B는 여러 건을 묶어 집계(GROUP BY)한 결과라, "
            "A(원장·건별)와 세는 단위(행 기준)가 달라 값이 다를 수 있음",
        ]))
    if sections:
        lines.append("대사 필요 지점")
        for label, items in sections:
            lines.append(f"[{label}]")
            lines += [f"· {it}" for it in items]
    lines.append("→ 운영 데이터 대사로 확인 필요")
    return "\n".join(lines)


def reconcile_ods_base(
    only_a: list[str], only_b: list[str], base_a: list[str], base_b: list[str]
) -> tuple[list[str], list[str], list[str]]:
    """한쪽만 읽는 ODS 집계 테이블을 반대편 **원천**으로 귀속. 귀속 성립 시 **양쪽 only 에서 제거**
    (B의 `stlm_ods` 귀속 시 A의 `ias_transaction` 도 상쇄). 반환 (남은 only_a, 남은 only_b, caveat 목록).

    게이트: 정의 없는 테이블은 `resolve_ods_lineage`=None → 현행 그대로. ODS지만 스파인이 반대편에
    없거나 모호 → 차이 유지 + 리니지 caveat(정보). 스파인 ⊆ 반대편 base → 귀속."""
    oa, ob = list(only_a), list(only_b)
    caveats: list[str] = []
    sa, sb = {t.lower() for t in base_a}, {t.lower() for t in base_b}

    for only, remove_from, remove_set in ((ob, "a", sa), (oa, "b", sb)):
        for t in list(only):
            lin = resolve_ods_lineage(t)
            if lin is None:
                continue                                    # 비-ODS → 현행
            if lin.spine and lin.spine <= remove_set:
                only.remove(t)                              # ODS 테이블 제거
                # 대응 원천을 반대편 only 에서도 상쇄
                if remove_from == "a":
                    oa[:] = [x for x in oa if x not in lin.spine]
                else:
                    ob[:] = [x for x in ob if x not in lin.spine]
                caveats.append(_lineage_caveat(t, lin, reconciled=True))
            else:
                caveats.append(_lineage_caveat(t, lin, reconciled=False))  # 유지 + 정보
    return oa, ob, caveats
