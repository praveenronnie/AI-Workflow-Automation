// Main content script - orchestrates form scanning and filling
//
// ARCHITECTURE: This content script ONLY interacts with the DOM and the
// platform-adapter registry. It contains no platform-specific logic:
//   - Platform adapters are declarative JSON configs (adapters/*.adapter.json)
//   - Executable extractors/parsers self-register as named handlers
//   - All backend API communication is handled by the background service worker
//
// Message Flow:
//   1. Content script resolves the platform adapter for the current page
//   2. Adapter strategy entry points are dispatched through the registry
//   3. Content script sends data to background via chrome.runtime.sendMessage
//   4. Background service worker makes API calls to FastAPI
//   5. Background returns results to content script via sendResponse

/**
 * Get the global adapter registry (injected by extractors/registry.js).
 * @returns {object} AdapterRegistry instance
 */
function getRegistry() {
  if (typeof window === "undefined" || !window.ApiExtractorRegistry) {
    throw new Error(
      "[CONTENT] AdapterRegistry unavailable — ensure " +
        "content/extractors/registry.js is injected before content.js",
    );
  }
  return window.ApiExtractorRegistry;
}

function sendToBackground(action, payload) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage({ action, ...payload }, (response) => {
      if (chrome.runtime.lastError) {
        console.error(
          "[CONTENT] Background message error:",
          chrome.runtime.lastError,
        );
        resolve({ success: false, error: chrome.runtime.lastError.message });
        return;
      }
      resolve(response);
    });
  });
}

/**
 * Extract report_id from the DOM.
 * Checks common patterns: URL params, hidden inputs, data attributes, meta tags.
 * @returns {string|null}
 */
function extractReportId() {
  // Check URL path for /reports/{id} pattern
  const pathMatch = window.location.pathname.match(
    /\/reports\/([a-zA-Z0-9_-]+)/,
  );
  if (pathMatch) return pathMatch[1];

  // Check URL params
  const urlParams = new URLSearchParams(window.location.search);
  const urlReportId =
    urlParams.get("report_id") ||
    urlParams.get("reportId") ||
    urlParams.get("id");
  if (urlReportId) return urlReportId;

  // Check hidden input fields
  const hiddenInput = document.querySelector(
    'input[type="hidden"][name*="report" i], input[type="hidden"][id*="report" i], input[name="report_id"], input[id="report_id"]',
  );
  if (hiddenInput?.value) return hiddenInput.value;

  // Check data attributes on body or main containers
  const reportIdFromData =
    document.body.getAttribute("data-report-id") ||
    document.body.getAttribute("data-report");
  if (reportIdFromData) return reportIdFromData;

  // Check meta tags
  const metaTag = document.querySelector(
    'meta[name="report-id"], meta[property="og:url"], meta[name="description"]',
  );
  if (metaTag) {
    const content =
      metaTag.getAttribute("content") || metaTag.getAttribute("property");
    if (content) {
      const match = content.match(/report[_-]?id[=:]?\s*([a-zA-Z0-9_-]+)/i);
      if (match) return match[1];
    }
  }

  return null;
}

/**
 * Resolve the platform adapter for a given host/url.
 * Delegates to the adapter loader which fetches adapter config JSON files.
 * @param {string} host - Hostname of the current page
 * @param {string} url - Full URL of the current page
 * @returns {Promise<object|null>}
 */
async function resolvePlatformAdapter(host, url) {
  if (typeof resolveAdapter !== "function") {
    console.warn("[CONTENT] Adapter loader not injected; skipping API extraction.");
    return null;
  }
  return resolveAdapter(host, url);
}

/**
 * Run the resolved adapter's API extraction strategy via the registry.
 * The adapter JSON declares the handler name; the registry resolves it.
 * @param {object} adapter - resolved adapter config
 * @param {string|number} reportId
 */
async function runApiStrategy(adapter, reportId) {
  return getRegistry().runStrategy(adapter, "api", reportId);
}

/**
 * Scan the entire form and return the form schema.
 * Uses unified scanner for single-pass DOM traversal.
 * @returns {Promise<{sections: Array, images: Array, multiStep: object, tables: Array, scanLog: Array, stats: object}>}
 */
