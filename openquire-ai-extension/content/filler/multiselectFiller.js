// Multiselect filler - fills checkbox groups (multiselect fields)

/**
 * Fill a checkbox group (multiselect) based on an array of values.
 * @param {HTMLInputElement} element - One checkbox from the group
 * @param {string[]|string} values - Array of values to check
 */
function fillMultiselect(element, values) {
  if (!element || values === undefined || values === null) return;

  const name = element.getAttribute("name");
  if (!name) return;

  const valueArray = Array.isArray(values) ? values : [values];

  // Find all checkboxes in the group
  const checkboxes = document.querySelectorAll(`input[name="${name}"]`);

  checkboxes.forEach((checkbox) => {
    const label = resolveLabel(checkbox);
    const shouldCheck = valueArray.some(
      (val) =>
        String(val).toLowerCase() === String(checkbox.value).toLowerCase() ||
        String(val).toLowerCase() === String(label).toLowerCase(),
    );

    checkbox.focus();
    checkbox.checked = shouldCheck;
    dispatchFillEvents(checkbox);
    checkbox.blur();
  });
}
