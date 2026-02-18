import os
import random
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

KSEF_URL = "https://ap.ksef.mf.gov.pl/web/"
REDIRECT_RE = re.compile(r"(podpis\.gov\.pl|login\.gov\.pl)", re.I)
WAIT_TIMEOUT_SEC = 20
DEBUG = os.getenv("KSEF_DEBUG") == "1"
DEBUG_DIR = Path(os.getenv("KSEF_DEBUG_DIR", "debug"))


def log(msg: str) -> None:
    print(f"[ksef] {msg}")


def debug(msg: str) -> None:
    if DEBUG:
        print(f"[ksef][debug] {msg}")


def dump_debug_state(page, label: str) -> None:
    if not DEBUG:
        return
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_") or "state"
    html_path = DEBUG_DIR / f"{safe_label}.html"
    png_path = DEBUG_DIR / f"{safe_label}.png"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
        debug(f"zapisano HTML: {html_path}")
    except Exception as exc:
        debug(f"nie udalo sie zapisac HTML: {exc}")
    try:
        page.screenshot(path=str(png_path), full_page=True)
        debug(f"zapisano screenshot: {png_path}")
    except Exception as exc:
        debug(f"nie udalo sie zapisac screenshot: {exc}")


def random_nip() -> str:
    weights = (6, 5, 7, 2, 3, 4, 5, 6, 7)
    while True:
        digits = [random.randint(0, 9) for _ in range(9)]
        check_sum = sum(d * w for d, w in zip(digits, weights)) % 11
        if check_sum == 10:
            continue
        digits.append(check_sum)
        return "".join(str(d) for d in digits)


def safe_response_text(resp) -> str:
    try:
        text = resp.text()
        text = text.strip()
        return text if text else "<empty body>"
    except Exception:
        return "<unable to read response body>"


def find_visible_by_pattern(page, pattern: re.Pattern):
    for frame in page.frames:
        candidates = [
            frame.get_by_role("button", name=pattern).first,
            frame.get_by_role("link", name=pattern).first,
            frame.get_by_text(pattern).first,
        ]
        for loc in candidates:
            try:
                if loc.is_visible(timeout=500):
                    return loc
            except Exception:
                continue
    return None


def find_nip_input(page):
    for frame in page.frames:
        try:
            locator = frame.get_by_placeholder("Wpisz NIP firmy").first
            if locator.is_visible(timeout=500):
                return locator
        except Exception:
            continue
    return None


def maybe_switch_to_new_page(context, current_page, timeout_ms=3000):
    try:
        new_page = context.wait_for_event("page", timeout=timeout_ms)
        new_page.wait_for_load_state("domcontentloaded")
        return new_page
    except Exception:
        # jeśli strona już się otworzyła zanim zaczęliśmy czekać
        pages = context.pages
        if pages and pages[-1] is not current_page:
            try:
                pages[-1].wait_for_load_state("domcontentloaded")
            except Exception:
                pass
            return pages[-1]
        return None


def any_page_with_url(context, pattern: re.Pattern):
    for p in context.pages:
        try:
            if pattern.search(p.url or ""):
                return p
        except Exception:
            continue
    return None


def wait_for_redirect_or_error(context, page):
    bad = {}
    console_err = {}

    def on_response(resp):
        if resp.status == 400 and "body" not in bad:
            bad["url"] = resp.url
            bad["body"] = safe_response_text(resp)

    def on_console(msg):
        if msg.type == "error" and "text" not in console_err:
            console_err["text"] = msg.text

    page.on("response", on_response)
    page.on("console", on_console)

    start = time.monotonic()
    try:
        while time.monotonic() - start < WAIT_TIMEOUT_SEC:
            redirected = any_page_with_url(context, REDIRECT_RE)
            if redirected or REDIRECT_RE.search(page.url or ""):
                return {"type": "redirect", "page": redirected or page}
            if "body" in bad:
                return {"type": "bad", "url": bad.get("url", "<unknown>"), "body": bad["body"]}
            if "text" in console_err:
                return {"type": "bad", "url": "<console>", "body": console_err["text"]}
            page.wait_for_timeout(200)
    finally:
        page.remove_listener("response", on_response)
        page.remove_listener("console", on_console)

    return {
        "type": "bad",
        "url": "<timeout>",
        "body": f"Brak przekierowania na podpis.gov.pl ani błędu w {WAIT_TIMEOUT_SEC}s",
    }


