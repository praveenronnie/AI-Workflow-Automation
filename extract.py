"""
Extract all fields and dropdown list options from Quire report page.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from collections import OrderedDict
from inspection_ai.config import QUIRE_EMAIL, QUIRE_PASSWORD, QUIRE_REPORT_URL
from playwright.sync_api import sync_playwright
from inspection_ai.services.playwright_js import EXTRACT_FIELDS_JS

URL = QUIRE_REPORT_URL
EMAIL = QUIRE_EMAIL
PASSWORD = QUIRE_PASSWORD
OUTPUT_FILE = "output.json"


def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.set_default_timeout(60000)

        print("Logging in...")
        page.goto("https://app.openquire.com/login", wait_until="networkidle")
        page.evaluate(
            """(creds) => {
                const email = document.querySelector("input[name='user_identifier']");
                const pass = document.querySelector("input[name='password']");
                if (email) { email.value = creds[0]; email.dispatchEvent(new Event('input', {bubbles: true})); }
                if (pass) { pass.value = creds[1]; pass.dispatchEvent(new Event('input', {bubbles: true})); }
            }""",
            [EMAIL, PASSWORD],
        )
        page.evaluate(
            """() => { const form = document.querySelector('form'); if(form) form.submit(); }"""
        )
        page.wait_for_timeout(5000)

        print("Navigating to report...")
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(8000)
        print(f"Page title: {page.title()}")

        print("Extracting structure...")

        try:
            page.click("text=Report Tags", timeout=5000)
            page.wait_for_timeout(3000)
        except:
            pass

        result = page.evaluate(EXTRACT_FIELDS_JS)

        outline_items = result["outline"]
        all_fields = result["fields"]
        report_tags = result.get("tags", [])
        print(
            f"Found {len(outline_items)} outline items, {len(all_fields)} fields, {len(report_tags)} tags"
        )

        hierarchical = _build_hierarchy(outline_items)

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
            form_groups = OrderedDict()
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

        output = {
            "hierarchical_structure": hierarchical,
            "all_fields_flat": all_fields,
            "report_tags": report_tags,
        }

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"Extraction complete. Output saved to {OUTPUT_FILE}")
        print(f"Sections: {len(outline_items)} outline items + metadata + item groups")
        print(
            f"Fields: {len(report_fields)} report fields + {len(item_fields)} item fields = {len(all_fields)} total"
        )

        page.wait_for_timeout(2000)
        browser.close()


def _build_hierarchy(outline):
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


if __name__ == "__main__":
    run()
