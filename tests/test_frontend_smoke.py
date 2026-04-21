#!/usr/bin/env python3
"""
Frontend-Smoketest (Playwright / Chromium headless).

Prueft dass das React-Frontend unter http://localhost:8080/app tatsaechlich
rendert (kein schwarzer/leerer Bildschirm). Fangt die Class of Bugs, die
Grep-basierte Python-Tests nicht sehen koennen:
  - JS-Runtime-Fehler beim Mount (z.B. fehlender Context-Provider)
  - 404 auf Assets / CSS
  - React-Router-Config-Probleme
  - CSS-Ladefehler, die zu #root-Leere fuehren

Nutzung:
    python3 tests/test_frontend_smoke.py             # default URL
    python3 tests/test_frontend_smoke.py --url X     # andere URL pruefen
    python3 tests/test_frontend_smoke.py --quiet     # nur Summary-Output

Exit-Code: 0 = alle Checks OK, 1 = mindestens ein Fehler.

Voraussetzung: `python3 -m pip install --user playwright` und einmalig
`python3 -m playwright install chromium`.
"""

import argparse
import sys

DEFAULT_URL = "http://localhost:8080/app"
RENDER_TIMEOUT_MS = 5000  # so lange warten wir auf ein non-empty #root
PAGE_LOAD_TIMEOUT_MS = 10000


class Colors:
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright, Error as PwError
    except ImportError:
        print(
            f"{Colors.RED}✗ playwright nicht installiert.{Colors.RESET}\n"
            "  Installation: python3 -m pip install --user playwright "
            "&& python3 -m playwright install chromium",
            file=sys.stderr,
        )
        return 2

    console_errors: list[str] = []
    page_errors: list[str] = []
    failed_requests: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.on(
            "console",
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error"
            else None,
        )
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))
        page.on(
            "requestfailed",
            lambda req: failed_requests.append(
                f"{req.method} {req.url} — {req.failure}"
            ),
        )
        # Auch HTTP-Fehler-Responses (404/500) mitloggen, sonst sehen wir kaputte Assets nicht
        page.on(
            "response",
            lambda resp: failed_requests.append(
                f"HTTP {resp.status} {resp.url}"
            )
            if resp.status >= 400
            else None,
        )

        try:
            page.goto(args.url, timeout=PAGE_LOAD_TIMEOUT_MS, wait_until="load")
        except PwError as e:
            print(
                f"{Colors.RED}✗ Seite konnte nicht geladen werden: {e}{Colors.RESET}"
            )
            browser.close()
            return 1

        # Warten bis #root mindestens 1 child hat (React gemounted)
        try:
            page.wait_for_function(
                """() => {
                    const el = document.getElementById('root');
                    return el && el.children.length > 0;
                }""",
                timeout=RENDER_TIMEOUT_MS,
            )
            rendered = True
        except PwError:
            rendered = False

        # Body-Hoehe messen — zweiter Sanity-Check
        try:
            body_height = page.evaluate("() => document.body.offsetHeight")
        except PwError:
            body_height = 0

        title = page.title() or "(kein Title)"
        browser.close()

    # ── Auswertung ────────────────────────────────────────────────────────────
    print(f"\n{Colors.BOLD}Frontend-Smoketest — {args.url}{Colors.RESET}")
    print(f"  Title: {title}")
    print(f"  body.offsetHeight: {body_height}px")

    checks: list[tuple[str, bool, str]] = []
    checks.append(
        (
            "React hat in #root gerendert",
            rendered,
            f"#root blieb {RENDER_TIMEOUT_MS}ms lang leer",
        )
    )
    checks.append(
        (
            "body hat nicht-triviale Hoehe",
            body_height > 50,
            f"body.offsetHeight={body_height}px (<=50 deutet auf unsichtbare UI)",
        )
    )
    checks.append(
        (
            "keine JS-Console-Errors",
            not console_errors,
            f"{len(console_errors)} Error(s): "
            + "; ".join(console_errors[:3])
            + (" …" if len(console_errors) > 3 else ""),
        )
    )
    checks.append(
        (
            "keine uncaught Page-Errors",
            not page_errors,
            f"{len(page_errors)} Error(s): "
            + "; ".join(page_errors[:3])
            + (" …" if len(page_errors) > 3 else ""),
        )
    )
    checks.append(
        (
            "keine fehlgeschlagenen Requests",
            not failed_requests,
            f"{len(failed_requests)} Request(s): "
            + "; ".join(failed_requests[:3])
            + (" …" if len(failed_requests) > 3 else ""),
        )
    )

    all_pass = all(ok for _, ok, _ in checks)
    if not args.quiet:
        print()
        for label, ok, detail in checks:
            if ok:
                print(f"  {Colors.GREEN}✓{Colors.RESET} {label}")
            else:
                print(f"  {Colors.RED}✗{Colors.RESET} {label}")
                print(f"      {Colors.YELLOW}{detail}{Colors.RESET}")

    print()
    if all_pass:
        print(
            f"{Colors.GREEN}{Colors.BOLD}✓ Frontend-Smoketest bestanden{Colors.RESET}"
        )
        return 0
    else:
        print(
            f"{Colors.RED}{Colors.BOLD}✗ Frontend-Smoketest fehlgeschlagen{Colors.RESET}"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
