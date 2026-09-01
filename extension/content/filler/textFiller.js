// Text filler - fills text inputs and textareas

/**
 * Fill a text input or textarea with a value.
 * @param {HTMLElement} element
 * @param {string} value
 */
function fillText(element, value) {
  if (!element || value === undefined || value === null) return;

  element.focus();
  element.value = String(value);
  dispatchFillEvents(element);
  element.blur();
}