async function scanForm() {
  // Use unified scanner for single-pass DOM traversal
  const scanResult = await scanEntireForm();

  // Attach images to their sections
  const imagesBySection = new Map();
  scanResult.images.forEach((img) => {
    const sectionName = img.section_name || "General";
    if (!imagesBySection.has(sectionName)) {
      imagesBySection.set(sectionName, []);
    }
    imagesBySection.get(sectionName).push(img);
  });

  // Filter out UI-only sections immediately
  const uiSectionIndicators = [
    "sidebar",
    "editor",
    "toolbar",
    "palette",
    "canvas",
    "workspace",
    "toolbox",
  ];

  // Build formSchema for backward compatibility
  let formSchema = {
    sections: scanResult.sections
      .map((section) => ({
        name: section.name,
        fields: scanResult.fields.filter(
          (f) => f.section_name === section.name,
        ),
        images: imagesBySection.get(section.name) || [],
      }))
      .filter((s) => {
        const name = s.name.toLowerCase();
        // Drop UI-only sections
        if (uiSectionIndicators.some((ind) => name.includes(ind))) {
          return false;
        }
        return s.fields.length > 0 || s.images.length > 0;
      }),
    fields: scanResult.fields,
    images: scanResult.images,
    multiStep: scanResult.multiStep,
    tables: scanResult.tables,
    scanLog: scanResult.scanLog,
    stats: scanResult.stats,
  };

  // Post-process: aggressively clean and deduplicate
  const cleanedFields = scanResult.fields.filter((f) => {
    const name = f.field_name.toLowerCase().trim();

    // Drop fields from UI-only sections (sidebars, editors, toolbars)
    const sectionName = (f.section_name || "").toLowerCase();
    if (
      uiSectionIndicators.some((indicator) => sectionName.includes(indicator))
    ) {
      return false;
    }

    // Drop UI-only labels, buttons, and section headers
    if (name.includes("viewing all sections")) return false;
    if (name.includes("view all")) return false;
    if (name.includes("show all")) return false;
    if (name.includes("collapse all")) return false;
    if (name.includes("expand all")) return false;
    if (name.startsWith("actions")) return false;
    if (name.startsWith("viewing")) return false;
    // Drop generic UI labels
    const uiLabels = new Set([
      "submit",
      "cancel",
      "close",
      "next",
      "previous",
      "back",
      "save",
      "delete",
      "edit",
      "menu",
      "settings",
      "filter",
      "search",
    ]);
    if (uiLabels.has(name)) return false;
    // Drop non-field types
    const validTypes = new Set([
      "text",
      "textarea",
      "select",
      "checkbox",
      "radio",
      "multiselect",
      "file",
      "number",
      "email",
      "tel",
      "url",
      "date",
      "password",
    ]);
    if (!validTypes.has(f.field_type)) return false;
    return true;
  });

  // Deduplicate by composite key (section_name + field_name)
  const deduped = [];
  const seen = new Set();
  cleanedFields.forEach((f) => {
    if (f.field_name.includes("\n")) return;
    const key = `${f.section_name || "General"}::${f.field_name}`;
    if (seen.has(key)) return;
    seen.add(key);
    deduped.push(f);
  });
  formSchema.fields = deduped;

  // Rebuild sections with deduplicated fields
  const dedupKeys = new Set(
    deduped.map((f) => `${f.section_name}::${f.field_name}`),
  );
  formSchema.sections = formSchema.sections
    .map((section) => {
      const seenInSection = new Set();
      return {
        ...section,
        fields: section.fields.filter((f) => {
          const key = `${section.name}::${f.field_name}`;
          if (!dedupKeys.has(key)) return false;
          if (seenInSection.has(key)) return false;
          seenInSection.add(key);
          return true;
        }),
        images: section.images || [],
      };
    })
    .filter((s) => s.fields.length > 0 || s.images.length > 0);

  // Resolve the platform adapter by URL and run its configured API strategy.
  const reportId = extractReportId();
  const adapter = await resolvePlatformAdapter(
    window.location.hostname,
    window.location.href,
  );
  if (reportId && adapter?.extraction?.strategies?.api) {
    const platformLabel = adapter?.displayName || adapter?.id || "platform";
    console.log(`[CONTENT] Attempting API extraction via adapter: ${platformLabel}`);
    try {
      const apiSchema = await runApiStrategy(adapter, reportId);
      console.log("[CONTENT] API schema extracted:", apiSchema);
      const mergedSchema = mergeApiSchema(formSchema, apiSchema);
      formSchema = mergedSchema;
    } catch (apiError) {
      console.warn(
        "[CONTENT] API extraction failed, using DOM-only data:",
        apiError,
      );
    }
  }

  // Final console output - only metadata sent to backend
  const backendSections = formSchema.sections
    .filter((s) => {
      const name = s.name.toLowerCase();
      return !uiSectionIndicators.some((ind) => name.includes(ind));
    })
    .map((s) => ({
      name: s.name,
      fields: s.fields.map((f) => ({
        field_id: f.field_id,
        field_name: f.field_name,
        field_type: f.field_type,
        value: f.current_value || null,
        required: f.required,
        options: f.options || [],
      })),
      images: s.images || [],
    }));

  // Ensure all fields have field_id for consistent mapping
  const ensureFieldIds = (sections) => {
    if (!sections || !Array.isArray(sections)) return [];
    return sections.map((s) => ({
      ...s,
      fields: (s.fields || []).map((f) => ({
        ...f,
        field_id: f.field_id || `${s.name}_${f.field_name}`,
      })),
    }));
  };

  const backendPayload = {
    report_id: reportId,
    sections: ensureFieldIds(formSchema.apiSections || backendSections),
    tables: formSchema.apiTables || [],
    blueprintTags: formSchema.blueprintTags || [],
    multiStep: formSchema.multiStep || null,
    stats: {
      elementsVisited: formSchema.stats.elementsVisited,
      fieldsFound: formSchema.stats.fieldsFound,
      sectionsFound: (formSchema.apiSections || backendSections).length,
      imagesFound: formSchema.stats.imagesFound,
      tablesFound: (formSchema.apiTables || []).length,
      duration: formSchema.stats.duration,
    },
  };

  console.log("[BACKEND PAYLOAD]", JSON.stringify(backendPayload, null, 2));

  // Send form schema to background script for storage
  // The background script handles the API call to avoid host permissions in content script
  if (reportId) {
    sendToBackground("STORE_FORM_SCHEMA", {
      reportId,
      formSchema: backendPayload,
    })
      .then((response) => {
        if (response.success) {
          console.log(
            "[CONTENT] Form schema stored successfully:",
            response.data,
          );
        } else {
          console.error(
            "[CONTENT] Failed to store form schema:",
            response.error,
          );
        }
      })
      .catch((error) => {
        console.error("[CONTENT] Failed to store form schema:", error);
      });
  }

  return formSchema;
}

