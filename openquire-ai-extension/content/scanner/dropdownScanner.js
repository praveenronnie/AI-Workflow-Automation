// Dropdown scanner - interacts with table cells to extract dropdown options

// Scan configuration
const SCAN_CONFIG = {
  throttleMs: 300,
  timeoutMs: 5000,
  pollIntervalMs: 100,
  maxRetries: 2,
  scrollBehavior: "auto",
  autoCloseDropdowns: true,
  skipLockedCells: true,
  expandSections: true,
  uiIdleTimeout: 2000,
};

/**
 * Scan all tables and extract dropdown options by interacting with cells.
 * @param {Array} tables - Array of table objects from form schema
 * @param {object} [options] - Scan options
 * @param {Function} [onProgress] - Progress callback (current, total, cellId)
 * @param {AbortSignal} [signal] - Abort signal for cancellation
 * @returns {Promise<object>} - Updated tables with scan results
 */
async function scanTableDropdowns(tables, options = {}, onProgress, signal) {
  const config = { ...SCAN_CONFIG, ...options };
  const startTime = Date.now();
  const summary = {
    total: 0,
    scanned: 0,
    locked: 0,
    timeout: 0,
    noOptions: 0,
    needsInteraction: 0,
    duration: "0s",
  };

  console.log("[DROPDOWN SCANNER] Starting dropdown scan...");

  const uiState = window.saveUIState();

  try {
    if (config.expandSections) {
      console.log("[DROPDOWN SCANNER] Expanding collapsible sections...");
      const expanded = await window.expandAllSections(signal);
      console.log(`[DROPDOWN SCANNER] Expanded ${expanded} sections`);
    }

    await window.waitForUIIdle(config.uiIdleTimeout, signal);

    for (const table of tables) {
      if (signal?.aborted) {
        throw new Error("Scan aborted by user");
      }

      console.log(`[DROPDOWN SCANNER] Processing table: ${table.table_id}`);

      const dropdownCells = findDropdownCells(table);
      summary.total += dropdownCells.length;

      for (let i = 0; i < dropdownCells.length; i++) {
        if (signal?.aborted) {
          throw new Error("Scan aborted by user");
        }

        const cell = dropdownCells[i];
        const cellId = `table_${table.table_id}_row_${cell.row}_col_${cell.column}`;

        if (onProgress) {
          onProgress(i + 1, dropdownCells.length, cellId);
        }

        if (i > 0) {
          await window.sleep(config.throttleMs, signal);
        }

        const result = await scanDropdownCell(cell, table, config, signal);

        cell.options = result.options;
        cell.scanStatus = result.status;
        cell.scanError = result.error || null;

        summary.scanned++;
        if (result.status === "locked") summary.locked++;
        else if (result.status === "timeout") summary.timeout++;
        else if (result.status === "no_options") summary.noOptions++;
        else if (result.status === "needs_interaction")
          summary.needsInteraction++;

        console.log(
          `[DROPDOWN SCANNER] Cell ${cellId}: ${result.status} - ${result.options?.length || 0} options`,
        );
      }
    }

    const durationMs = Date.now() - startTime;
    summary.duration = `${(durationMs / 1000).toFixed(1)}s`;

    console.log("[DROPDOWN SCANNER] Scan complete:", summary);

    return {
      tables,
      scanSummary: summary,
    };
  } catch (error) {
    console.error("[DROPDOWN SCANNER] Scan failed:", error);
    throw error;
  } finally {
    window.restoreUIState(uiState);
    window.closeDropdowns();
  }
}

/**
 * Find all cells in a table - return all cells since we don't know
 * which ones have dropdowns until we check the DOM.
 * @param {object} table
 * @returns {Array}
 */
function findDropdownCells(table) {
  const allCells = [];

  for (const row of table.rows || []) {
    for (const cell of row.cells || []) {
      // Include all cells - we'll check for dropdowns in the DOM
      allCells.push(cell);
    }
  }

  return allCells;
}

/**
 * Generate a CSS selector for a table cell based on its position.
 * @param {object} table
 * @param {object} cell
 * @returns {string|null}
 */
function generateSelectorFromTable(table, cell) {
  // Try to find the table element in DOM
  let tableEl = null;

  if (table.selector) {
    tableEl = document.querySelector(table.selector);
  }

  // Fallback: find table by index
  if (!tableEl) {
    const tables = document.querySelectorAll("table");
    const tableIndex = parseInt(table.table_id.replace("table_", "")) - 1;
    if (tables[tableIndex]) {
      tableEl = tables[tableIndex];
    }
  }

  if (!tableEl) return null;

  return findCellSelector(tableEl, cell.row, cell.column);
}

/**
 * Find selector for a specific cell in a table.
 * @param {HTMLElement} tableEl
 * @param {number} rowIndex
 * @param {number} colIndex
 * @returns {string|null}
 */
function findCellSelector(tableEl, rowIndex, colIndex) {
  try {
    const rows = tableEl.querySelectorAll("tr");
    if (rowIndex < 1 || rowIndex > rows.length) return null;

    const row = rows[rowIndex - 1];
    const cells = row.querySelectorAll("td, th");
    if (colIndex < 1 || colIndex > cells.length) return null;

    const cell = cells[colIndex - 1];

    // Look for select/combobox in this cell
    const select = cell.querySelector(
      "select, [role='combobox'], .autocomplete-control, .js-autocomplete-control",
    );
    if (select) {
      return generateSelector(select);
    }

    // Return cell selector if no select found
    return generateSelector(cell);
  } catch (e) {
    console.error("[DROPDOWN SCANNER] Error finding cell selector:", e);
    return null;
  }
}

