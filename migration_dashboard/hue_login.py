"""Hue 로그인 세션 저장 (id/pw 방식일 때만 1회 실행).

🔒 이 스크립트는 **로그인 페이지에서만** 폼을 제출(인증)하고, 인증된 세션을 hue_auth.json에 저장한다.
이후 데이터 수집은 sync_hue_comments.py가 그 세션을 재사용해 **읽기 전용**으로만 동작한다.
쿠키 방식(HUE_SESSIONID)을 쓰면 이 스크립트는 필요 없다(로그인 POST 자체가 없음 — 가장 안전).

실행:  python hue_login.py            # 헤드리스 로그인 후 hue_auth.json 저장
       python hue_login.py --show     # 브라우저를 띄워 직접 로그인(2FA 등)
"""
from __future__ import annotations

import argparse

from hue_common import load_config, AUTH_STATE


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true", help="브라우저 표시(직접 로그인)")
    args = ap.parse_args()

    cfg = load_config()
    raw = (cfg.get("HUE_URL", "") or "").strip()
    user, pw = cfg.get("HUE_USERNAME", ""), cfg.get("HUE_PASSWORD", "")
    if not raw:
        raise SystemExit("HUE_URL 미설정")
    from urllib.parse import urlparse
    pu = urlparse(raw)
    base = f"{pu.scheme}://{pu.netloc}"

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show)
        ctx = browser.new_context(ignore_https_errors=True)  # 사내 self-signed 대응
        page = ctx.new_page()
        page.goto(base + "/hue/accounts/login/", wait_until="domcontentloaded", timeout=20000)
        if args.show:
            print("브라우저에서 직접 로그인하세요. 로그인 완료 후 이 창에서 Enter…")
            try:
                input()
            except EOFError:
                page.wait_for_timeout(60000)
        else:
            if not (user and pw):
                raise SystemExit("HUE_USERNAME/HUE_PASSWORD 미설정 — 또는 --show로 직접 로그인")
            # 로그인 페이지에서만 폼 입력·제출(유일하게 허용된 상호작용 = 인증)
            for sel in ["input[name=username]", "#id_username", "input[type=text]"]:
                if page.query_selector(sel):
                    page.fill(sel, user); break
            for sel in ["input[name=password]", "#id_password", "input[type=password]"]:
                if page.query_selector(sel):
                    page.fill(sel, pw); break
            page.click("button[type=submit], input[type=submit]")
            page.wait_for_load_state("networkidle", timeout=20000)

        ctx.storage_state(path=str(AUTH_STATE))
        browser.close()
    print(f"세션 저장 완료 → {AUTH_STATE}  (이제 python sync_hue_comments.py 실행)")


if __name__ == "__main__":
    main()
