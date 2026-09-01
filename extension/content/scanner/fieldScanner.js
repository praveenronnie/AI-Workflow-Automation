// Field scanner - detects form fields within sections

/**
 * Generate a deterministic field ID based on section, label, and selector.
 * This ensures stable IDs across scans and page refreshes.
 * @param {string} sectionName
 * @param {string} fieldName
 * @param {string} selector
 * @returns {string}
 */
function generateFieldId(sectionName, fieldName, selector) {
  // Create a stable hash from section + field + selector + type to avoid collisions
  const combined = `${sectionName}|${fieldName}|${selector}`;
  let hash = 0;
  for (let i = 0; i < combined.length; i++) {
    const char = combined.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  // Convert to 8-character hex string
  return `field_${Math.abs(hash).toString(16).padStart(8, "0").slice(0, 8)}`;
}

/**
 * Generate qualified label with section context.
 * @param {string} sectionName
 * @param {string} fieldName
 * @returns {string}
 */
function getQualifiedLabel(sectionName, fieldName) {
  if (
    !sectionName ||
    sectionName === "Untitled Section" ||
    sectionName === "General"
  ) {
    return fieldName;
  }
  return `${sectionName} > ${fieldName}`;
}

/**
 * Check if element is required.
 * @param {HTMLElement} el
 * @returns {boolean}
 */
function isFieldRequired(el) {
  return (
    el.hasAttribute("required") || el.getAttribute("aria-required") === "true"
  );
}

/**
 * Get placeholder text from element.
 * @param {HTMLElement} el
 * @returns {string}
 */
function getPlaceholder(el) {
  return el.getAttribute("placeholder") || "";
}

/**
 * Get help text from aria-describedby or nearby elements.
 * @param {HTMLElement} el
 * @returns {string}
 */
function getHelpText(el) {
  const describedBy = el.getAttribute("aria-describedby");
  if (describedBy) {
    const helpEl = document.getElementById(describedBy);
    if (helpEl) return helpEl.textContent.trim();
  }

  // Check for sibling help text
  const parent = el.parentElement;
  if (parent) {
    const siblings = Array.from(parent.children);
    const elIndex = siblings.indexOf(el);
    for (let i = elIndex + 1; i < siblings.length; i++) {
      const sibling = siblings[i];
      if (
        sibling.classList.contains("help-text") ||
        sibling.classList.contains("form-text") ||
        (sibling.hasAttribute("role") &&
          sibling.getAttribute("role") === "alert")
      ) {
        return sibling.textContent.trim();
      }
    }
  }

  return "";
}

/**
 * Group radio buttons by name attribute.
 * @param {NodeList} radioElements
 * @param {string} sectionName
 * @returns {Array}
 */
function groupRadios(radioElements, sectionName) {
  const groups = {};

  radioElements.forEach((el) => {
    const name = el.getAttribute("name");
    if (!name) return;

    if (!groups[name]) {
      groups[name] = {
        element: el,
        options: [],
      };
    }
    groups[name].options.push(el);
  });

  const fields = [];
  Object.entries(groups).forEach(([name, group]) => {
    const el = group.element;
    const options = group.options.map((radio) => {
      const label = resolveLabel(radio);
      return label || radio.value;
    });

    const fieldName = resolveLabel(el) || name;
    const selector = generateSelector(el);
    fields.push({
      field_id: generateFieldId(sectionName, fieldName, selector),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: FIELD_TYPES.RADIO,
      current_value: getCurrentValue(el),
      options: options,
      selector: selector,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    });
  });

  return fields;
}

/**
 * Group checkboxes by name attribute or proximity.
 * @param {NodeList} checkboxElements
 * @param {string} sectionName
 * @returns {Array}
 */
function groupCheckboxes(checkboxElements, sectionName) {
  const groups = {};

  checkboxElements.forEach((el) => {
    const name = el.getAttribute("name");
    if (name) {
      if (!groups[name]) {
        groups[name] = {
          element: el,
          options: [],
        };
      }
      groups[name].options.push(el);
    }
  });

  const fields = [];

  // Handle grouped checkboxes
  Object.entries(groups).forEach(([name, group]) => {
    const el = group.element;
    const options = group.options.map((checkbox) => {
      const label = resolveLabel(checkbox);
      return label || checkbox.value;
    });

    const fieldName = resolveLabel(el) || name;
    const selector = generateSelector(el);
    fields.push({
      field_id: generateFieldId(sectionName, fieldName, selector),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: FIELD_TYPES.MULTISELECT,
      current_value: group.options
        .filter((cb) => cb.checked)
        .map((cb) => cb.value),
      options: options,
      selector: selector,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    });
  });

  // Handle standalone checkboxes (no name)
  checkboxElements.forEach((el) => {
    if (!el.getAttribute("name")) {
      const fieldName = resolveLabel(el) || "Checkbox";
      const selector = generateSelector(el);
      fields.push({
        field_id: generateFieldId(sectionName, fieldName, selector),
        section_name: sectionName,
        field_name: fieldName,
        qualified_label: getQualifiedLabel(sectionName, fieldName),
        field_type: FIELD_TYPES.CHECKBOX,
        current_value: el.checked ? "checked" : "unchecked",
        options: [],
        selector: selector,
        required: isFieldRequired(el),
        placeholder: getPlaceholder(el),
        help_text: getHelpText(el),
      });
    }
  });

  return fields;
}

/**
 * Scan all form fields within a given section element.
 * Supports: input[type=text], textarea, select, input[type=checkbox], input[type=radio], input[type=file]
 * @param {HTMLElement} sectionElement
 * @param {string} sectionName
 * @returns {Array}
 */
function scanFields(sectionElement, sectionName) {
  const fields = [];

  // Collect all form elements within the section
  const formElements = sectionElement.querySelectorAll(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), textarea, select',
  );

  // Separate elements by type for grouping
  const textElements = [];
  const selectElements = [];
  const radioElements = [];
  const checkboxElements = [];
  const fileElements = [];

  formElements.forEach((el) => {
    if (el.offsetParent === null || el.disabled) return;

    const type = (el.getAttribute("type") || "text").toLowerCase();
    if (type === "radio") {
      radioElements.push(el);
    } else if (type === "checkbox") {
      checkboxElements.push(el);
    } else if (type === "file") {
      fileElements.push(el);
    } else if (el.tagName.toLowerCase() === "select") {
      selectElements.push(el);
    } else {
      textElements.push(el);
    }
  });

  // Process text inputs
  textElements.forEach((el) => {
    const fieldType = getFieldType(el);
    if (!fieldType) return;

    const fieldName =
      resolveLabel(el) || el.getAttribute("name") || "Unnamed Field";
    const selector = generateSelector(el);
    fields.push({
      field_id: generateFieldId(sectionName, fieldName, selector),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: fieldType,
      current_value: getCurrentValue(el),
      options: [],
      selector: selector,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    });
  });

  // Process select elements
  selectElements.forEach((el) => {
    const fieldName =
      resolveLabel(el) || el.getAttribute("name") || "Unnamed Field";
    const selector = generateSelector(el);
    fields.push({
      field_id: generateFieldId(sectionName, fieldName, selector),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: FIELD_TYPES.SELECT,
      current_value: getCurrentValue(el),
      options: getSelectOptions(el),
      selector: selector,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    });
  });

  // Process radio groups
  fields.push(...groupRadios(radioElements, sectionName));

  // Process checkbox groups
  fields.push(...groupCheckboxes(checkboxElements, sectionName));

  // Process file inputs
  fileElements.forEach((el) => {
    const fieldName =
      resolveLabel(el) || el.getAttribute("name") || "File Upload";
    const selector = generateSelector(el);
    fields.push({
      field_id: generateFieldId(sectionName, fieldName, selector),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: FIELD_TYPES.FILE,
      current_value: "",
      options: [],
      selector: selector,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    });
  });

  return fields;
}

/**
 * Determine the field type from an element.
 * @param {HTMLElement} el
 * @returns {string|null}
 */
function getFieldType(el) {
  const tag = el.tagName.toLowerCase();
  if (tag === "textarea") return FIELD_TYPES.TEXTAREA;
  if (tag === "select") return FIELD_TYPES.SELECT;

  const type = (el.getAttribute("type") || "text").toLowerCase();
  switch (type) {
    case "text":
    case "email":
    case "tel":
    case "url":
    case "number":
    case "date":
    case "password":
    case "search":
    case "color":
    case "range":
    case "datetime-local":
    case "time":
    case "month":
    case "week":
      return FIELD_TYPES.TEXT;
    case "checkbox":
      return FIELD_TYPES.CHECKBOX;
    case "radio":
      return FIELD_TYPES.RADIO;
    case "file":
      return FIELD_TYPES.FILE;
    default:
      // Log unknown field types for debugging instead of silently dropping
      console.warn(`Unknown field type: "${type}" for element`, el);
      return FIELD_TYPES.TEXT;
  }
}
