"""
Playwright Service - Handles browser automation for Quire form filling.
Extracts webpage fields and fills forms automatically.
"""

from playwright.sync_api import sync_playwright

from inspection_ai.config import (
    DEFAULT_TIMEOUT,
    QUIRE_LOGIN_URL,
    QUIRE_REPORT_URL,
)


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

        self.page.goto(QUIRE_REPORT_URL, wait_until="domcontentloaded")
        self.page.wait_for_timeout(8000)

        try:
            self.page.click("text=Report Tags", timeout=5000)
            self.page.wait_for_timeout(3000)
        except:
            pass

        result = self.page.evaluate("""() => {
            const items = document.querySelectorAll('#outline-navigation-list li.outlineItem');
            const outlineItems = [];
            for (const item of items) {
                const cls = item.className || '';
                const textEl = item.querySelector('a, span, .outline-item-label, .item-label') || item;
                const title = (textEl.textContent || '').trim().replace(/\\s+/g, ' ');

                let indentLevel = 0;
                const match = cls.match(/indent-level-(\\d+)/);
                if (match) indentLevel = parseInt(match[1], 10);

                let sectionType = 'section';
                if (cls.includes('info_table_section')) sectionType = 'info_table';
                else if (cls.includes('report_section')) sectionType = 'report_section';

                outlineItems.push({
                    title: title,
                    indent_level: indentLevel,
                    section_type: sectionType
                });
            }

            const forms = document.querySelectorAll('form');
            const allFields = [];

            for (const form of forms) {
                const formId = form.id || '';

                const inputs = form.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea');
                for (const el of inputs) {
                    let label = '';
                    const id = el.id;
                    if (id) {
                        const lbl = document.querySelector('label[for="' + id + '"]');
                        if (lbl) label = lbl.textContent.trim();
                    }
                    if (!label) {
                        const prev = el.previousElementSibling;
                        if (prev && ['LABEL', 'SPAN', 'DIV', 'TH'].includes(prev.tagName)) {
                            label = prev.textContent.trim();
                        }
                    }
                    if (!label) {
                        const parent = el.parentElement;
                        if (parent && parent.tagName === 'LABEL') label = parent.textContent.trim();
                    }
                    if (!label) {
                        const parentDiv = el.closest('.field, .form-group');
                        if (parentDiv) {
                            const lbl = parentDiv.querySelector('label');
                            if (lbl) label = lbl.textContent.trim();
                        }
                    }
                    if (!label) {
                        const aria = el.getAttribute('aria-label');
                        if (aria) label = aria;
                    }
                    if (!label) label = el.name || el.placeholder || '';

                    const field = {
                        label: label,
                        type: el.tagName.toLowerCase(),
                        name: el.name || '',
                        value: el.value || '',
                        form_id: formId
                    };

                    if (el.tagName === 'SELECT') {
                        const opts = [];
                        for (let i = 0; i < el.options.length; i++) {
                            const val = el.options[i].text.trim();
                            if (val) opts.push(val);
                        }
                        field.options = opts;
                    }

                    if (el.type === 'radio' || el.type === 'checkbox') {
                        const nameAttr = el.name;
                        if (nameAttr) {
                            const siblings = document.querySelectorAll('input[name="' + nameAttr + '"]');
                            if (siblings.length > 1 && siblings[0] === el) {
                                const options = [];
                                for (let i = 0; i < siblings.length; i++) {
                                    const sib = siblings[i];
                                    let optLabel = '';
                                    const sid = sib.id;
                                    if (sid) {
                                        const lbl = document.querySelector('label[for="' + sid + '"]');
                                        if (lbl) optLabel = lbl.textContent.trim();
                                    }
                                    if (!optLabel) {
                                        const nextLbl = sib.nextElementSibling;
                                        if (nextLbl && nextLbl.tagName === 'LABEL') optLabel = nextLbl.textContent.trim();
                                    }
                                    options.push({
                                        label: optLabel || sib.value || '',
                                        value: sib.value,
                                        selected: sib.checked
                                    });
                                }
                                field.radio_options = options;
                            } else if (siblings.length === 1) {
                                field.checked = el.checked;
                            }
                        } else {
                            field.checked = el.checked;
                        }
                    }

                    allFields.push(field);
                }
            }

            const reportTags = [];
            const allTagElements = document.querySelectorAll('*');
            for (const el of allTagElements) {
                const className = (el.className || '').toLowerCase();
                const id = (el.id || '').toLowerCase();
                const textContent = (el.textContent || '').toLowerCase();

                if (className.includes('tag') || id.includes('tag') ||
                    el.querySelector('input[name*="tag"], select[name*="tag"]') ||
                    (el.tagName === 'INPUT' && (el.name || '').toLowerCase().includes('tag')) ||
                    (el.tagName === 'SELECT' && (el.name || '').toLowerCase().includes('tag'))) {

                    const tagInputs = el.tagName === 'INPUT' || el.tagName === 'SELECT'
                        ? [el]
                        : el.querySelectorAll('input[name*="tag"], select[name*="tag"]');

                    for (const tagEl of tagInputs) {
                        let tagLabel = '';
                        const tagId = tagEl.id;
                        if (tagId) {
                            const lbl = document.querySelector('label[for="' + tagId + '"]');
                            if (lbl) tagLabel = lbl.textContent.trim();
                        }
                        if (!tagLabel) {
                            const prev = tagEl.previousElementSibling;
                            if (prev && ['LABEL', 'SPAN', 'DIV'].includes(prev.tagName)) {
                                tagLabel = prev.textContent.trim();
                            }
                        }
                        if (!tagLabel) tagLabel = tagEl.name || tagEl.placeholder || tagEl.getAttribute('data-label') || '';

                        const tagField = {
                            label: tagLabel,
                            type: tagEl.tagName.toLowerCase(),
                            name: tagEl.name || '',
                            value: tagEl.value || ''
                        };

                        if (tagEl.tagName === 'SELECT' && tagEl.options) {
                            const opts = [];
                            for (let i = 0; i < tagEl.options.length; i++) {
                                const val = tagEl.options[i].text.trim();
                                if (val) opts.push(val);
                            }
                            tagField.options = opts;
                        }

                        if (!reportTags.some(t => t.name === tagField.name && t.value === tagField.value)) {
                            reportTags.push(tagField);
                        }
                    }
                }
            }

            return { outline: outlineItems, fields: allFields, tags: reportTags };
        }""")

        return result

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