/**
 * Generate a unique CSS selector for an element.
 * @param {HTMLElement} el
 * @returns {string}
 */
function generateSelector(el) {
  if (!el) return "";

  if (el.id) {
    return `#${el.id}`;
  }

  const path = [];
  let current = el;

  while (current && current !== document.body) {
    let selector = current.tagName.toLowerCase();

    if (current.id) {
      selector = `#${current.id}`;
      path.unshift(selector);
      break;
    } else if (current.className) {
      const classes = current.className.split(" ").filter((c) => c.trim());
      if (classes.length > 0) {
        selector += "." + classes.slice(0, 2).join(".");
      }
    }

    path.unshift(selector);
    current = current.parentElement;

    if (path.length > 5) break;
  }

  return path.join(" > ");
}

/**
 * Scan a single dropdown cell.
 * @param {object} cell
 * @param {object} table
 * @param {object} config
 * @param {AbortSignal} signal
 * @returns {Promise<object>}
 */
async function scanDropdownCell(cell, table, config, signal) {
  const result = {
    options: cell.options || [],
    status: "success",
    error: null,
  };

  // Try to find selector from cell, or generate from table
  let selector = cell.selector;
  if (!selector) {
    selector = generateSelectorFromTable(table, cell);
  }

  if (!selector) {
    result.status = "needs_interaction";
    result.error = "Could not generate selector for cell";
    return result;
  }

  const element = document.querySelector(selector);
  if (!element) {
    result.status = "needs_interaction";
    result.error = "Element not found in DOM with selector: " + selector;
    return result;
  }

  if (config.skipLockedCells && window.isElementLocked(element)) {
    result.status = "locked";
    result.error = "Element is locked by MUTEX";
    return result;
  }

  if (!window.isElementVisible(element)) {
    result.status = "needs_interaction";
    result.error = "Element not visible";
    return result;
  }

  for (let attempt = 0; attempt < config.maxRetries; attempt++) {
    if (signal?.aborted) {
      throw new Error("Scan aborted");
    }

    try {
      window.scrollIntoViewSafely(element, config.scrollBehavior);

      await window.waitForUIIdle(config.uiIdleTimeout, signal);

      element.click();

      await window.sleep(config.pollIntervalMs * 2, signal);

      const options = await waitForOptionsToAppear(
        element,
        config.timeoutMs,
        config.pollIntervalMs,
        signal,
      );

      if (options.length > 0) {
        result.options = options;
        result.status = "success";
        return result;
      } else {
        result.status = "no_options";
        result.error = "Dropdown opened but no options found";
      }
    } catch (error) {
      if (error.message === "Operation aborted") {
        throw error;
      }
      result.error = error.message;

      if (attempt < config.maxRetries - 1) {
        await window.sleep(config.throttleMs, signal);
      }
    } finally {
      if (config.autoCloseDropdowns) {
        window.closeDropdowns();
        await window.sleep(config.pollIntervalMs, signal);
      }
    }
  }

  if (result.status === "success") {
    result.status = "timeout";
    result.error = "Timeout waiting for options";
  }

  return result;
}

/**
 * Wait for options to appear in dropdown after clicking.
 * @param {HTMLElement} element
 * @param {number} timeout
 * @param {number} pollInterval
 * @param {AbortSignal} signal
 * @returns {Promise<Array<string>>}
 */
async function waitForOptionsToAppear(element, timeout, pollInterval, signal) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    if (signal?.aborted) {
      throw new Error("Operation aborted");
    }

    if (element.tagName === "SELECT") {
      const options = Array.from(element.options).map((opt) => opt.text.trim());
      if (options.length > 0) {
        return options;
      }
    }

    const dictionary = element.closest(
      ".autocomplete-control, .js-autocomplete-control, [role='combobox']",
    );

    if (dictionary) {
      const listItems = dictionary.querySelectorAll(
        "ul.dictionary li, ul[class*='dictionary'] li, .dropdown-menu li, [role='listbox'] li",
      );

      if (listItems.length > 0) {
        return Array.from(listItems)
          .map((li) => li.getAttribute("data-name") || li.textContent.trim())
          .filter((opt) => opt.length > 0);
      }
    }

    await new Promise((resolve) => setTimeout(resolve, pollInterval));
  }

  return [];
}

/**
 * Extract options from a select element.
 * @param {HTMLSelectElement} selectEl
 * @returns {Array<string>}
 */
function extractSelectOptions(selectEl) {
  if (!selectEl || !selectEl.options) return [];
  return Array.from(selectEl.options).map((opt) => opt.text.trim());
}

/**
 * Extract options from a combobox/autocomplete.
 * @param {HTMLElement} comboboxEl
 * @returns {Array<string>}
 */
function extractComboboxOptions(comboboxEl) {
  if (!comboboxEl) return [];

  const dictionary = comboboxEl.closest(
    ".autocomplete-control, .js-autocomplete-control, [role='combobox']",
  );

  if (dictionary) {
    const listItems = dictionary.querySelectorAll(
      "ul.dictionary li, ul[class*='dictionary'] li, .dropdown-menu li, [role='listbox'] li",
    );

    return Array.from(listItems)
      .map((li) => li.getAttribute("data-name") || li.textContent.trim())
      .filter((opt) => opt.length > 0);
  }

  return [];
}

// Attach to global scope for content script access
if (typeof window !== "undefined") {
  window.scanTableDropdowns = scanTableDropdowns;
  window.SCAN_CONFIG = SCAN_CONFIG;
}
