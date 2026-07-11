"""
Shared JavaScript for field extraction in Playwright services.
"""

EXTRACT_FIELDS_JS = """
() => {
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
}
"""
