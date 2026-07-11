"""
Async wrapper for Playwright extraction of Quire report page.
"""

import asyncio

from playwright.async_api import async_playwright

from inspection_ai.config import QUIRE_LOGIN_URL
from inspection_ai.services.playwright_js import EXTRACT_FIELDS_JS


class AsyncExtractService:
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    async def extract(self, report_url: str) -> dict:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            page.set_default_timeout(60000)

            await self._login(page)
            await self._navigate_to_report(page, report_url)
            result = await self._extract_structure(page)
            await browser.close()

            return result

    async def _login(self, page):
        await page.goto(QUIRE_LOGIN_URL, wait_until="networkidle")
        await page.evaluate(
            """(creds) => {
                const email = document.querySelector("input[name='user_identifier']");
                const pass = document.querySelector("input[name='password']");
                if (email) { email.value = creds[0]; email.dispatchEvent(new Event('input', {bubbles: true})); }
                if (pass) { pass.value = creds[1]; pass.dispatchEvent(new Event('input', {bubbles: true})); }
            }""",
            [self.email, self.password],
        )
        await page.evaluate(
            """() => { const form = document.querySelector('form'); if(form) form.submit(); }"""
        )
        await page.wait_for_timeout(5000)

    async def _navigate_to_report(self, page, report_url: str):
        await page.goto(report_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(8000)

    async def _extract_structure(self, page) -> dict:
        result = await page.evaluate(EXTRACT_FIELDS_JS)

        outline_items = result["outline"]
        all_fields = result["fields"]
        report_tags = result.get("tags", [])

        hierarchical = self._build_hierarchy(outline_items)

        report_fields = [f for f in all_fields if f["form_id"] == "edit_report_1762900"]
        item_fields = [f for f in all_fields if f["form_id"] != "edit_report_1762900"]

        report_info_node = {
            "title": "Report Information",
            "section_type": "metadata",
            "fields": report_fields,
            "children": [],
        }
        hierarchical["children"].insert(0, report_info_node)

        if item_fields:
            form_groups = {}
            for f in item_fields:
                fid = f["form_id"]
                if fid not in form_groups:
                    form_groups[fid] = []
                form_groups[fid].append(f)

            item_section = {
                "title": "Condition Action Items",
                "section_type": "data_items",
                "fields": [],
                "children": [],
            }

            for fid, flds in form_groups.items():
                item_num = fid.replace("edit_quire_condition_action_item_", "")
                sub = {
                    "title": f"Action Item {item_num}",
                    "section_type": "action_item",
                    "fields": flds,
                    "children": [],
                }
                item_section["children"].append(sub)

            hierarchical["children"].append(item_section)

        return {
            "hierarchical_structure": hierarchical,
            "all_fields_flat": all_fields,
            "report_tags": report_tags,
        }

    def _build_hierarchy(self, outline: list) -> dict:
        root = {"title": "Report Sections", "children": []}
        stack = [root]

        for item in outline:
            level = item["indent_level"]
            node = {
                "title": item["title"],
                "section_type": item["section_type"],
                "fields": [],
                "children": [],
            }

            while len(stack) > level + 1:
                stack.pop()

            while len(stack) <= level:
                parent = stack[-1]
                intermediate = {"title": "", "children": []}
                parent["children"].append(intermediate)
                stack.append(intermediate)

            parent = stack[-1]
            parent["children"].append(node)
            stack.append(node)

        return root
