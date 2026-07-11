"""
Async wrapper for Playwright extraction of Quire report page.
Extracts all fields and dropdown options preserving hierarchical order.
"""

import asyncio
import json
from typing import Optional

from playwright.async_api import async_playwright

from inspection_ai.config import QUIRE_LOGIN_URL


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
        result = await page.evaluate("""() => {
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

            // Extract Report Tags section
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
