// Radio filler - fills radio button groups

/**
 * Fill a radio button group by selecting the matching option.
 * @param {HTMLInputElement} element - One radio button from the group
 * @param {string} value
 */
function fillRadio(element, value) {
  if (!element || value === undefined || value === null) return;

  const name = element.getAttribute("name");
  if (!name) {
    // Single radio without group name
    element.focus();
    element.checked = true;
    dispatchFillEvents(element);
    element.blur();
    return;
  }

  // Find the radio button matching the value
  const radios = document.querySelectorAll(`input[name="${name}"]`);
  let selected = null;

  radios.forEach((radio) => {
    const label = resolveLabel(radio);
    if (
      radio.value === String(value) ||
      label.toLowerCase() === String(value).toLowerCase()
    ) {
      selected = radio;
    }
  });

  // Fallback: select first radio if no match
  if (!selected && radios.length > 0) {
    selected = radios[0];
  }

  if (selected) {
    selected.focus();
    selected.checked = true;
    dispatchFillEvents(selected);
    selected.blur();
  }
}
