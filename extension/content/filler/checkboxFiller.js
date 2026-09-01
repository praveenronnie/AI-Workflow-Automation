// Checkbox filler - fills checkbox inputs

/**
 * Fill a checkbox based on a boolean-like value.
 * @param {HTMLInputElement} element
 * @param {string|boolean} value
 */
function fillCheckbox(element, value) {
  if (!element || value === undefined || value === null) return;

  const shouldCheck =
    String(value).toLowerCase() === "true" ||
    String(value).toLowerCase() === "yes" ||
    String(value) === "1" ||
    String(value).toLowerCase() === "checked";

  element.focus();
  element.checked = shouldCheck;
  dispatchFillEvents(element);
  element.blur();
}
