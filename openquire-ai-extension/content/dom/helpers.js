// DOM helpers for form field traversal and event dispatch

/**
 * Dispatch native events on an element after programmatic value changes.
 * @param {HTMLElement} element
 */
function dispatchFillEvents(element) {
  FILL_EVENTS.forEach((eventType) => {
    element.dispatchEvent(
      new Event(eventType, { bubbles: true, cancelable: true }),
    );
  });
}

/**
 * Find the closest label for a given form element.
 * Resolution order:
 * 1. aria-label
 * 2. aria-labelledby
 * 3. label[for=id]
 * 4. parent label
 * 5. sibling label
 * 6. nearest text sibling
 * 7. nearest ancestor text
 * 8. placeholder
 * 9. name attribute
 * @param {HTMLElement} element
 * @returns {string}
 */
function resolveLabel(element) {
  // 1. aria-label
  if (element.hasAttribute("aria-label")) {
    return element.getAttribute("aria-label");
  }

  // 2. aria-labelledby
  const labelledBy = element.getAttribute("aria-labelledby");
  if (labelledBy) {
    const labelEl = document.getElementById(labelledBy);
    if (labelEl) return labelEl.textContent.trim();
  }

  // 3. associated <label>
  let id = element.id;
  if (!id) {
    // Label may point to wrapper div; check nearest ancestor with id
    const ancestorWithId = element.closest("[id]");
    if (ancestorWithId) id = ancestorWithId.id;
  }
  if (id) {
    const label = document.querySelector(`label[for="${id}"]`);
    if (label) return label.textContent.trim();
  }

  // 4. parent label - filter out form field text to avoid picking up option values
  const parentLabel = element.closest("label");
  if (parentLabel) {
    const clone = parentLabel.cloneNode(true);
    const childFields = clone.querySelectorAll(
      'input, select, textarea, [role="textbox"], [role="combobox"], [role="checkbox"], [role="radio"]',
    );
    childFields.forEach((field) => field.remove());
    const labelText = clone.textContent.trim();
    if (labelText) return labelText;
  }

  // 5. preceding sibling label
  const prev = element.previousElementSibling;
  if (prev && prev.tagName === "LABEL") {
    return prev.textContent.trim();
  }

  // 6. nearest text sibling - skip containers with option values and value displays
  let sibling = element.previousSibling;
  while (sibling) {
    if (sibling.nodeType === Node.TEXT_NODE && sibling.textContent.trim()) {
      return sibling.textContent.trim();
    }
    if (sibling.nodeType === Node.ELEMENT_NODE) {
      // Skip option containers
      const isInsideOptionContainer = sibling.closest(
        "ul, ol, dl, select, [role='listbox'], [role='combobox']",
      );
      if (isInsideOptionContainer) {
        sibling = sibling.previousSibling;
        continue;
      }
      // Skip selected-value display spans
      if (
        sibling.classList.contains("tag-value-width") ||
        sibling.classList.contains("selected-value") ||
        sibling.getAttribute("role") === "alert"
      ) {
        sibling = sibling.previousSibling;
        continue;
      }
      const text = sibling.textContent.trim();
      if (text) return text;
    }
    sibling = sibling.previousSibling;
  }

  // 7. nearest ancestor text - skip option/list containers
  let current = element.parentElement;
  while (current && current !== document.body) {
    const isOptionContainer = current.matches(
      "ul, ol, dl, select, [role='listbox'], [role='combobox']",
    );
    if (!isOptionContainer) {
      const textNode = Array.from(current.childNodes).find(
        (n) =>
          n.nodeType === Node.TEXT_NODE &&
          n.textContent.trim() &&
          !n.parentElement.closest("ul, ol, dl, select, [role='listbox']"),
      );
      if (textNode) return textNode.textContent.trim();
    }
    current = current.parentElement;
  }

  // 8. placeholder
  const placeholder = element.getAttribute("placeholder");
  if (placeholder) return placeholder;

  // 9. name attribute
  return element.getAttribute("name") || "";
}

