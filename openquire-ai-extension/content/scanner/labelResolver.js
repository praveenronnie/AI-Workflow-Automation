// Label resolver - resolves field labels from the DOM structure

/**
 * Resolve the section name for a field by walking up the DOM tree.
 * Looks for heading elements (h1-h6), legend, or elements with section-like classes.
 * @param {HTMLElement} element
 * @returns {string}
 */
function resolveSectionName(element) {
  let current = element.parentElement;
  while (current) {
    // Check for heading elements
    const heading = current.querySelector("h1, h2, h3, h4, h5, h6, legend");
    if (heading) {
      return heading.textContent.trim();
    }

    // Check for elements with section/group role
    if (
      current.getAttribute("role") === "region" ||
      current.getAttribute("role") === "group"
    ) {
      const label = current.getAttribute("aria-label");
      if (label) return label;
    }

    // Check for fieldset
    if (current.tagName === "FIELDSET") {
      const legend = current.querySelector("legend");
      if (legend) return legend.textContent.trim();
    }

    current = current.parentElement;
  }

  return "General";
}

/**
 * Extract dropdown options from a select element.
 * @param {HTMLSelectElement} selectEl
 * @returns {string[]}
 */
function getSelectOptions(selectEl) {
  if (!selectEl || !selectEl.options) return [];
  return Array.from(selectEl.options).map((opt) => opt.text.trim());
}

/**
 * Extract radio button options sharing the same name.
 * @param {HTMLInputElement} radioEl
 * @returns {string[]}
 */
function getRadioOptions(radioEl) {
  const name = radioEl.getAttribute("name");
  if (!name) return [radioEl.value];
  const radios = document.querySelectorAll(`input[name="${name}"]`);
  return Array.from(radios).map((r) => {
    const label = resolveLabel(r);
    return label || r.value;
  });
}