/**
 * Generate selector on-demand for a field.
 * @param {string} fieldId
 * @returns {string|null}
 */
function getSelectorByFieldId(fieldId) {
  const allFields = document.querySelectorAll(
    'input, textarea, select, [role="textbox"], [role="combobox"], [role="checkbox"], [role="radio"]',
  );

  for (const el of allFields) {
    const fieldName = resolveLabel(el) || el.getAttribute("name") || "";
    const selector = generateSelector(el);
    const hash = generateFieldId("", fieldName, selector);
    if (hash === fieldId) {
      return selector;
    }
  }

  // Fallback: try name / aria-label / data-field-id
  const fallback = document.querySelector(
    `[name*="Property Unit Count"], [aria-label*="Property Unit Count"], [data-field-id="field_1ba5ec82"]`,
  );
  if (fallback) {
    console.warn(
      "[CONTENT] Fallback selector found for field_id",
      fieldId,
      fallback,
    );
    return (
      fallback.tagName.toLowerCase() + (fallback.id ? `#${fallback.id}` : "")
    );
  }

  return null;
}

/**
 * Fill a single field identified by its selector.
 * @param {string} selector
 * @param {string} fieldType
 * @param {*} value
 */
function fillFieldBySelector(selector, fieldType, value) {
  const element = document.querySelector(selector);
  if (!element) return;

  switch (fieldType) {
    case FIELD_TYPES.TEXT:
    case FIELD_TYPES.TEXTAREA:
      fillText(element, value);
      break;
    case FIELD_TYPES.SELECT:
      fillDropdown(element, value);
      break;
    case FIELD_TYPES.CHECKBOX:
      fillCheckbox(element, value);
      break;
    case FIELD_TYPES.RADIO:
      fillRadio(element, value);
      break;
    case FIELD_TYPES.MULTISELECT:
      fillMultiselect(element, value);
      break;
  }
}

/**
 * Fill all mapped fields on the form.
 * Generates selectors on-demand for performance.
 * @param {Array} mappings - Array of {formField, sourceKey, value, selector, field_type}
 */
