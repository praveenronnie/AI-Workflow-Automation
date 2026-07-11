"""
Playwright Service - Handles browser automation for Quire form filling.
"""

from playwright.sync_api import sync_playwright

from inspection_ai.config import DEFAULT_TIMEOUT, QUIRE_LOGIN_URL
from inspection_ai.services.playwright_js import EXTRACT_FIELDS_JS


class PlaywrightService:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.browser = None
        self.context = None
        self.page = None

    def login(self) -> bool:
        if not self.page:
            raise RuntimeError("Browser not initialized. Call launch() first.")

        self.page.goto(QUIRE_LOGIN_URL, wait_until="networkidle")
        self.page.evaluate(
            """(creds) => {
                const email = document.querySelector("input[name='user_identifier']");
                const pass = document.querySelector("input[name='password']");
                if (email) { email.value = creds[0]; email.dispatchEvent(new Event('input', {bubbles: true})); }
                if (pass) { pass.value = creds[1]; pass.dispatchEvent(new Event('input', {bubbles: true})); }
            }""",
            [self.email, self.password],
        )
        self.page.evaluate(
            """() => { const form = document.querySelector('form'); if(form) form.submit(); }"""
        )
        self.page.wait_for_timeout(5000)
        return True

    def extract_fields(self) -> dict:
        if not self.page:
            raise RuntimeError("Browser not initialized. Call launch() first.")

        self.page.goto(
            "https://app.openquire.com/reports/1762900", wait_until="domcontentloaded"
        )
        self.page.wait_for_timeout(8000)

        try:
            self.page.click("text=Report Tags", timeout=5000)
            self.page.wait_for_timeout(3000)
        except:
            pass

        return self.page.evaluate(EXTRACT_FIELDS_JS)

    def fill_form(self, mapped_data: dict) -> bool:
        if not self.page:
            raise RuntimeError("Browser not initialized. Call launch() first.")

        for field_name, field_value in mapped_data.items():
            try:
                selector = f"[name='{field_name}']"
                if self.page.is_visible(selector):
                    self.page.fill(selector, str(field_value))
            except:
                pass

        return True

    def launch(self, headless: bool = True) -> None:
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080}
        )
        self.page = self.context.new_page()
        self.page.set_default_timeout(DEFAULT_TIMEOUT)

    def close(self) -> None:
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()
