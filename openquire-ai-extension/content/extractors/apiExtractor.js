// OpenQuire API Extraction Strategy
// This module provides functions to extract report data via authenticated
// OpenQuire APIs. It is designed to be an additional extraction path that
// augments the existing DOM-based scanners.

/**
 * Get CSRF token from the page's meta tag.
 * Rails apps typically include this in the page head.
 * @returns {string|null}
 */
function getCsrfToken() {
  if (typeof document === "undefined") return null;
  const meta = document.querySelector('meta[name="csrf-token"]');
  return meta ? meta.getAttribute("content") : null;
}

/**
 * Fetch the full report HTML for a given report ID.
 * @param {string|number} reportId
 * @returns {Promise<string>} HTML string
 */
async function extractReport(reportId) {
  const url = `/reports/${reportId}`;
  console.log("[API] fetchReport", url);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to fetch report ${reportId}: ${response.status}`);
  }
  return await response.text();
}

/**
 * Extract unique table section IDs from report HTML.
 * @param {string} html
 * @returns {string[]} Array of table section IDs
 */
function extractTableIds(html) {
  const regex = /info_table_sections\/([0-9]+)/g;
  const ids = new Set();
  let match;
  while ((match = regex.exec(html)) !== null) {
    ids.add(match[1]);
  }
  return Array.from(ids);
}

/**
 * Fetch the JSON data for a specific table section.
 * @param {string} tableId
 * @returns {Promise<object>} JSON object
 */
async function fetchTableSection(tableId) {
  const url = `/info_table_sections/${tableId}/edit_table?force=1`;
  console.log("[API] fetchTableSection", url);
  const response = await fetch(url, { credentials: "include" });
  if (!response.ok) {
    throw new Error(
      `Failed to fetch table section ${tableId}: ${response.status}`,
    );
  }
  return await response.json();
}

/**
 * Parse table JSON and extract field metadata.
 * @param {object} data - JSON response from /edit_table endpoint
 * @returns {object} Table object with metadata and fields
 */
function parseTableJSON(data) {
  const fields = [];
  const tableId = data.container?.id;
  const tableName =
    data.container?.title || data.container?.header_title || "Table";
  const lockUid = data.uid || null;

  // Extract row-level fields with dictionaries
  if (data.rows) {
    data.rows.forEach((row) => {
      if (!row.data) return;

      // Find label cell (first cell with plain value, no cell_definition)
      let labelCellValue = null;
      const dataEntries = Object.entries(row.data);
      for (const [key, cellData] of dataEntries) {
        if (key === "position" || key === "metadata") continue;
        if (cellData.value && !cellData.cell_definition) {
          // Strip HTML tags
          labelCellValue = cellData.value.replace(/<[^>]*>/g, "").trim();
          break;
        }
      }

      // Extract dictionary cells
      dataEntries.forEach(([key, cellData]) => {
        if (key === "position" || key === "metadata") return;
        if (
          cellData &&
          cellData.cell_definition &&
          cellData.cell_definition.dictionary &&
          cellData.cell_definition.dictionary.length > 0
        ) {
          // Convert dictionary array to {id: name} format
          const options = {};
          cellData.cell_definition.dictionary.forEach((item) => {
            options[item.id] = item.name;
          });

          // Parse value after "_quire_keyword_value:"
          let parsedValue = null;
          if (cellData.value && typeof cellData.value === "string") {
            const match = cellData.value.match(/_quire_keyword_value:(.*)$/);
            if (match) {
              parsedValue = match[1].trim() || null;
            }
          }

          // Use label cell as field name, fallback to column name
          const colDef = data.column_definitions?.find(
            (c) => c.id === cellData.cell_definition.column_definition_id,
          );
          const fieldName = labelCellValue || colDef?.name || "Unnamed Field";

          fields.push({
            fieldName: fieldName,
            value: parsedValue,
            options: options,
            rowId: row.id,
            cellDefinitionId: cellData.cell_definition.id,
            columnId: cellData.cell_definition.column_definition_id,
          });
        }
      });
    });
  }

  return { tableId, tableName, lockUid, fields };
}

/**
 * Fetch blueprint tags for a report.
 * @param {string|number} reportId
 * @returns {Promise<Array>} Array of blueprint tag objects
 */
async function fetchBlueprintTags(reportId) {
  const url = `/reports/${reportId}/blueprint_tags`;
  console.log("[API] fetchBlueprintTags", url);
  const response = await fetch(url, {
    credentials: "include",
    headers: {
      Accept: "application/json",
      "X-Requested-With": "XMLHttpRequest",
    },
  });
  if (!response.ok) {
    throw new Error(
      `Failed to fetch blueprint tags for report ${reportId}: ${response.status}`,
    );
  }
  return await response.json();
}

/**
 * Parse blueprint tags into field schema.
 * @param {Array} data - Array of blueprint tag objects
 * @returns {Array} Array of field objects
 */
function parseBlueprintTags(data) {
  return data.map((tag) => ({
    fieldName: tag.name,
    value: tag.set_value,
    tagId: tag.id,
    itemId: tag.item_id,
    slug: tag.slug,
    editor: tag.editor,
    precision: tag.precision,
    locked: tag.locked,
  }));
}

/**
 * Update a table cell value.
 * @param {number} rowId - The row ID
 * @param {number} columnId - The column definition ID
 * @param {number} keywordId - The selected dictionary option ID
 * @returns {Promise<object>} Response from server
 */
async function updateTableValue(rowId, columnId, keywordId) {
  const url = `/info_table_values/${rowId}`;
  console.log("[API] updateTableValue", url);

  const formData = new URLSearchParams();
  formData.append(`columns[${columnId}][_quire_keyword_id]`, keywordId);

  const headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    Accept: "application/json",
  };

  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(url, {
    method: "PUT",
    credentials: "include",
    headers: headers,
    body: formData.toString(),
  });

  if (!response.ok) {
    throw new Error(
      `Failed to update table value for row ${rowId}: ${response.status}`,
    );
  }

  return await response.json();
}

/**
 * Release the edit lock for a table section.
 * @param {number} tableId - The table section ID
 * @param {string} lockUid - The lock UID from the table data
 * @returns {Promise<object>} Response from server
 */
async function releaseTableLock(tableId, lockUid) {
  const url = `/info_table_sections/${tableId}/unlock_for_edit`;
  console.log("[API] releaseTableLock", url);

  const formData = new URLSearchParams();
  formData.append("lock_uid", lockUid);
  //formData.append("_browser_id", "2001785256285544");

  const headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
    Accept: "application/json",
  };

  const csrfToken = getCsrfToken();
  if (csrfToken) {
    headers["X-CSRF-Token"] = csrfToken;
  }

  const response = await fetch(url, {
    method: "POST",
    credentials: "include",
    headers: headers,
    body: formData.toString(),
  });

  if (!response.ok) {
    throw new Error(
      `Failed to release lock for table ${tableId}: ${response.status}`,
    );
  }

  return await response.json();
}

/**
 * Build a schema object from a report ID.
 * @param {string|number} reportId
 * @returns {Promise<Object>} Schema object with sections, tables, blueprintTags
 */
async function buildSchema(reportId) {
  console.log("[API] buildSchema for", reportId);
  const reportHtml = await extractReport(reportId);
  const tableIds = extractTableIds(reportHtml);
  const tables = [];
  const sections = [];

  for (const id of tableIds) {
    try {
      const tableData = await fetchTableSection(id);
      const parsedTable = parseTableJSON(tableData);
      tables.push(parsedTable);
      // Add section name to sections list
      sections.push({
        name: parsedTable.tableName,
        tableId: parsedTable.tableId,
      });

      // Release lock after extraction
      /*if (parsedTable.lockUid) {
        try {
          await releaseTableLock(id, parsedTable.lockUid);
          console.log(`[API] Released lock for table ${id}`);
        } catch (e) {
          console.warn(`Failed to release lock for table ${id}:`, e);
        }
      }*/
    } catch (e) {
      console.warn(`Failed to process table ${id}:`, e);
    }
  }

  let blueprintTags = [];
  try {
    const tagsData = await fetchBlueprintTags(reportId);
    blueprintTags = parseBlueprintTags(tagsData);
  } catch (e) {
    console.warn(`Failed to fetch blueprint tags:`, e);
  }

  return { reportId: Number(reportId), sections, tables, blueprintTags };
}

// Expose for debugging in devtools
if (typeof window !== "undefined") {
  window.openquireExtractor = {
    extractReport,
    extractTableIds,
    fetchTableSection,
    parseTableJSON,
    fetchBlueprintTags,
    parseBlueprintTags,
    updateTableValue,
    releaseTableLock,
    buildSchema,
    getCsrfToken,
  };

  // Self-register this platform's executable handlers with the adapter
  // registry. The adapter JSON references these names via strategy
  // entry points (e.g. "openquire.buildSchema"), so content.js stays
  // implementation-agnostic. Handlers receive (adapter, strategy, ...args)
  // so thin wrappers adapt that to the plain extractor signatures.
  // Requires registry.js to be injected first.
  if (window.ApiExtractorRegistry) {
    window.ApiExtractorRegistry.registerHandler(
      "openquire.buildSchema",
      (_adapter, _strategy, reportId) => buildSchema(reportId),
    );
    window.ApiExtractorRegistry.registerHandler(
      "openquire.parseTableJSON",
      (_adapter, _strategy, data) => parseTableJSON(data),
    );
    window.ApiExtractorRegistry.registerHandler(
      "openquire.parseBlueprintTags",
      (_adapter, _strategy, data) => parseBlueprintTags(data),
    );
  }
}

// Export for Node.js (Jest tests)
if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    extractReport,
    extractTableIds,
    fetchTableSection,
    parseTableJSON,
    fetchBlueprintTags,
    parseBlueprintTags,
    updateTableValue,
    releaseTableLock,
    buildSchema,
    getCsrfToken,
  };
}