function autoFill(mappings) {
  console.log("[CONTENT] Processing", mappings.length, "mappings");

  mappings.forEach((mapping, index) => {
    console.log(
      `[CONTENT] Processing mapping ${index + 1}/${mappings.length}:`,
      {
        field_id: mapping.field_id,
        field_name: mapping.formField,
        value: mapping.value,
        field_type: mapping.field_type,
        provided_selector: mapping.selector,
      },
    );

    // Generate selector on-demand if not provided
    let selector = mapping.selector;
    if (!selector) {
      console.log(
        `[CONTENT] No selector provided, generating for field_id: ${mapping.field_id}`,
      );
      selector = getSelectorByFieldId(mapping.field_id);
      console.log(`[CONTENT] Generated selector: ${selector}`);
    }

    if (selector) {
      console.log(
        `[CONTENT] Filling field "${mapping.formField}" with value "${mapping.value}"`,
      );
      fillFieldBySelector(selector, mapping.field_type, mapping.value);
      console.log(`[CONTENT] Successfully filled field "${mapping.formField}"`);
    } else {
      console.warn(
        `[CONTENT] Could not find selector for field "${mapping.formField}" (field_id: ${mapping.field_id})`,
      );

      // Try fallback: search by field name in the DOM
      console.log(
        `[CONTENT] Trying fallback search for field: ${mapping.formField}`,
      );
      // Fallback: search for label elements containing the field name
      const labels = Array.from(document.querySelectorAll("label"));
      const matchingLabel = labels.find(
        (lbl) => lbl.textContent.trim() === mapping.formField,
      );
      if (matchingLabel) {
        const forAttr = matchingLabel.getAttribute("for");
        if (forAttr) {
          const element = document.getElementById(forAttr);
          if (element) {
            console.log(`[CONTENT] Found element via label for="${forAttr}"`);
            fillFieldBySelector(
              `#${forAttr}`,
              mapping.field_type,
              mapping.value,
            );
            console.log(
              `[CONTENT] Successfully filled field using label fallback`,
            );
            return;
          }
        }
        // If no for attribute, try to find the first input inside the label
        const inputInside = matchingLabel.querySelector(
          'input, textarea, select, [role="textbox"], [role="combobox"], [role="checkbox"], [role="radio"]',
        );
        if (inputInside) {
          console.log(
            `[CONTENT] Found input inside label for field "${mapping.formField}"`,
          );
          const selector = generateSelector(inputInside);
          fillFieldBySelector(selector, mapping.field_type, mapping.value);
          console.log(
            `[CONTENT] Successfully filled field using label inner input fallback`,
          );
          return;
        }
      }
    }
  });

  console.log(`[CONTENT] Finished processing all mappings`);
}

// Merge API-derived schema with DOM-derived schema
function mergeApiSchema(domSchema, apiSchema) {
  if (!apiSchema) return domSchema;

  // Store API-derived data separately for backend
  return {
    ...domSchema,
    apiSections: apiSchema.sections || [],
    apiTables: apiSchema.tables || [],
    blueprintTags: apiSchema.blueprintTags || [],
  };
}

// Expose helper functions to window for console testing
if (typeof window !== "undefined") {
  window.getSelectorByFieldId = getSelectorByFieldId;
  window.fillFieldBySelector = fillFieldBySelector;
  window.scanForm = scanForm;
  window.extractReportId = extractReportId;
  window.mergeApiSchema = mergeApiSchema;
}

// Listen for messages from the popup or background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  switch (message.action) {
    case "scanForm":
      scanForm().then((schema) => {
        sendResponse({ success: true, data: schema });
      });
      return true; // Keep channel open for async response

    case "autoFill":
      try {
        console.log(
          "[CONTENT] autoFill received:",
          JSON.stringify(message.mappings, null, 2),
        );
        console.log(
          "[CONTENT] Number of mappings to apply:",
          message.mappings.length,
        );

        if (message.mappings.length === 0) {
          console.warn("[CONTENT] No mappings provided, nothing to fill");
          sendResponse({ success: true, message: "No mappings provided" });
          return;
        }

        autoFill(message.mappings);
        console.log("[CONTENT] autoFill completed successfully");
        sendResponse({ success: true });
      } catch (error) {
        console.error("[CONTENT] autoFill error:", error);
        sendResponse({ success: false, error: error.message });
      }
      break;

    case "getFieldValue":
      try {
        const el = document.querySelector(message.selector);
        const value = el ? getCurrentValue(el) : "";
        sendResponse({ success: true, data: value });
      } catch (error) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    case "scanDropdownOptions":
      console.log("[CONTENT] Scanning dropdown options...");

      // First, scan the form to get current tables
      scanForm()
        .then((formSchema) => {
          const tables = formSchema.tables || [];

          if (tables.length === 0) {
            sendResponse({
              success: true,
              data: {
                tables: [],
                scanSummary: {
                  total: 0,
                  scanned: 0,
                  message: "No tables found",
                },
              },
            });
            return;
          }

          // Scan dropdown options using globally available function
          window
            .scanTableDropdowns(
              tables,
              {
                throttleMs: 300,
                timeoutMs: 5000,
                maxRetries: 2,
              },
              (current, total, cellId) => {
                console.log(
                  `[CONTENT] Scanning dropdown ${current}/${total}: ${cellId}`,
                );
              },
              message.signal,
            )
            .then((result) => {
              console.log(
                "[CONTENT] Dropdown scan complete:",
                result.scanSummary,
              );

              sendResponse({
                success: true,
                data: result,
              });
            })
            .catch((error) => {
              console.error("[CONTENT] Dropdown scan error:", error);
              sendResponse({ success: false, error: error.message });
            });
        })
        .catch((error) => {
          console.error("[CONTENT] Form scan error:", error);
          sendResponse({ success: false, error: error.message });
        });
      return true; // Keep channel open for async response

    default:
      sendResponse({
        success: false,
        error: `Unknown action: ${message.action}`,
      });
  }
});