/**
 * Generate a stable CSS selector for an element using its attributes.
 * Priority order:
 * 1. id
 * 2. data-testid
 * 3. data-field-id
 * 4. name
 * 5. aria-label
 * 6. generated CSS path
 * @param {HTMLElement} element
 * @returns {string}
 */
function generateSelector(element) {
  const tag = element.tagName.toLowerCase();

  // 1. id
  if (element.id) return `#${element.id}`;

  // 2. data-testid
  const testId = element.getAttribute("data-testid");
  if (testId) return `${tag}[data-testid="${testId}"]`;

  // 3. data-field-id
  const fieldId = element.getAttribute("data-field-id");
  if (fieldId) return `${tag}[data-field-id="${fieldId}"]`;

  const parent = element.parentElement;
  const siblings = parent
    ? Array.from(parent.children).filter((c) => c.tagName === element.tagName)
    : [];

  const index = siblings.indexOf(element);
  const nth = siblings.length > 1 ? `:nth-of-type(${index + 1})` : "";

  // 4. name
  const name = element.getAttribute("name");
  if (name) return `${tag}[name="${name}"]${nth}`;

  // 5. aria-label
  const ariaLabel = element.getAttribute("aria-label");
  if (ariaLabel) return `${tag}[aria-label="${ariaLabel}"]${nth}`;

  // 6. generated CSS path (avoid random classes)
  const stableClasses = Array.from(element.classList)
    .filter(
      (cls) => !cls.match(/^[a-z]/) || cls.includes("-") || cls.includes("_"),
    )
    .slice(0, 2);
  if (stableClasses.length > 0) {
    return `${tag}.${stableClasses.join(".")}${nth}`;
  }

  return `${tag}${nth}`;
}

/**
 * Get current value from a form element respecting its type.
 * @param {HTMLElement} element
 * @returns {string}
 */
function getCurrentValue(element) {
  if (element.type === "checkbox")
    return element.checked ? "checked" : "unchecked";
  if (element.type === "radio") {
    const name = element.getAttribute("name");
    if (name) {
      const checked = document.querySelector(`input[name="${name}"]:checked`);
      return checked ? checked.value : "";
    }
    return element.checked ? element.value : "";
  }
  return element.value || "";
}

/**
 * Transform value based on field type and format hints.
 * @param {*} value
 * @param {string} fieldType
 * @param {string} formatHint - 'date', 'currency', 'number'
 * @returns {*}
 */
function transformValue(value, fieldType, formatHint) {
  if (value === undefined || value === null) return value;

  // Date transformation
  if (formatHint === "date" || fieldType === "date") {
    if (typeof value === "string") {
      // Try to parse various date formats
      const date = new Date(value);
      if (!isNaN(date.getTime())) {
        return date.toISOString().split("T")[0]; // YYYY-MM-DD
      }
    }
  }

  // Currency transformation
  if (formatHint === "currency") {
    if (typeof value === "string") {
      // Remove currency symbols and commas
      const num = parseFloat(value.replace(/[$,]/g, ""));
      if (!isNaN(num)) {
        return num.toFixed(2);
      }
    }
  }

  // Number transformation
  if (formatHint === "number") {
    if (typeof value === "string") {
      const num = parseFloat(value.replace(/[,]/g, ""));
      if (!isNaN(num)) {
        return num;
      }
    }
  }

  return value;
}

/**
 * Flatten nested object for mapping.
 * @param {object} obj
 * @param {string} prefix
 * @returns {object}
 */
function flattenObject(obj, prefix = "") {
  const result = {};

  Object.entries(obj).forEach(([key, value]) => {
    const newKey = prefix ? `${prefix}.${key}` : key;

    if (value && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(result, flattenObject(value, newKey));
    } else if (Array.isArray(value)) {
      // Convert array to indexed keys
      value.forEach((item, index) => {
        if (item && typeof item === "object") {
          Object.assign(result, flattenObject(item, `${newKey}[${index}]`));
        } else {
          result[`${newKey}[${index}]`] = item;
        }
      });
    } else {
      result[newKey] = value;
    }
  });

  return result;
}
