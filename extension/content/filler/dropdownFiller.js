// Dropdown filler - fills select elements

/**
 * Fill a select dropdown by matching the value to an option.
 * @param {HTMLSelectElement} element
 * @param {string} value
 */
function fillDropdown(element, value) {
  if (!element || value === undefined || value === null) return;

  element.focus();

  // Try to match by value first, then by text
  const options = Array.from(element.options);
  const match = options.find(
    (opt) => opt.value === String(value) || opt.text.trim() === String(value),
  );

  if (match) {
    element.value = match.value;
  } else if (options.length > 0) {
    // Fallback: set first non-empty option
    const firstValid = options.find((opt) => opt.value);
    if (firstValid) element.value = firstValid.value;
  }

  dispatchFillEvents(element);
  element.blur();
}
