// Mutation Observer - detects DOM changes for dynamic forms

let observer = null;
let fieldRegistry = new Map();
let sectionRegistry = new Map();
let debounceTimer = null;
let onFieldsChanged = null;

/**
 * Initialize the mutation observer.
 * @param {function} callback - Called when fields change
 */
function initMutationObserver(callback) {
  onFieldsChanged = callback;

  observer = new MutationObserver((mutations) => {
    const changes = {
      addedFields: [],
      removedFields: [],
      changedSections: [],
    };

    // Debounce to avoid excessive rescans
    if (debounceTimer) {
      clearTimeout(debounceTimer);
    }

    debounceTimer = setTimeout(() => {
      mutations.forEach((mutation) => {
        if (mutation.type === "childList") {
          // Handle added nodes
          mutation.addedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              const fields = extractFieldsFromNode(node);
              if (fields.length > 0) {
                changes.addedFields.push(...fields);
              }
            }
          });

          // Handle removed nodes
          mutation.removedNodes.forEach((node) => {
            if (node.nodeType === Node.ELEMENT_NODE) {
              const fieldIds = getFieldIdsFromNode(node);
              if (fieldIds.length > 0) {
                changes.removedFields.push(...fieldIds);
              }
            }
          });
        }

        if (mutation.type === "attributes") {
          // Check for visibility changes
          if (
            mutation.attributeName === "style" ||
            mutation.attributeName === "class"
          ) {
            const fieldId = getFieldIdFromElement(mutation.target);
            if (fieldId) {
              const wasVisible = fieldRegistry.get(fieldId)?.visible;
              const isVisible =
                mutation.target.offsetParent !== null &&
                !mutation.target.hasAttribute("hidden");

              if (wasVisible !== isVisible) {
                changes.changedSections.push({
                  fieldId,
                  visible: isVisible,
                });
              }
            }
          }
        }
      });

      // Only notify if there are actual changes
      if (
        changes.addedFields.length > 0 ||
        changes.removedFields.length > 0 ||
        changes.changedSections.length > 0
      ) {
        if (onFieldsChanged) {
          onFieldsChanged(changes);
        }
      }
    }, 500); // 500ms debounce
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["style", "class", "hidden"],
  });
}

/**
 * Stop the mutation observer.
 */
function stopMutationObserver() {
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
}

/**
 * Extract form fields from a DOM node.
 * @param {HTMLElement} node
 * @returns {Array}
 */
function extractFieldsFromNode(node) {
  const fields = [];
  const formElements = node.querySelectorAll
    ? node.querySelectorAll(
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select, [role="textbox"], [role="combobox"]',
      )
    : [];

  formElements.forEach((el) => {
    if (el.offsetParent === null) return;

    const fieldId = getFieldIdFromElement(el);
    if (fieldId) {
      fieldRegistry.set(fieldId, {
        element: el,
        visible: true,
        selector: generateSelector(el),
      });
      fields.push({
        fieldId,
        element: el,
      });
    }
  });

  return fields;
}

/**
 * Get field IDs from a removed node.
 * @param {HTMLElement} node
 * @returns {Array}
 */
function getFieldIdsFromNode(node) {
  const ids = [];
  const elements = node.querySelectorAll
    ? node.querySelectorAll(
        'input:not([type="hidden"]), textarea, select, [role="textbox"]',
      )
    : [];

  elements.forEach((el) => {
    const fieldId = getFieldIdFromElement(el);
    if (fieldId) {
      fieldRegistry.delete(fieldId);
      ids.push(fieldId);
    }
  });

  return ids;
}

/**
 * Generate or retrieve field ID for an element.
 * @param {HTMLElement} element
 * @returns {string}
 */
function getFieldIdFromElement(element) {
  // Check for existing data-field-id
  let fieldId = element.getAttribute("data-field-id");
  if (fieldId) return fieldId;

  // Generate deterministic ID
  const sectionName = resolveSectionName(element) || "General";
  const fieldName =
    resolveLabel(element) || element.getAttribute("name") || "Field";
  const selector = generateSelector(element);

  fieldId = generateFieldId(sectionName, fieldName, selector);
  element.setAttribute("data-field-id", fieldId);

  return fieldId;
}

/**
 * Rescan a specific section for changes.
 * @param {HTMLElement} sectionElement
 * @param {string} sectionName
 * @returns {Array}
 */
function rescanSection(sectionElement, sectionName) {
  const fields = scanFields(sectionElement, sectionName);
  return fields;
}

/**
 * Get current field registry.
 * @returns {Map}
 */
function getFieldRegistry() {
  return fieldRegistry;
}

/**
 * Clear field registry.
 */
function clearFieldRegistry() {
  fieldRegistry.clear();
  sectionRegistry.clear();
}