def click_optional_action(page):
    action_pattern = re.compile(r"(Dalej|Kontynuuj|Zaloguj|Przejdź|Potwierdź)", re.I)
    loc = find_visible_by_pattern(page, action_pattern)
    if loc:
        try:
            loc.click()
            debug("kliknięto przycisk akcji po NIP")
            return True
        except Exception:
            return False
    return False


def test_step2_click_auth_sees_trusted_profile():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        try:
            page = context.new_page()
            response = page.goto(KSEF_URL, wait_until="domcontentloaded")
            status = response.status if response else "no response"
            log(f"HTTP status: {status}")
            debug(f"url po wejściu: {page.url}")
            debug(f"tytul: {page.title()}")

            auth_pattern = re.compile(r"Uwierzytelnij\s+się\s+w\s+Krajowym\s+Systemie", re.I)
            header = page.locator("h2", has_text=auth_pattern).first
            header.wait_for(state="visible", timeout=15000)
            log("OK: widoczny nagłówek h2 'Uwierzytelnij się w Krajowym Systemie'")

            clicked = False
            try:
                header.click()
                clicked = True
                debug("kliknięto h2")
            except Exception:
                pass
            if not clicked:
                loc = find_visible_by_pattern(page, auth_pattern)
                if not loc:
                    raise AssertionError("Nie znaleziono elementu do kliknięcia dla 'Uwierzytelnij się w Krajowym Systemie'")
                loc.click()
                debug("kliknięto przycisk/link z tekstem 'Uwierzytelnij się w Krajowym Systemie'")

            active_page = maybe_switch_to_new_page(context, page) or page
            if active_page is not page:
                debug("otwarto nową stronę po kliknięciu")
            active_page.wait_for_load_state("domcontentloaded")

            trusted_pattern = re.compile(r"Zaloguj\s+profilem\s+zaufanym", re.I)
            trusted = find_visible_by_pattern(active_page, trusted_pattern)
            if not trusted:
                dump_debug_state(active_page, "step2_no_trusted_button")
                raise AssertionError("Nie znaleziono przycisku 'Zaloguj profilem zaufanym'")
            log("OK: widoczny przycisk 'Zaloguj profilem zaufanym'")

            trusted.click()
            debug("kliknięto 'Zaloguj profilem zaufanym'")
            active_page = maybe_switch_to_new_page(context, active_page) or active_page
            active_page.wait_for_load_state("domcontentloaded")

            nip_input = find_nip_input(active_page)
            if not nip_input:
                dump_debug_state(active_page, "step3_no_nip_input")
                raise AssertionError("Nie znaleziono pola z placeholderem 'Wpisz NIP firmy'")
            log("OK: widoczne pole z placeholderem 'Wpisz NIP firmy'")

            nip = random_nip()
            nip_input.fill(nip)
            debug(f"wpisano NIP: {nip}")
            try:
                nip_input.press("Enter")
                debug("wciśnięto Enter w polu NIP")
            except Exception:
                pass
            click_optional_action(active_page)

            outcome = wait_for_redirect_or_error(context, active_page)
            if outcome["type"] == "redirect":
                debug(f"przekierowano na: {outcome['page'].url}")
                dump_debug_state(outcome["page"], "step4_redirect")
                log("Logowanie po PZ ok")
                return

            raise AssertionError(f"[ksef] błąd z konsoli: {outcome['body']}")
        except Exception:
            dump_debug_state(page, "step3_fail")
            raise
        finally:
            context.close()
            browser.close()
