// Table/Grid scanner - detects repeating form structures
// scanTableDropdowns is available globally from dropdownScanner.js

/**
 * Scan for table and grid structures in forms.
 * @returns {Array<object>}
 */
function scanTables() {
  const tables = [];

  // Detect HTML tables
  const htmlTables = document.querySelectorAll("table");
  htmlTables.forEach((table, tableIndex) => {
    if (table.offsetParent === null) return;

    const tableData = extractTableStructure(table, tableIndex);
    if (tableData) {
      tables.push(tableData);
    }
  });

  // Detect grid role elements
  const grids = document.querySelectorAll('[role="grid"], [role="table"]');
  grids.forEach((grid, gridIndex) => {
    if (grid.offsetParent === null) return;

    const tableData = extractGridStructure(grid, gridIndex);
    if (tableData) {
      tables.push(tableData);
    }
  });

  // Detect div-based tables (common in React)
  const divTables = document.querySelectorAll(
    '.table, .grid, [class*="table"], [class*="grid"]',
  );
  divTables.forEach((divTable, divIndex) => {
    if (divTable.offsetParent === null) return;

    // Check if it looks like a table (has header + rows)
    const hasHeader = divTable.querySelector(
      ".header, .thead, [class*='header'], th",
    );
    const hasRows = divTable.querySelector(
      ".row, .tr, [class*='row'], [class*='tr']",
    );

    if (hasHeader && hasRows) {
      const tableData = extractDivTableStructure(divTable, divIndex);
      if (tableData) {
        tables.push(tableData);
      }
    }
  });

  return tables;
}

/**
 * Extract structure from HTML table.
 * @param {HTMLTableElement} table
 * @param {number} index
 * @returns {object}
 */
function extractTableStructure(table, index) {
  const sectionName = resolveSectionName(table) || "Table";

  // Extract columns from header
  const headerCells = table.querySelectorAll("thead th, tr:first-child th");
  const columns = Array.from(headerCells).map((cell, colIndex) => ({
    column_id: `col_${colIndex + 1}`,
    column_name: cell.textContent.trim() || `Column ${colIndex + 1}`,
    column_index: colIndex,
  }));

  // Extract rows
  const rows = [];
  const rowElements = table.querySelectorAll("tbody tr, tr:not(:first-child)");

  rowElements.forEach((row, rowIndex) => {
    const cells = Array.from(row.querySelectorAll("td, th")).map(
      (cell, colIndex) => {
        const input = cell.querySelector(
          'input, select, textarea, [role="textbox"], [role="combobox"]',
        );

        if (input) {
          const fieldName =
            resolveLabel(input) ||
            input.getAttribute("name") ||
            `${columns[colIndex]?.column_name || "Field"} Row ${rowIndex + 1}`;
          const selector = generateSelector(input);
          const fieldType = getFieldType(input) || "text";

          let options = [];
          if (fieldType === "select") {
            options = getSelectOptions(input);
            // If no options found, check for custom autocomplete/dictionary pattern
            if (options.length === 0) {
              const dictionary = input.closest(
                ".autocomplete-control, .js-autocomplete-control, [role='combobox']",
              );
              if (dictionary) {
                const listItems = dictionary.querySelectorAll(
                  "ul.dictionary li, ul[class*='dictionary'] li, .dropdown-menu li, [role='listbox'] li",
                );
                options = Array.from(listItems)
                  .map(
                    (li) =>
                      li.getAttribute("data-name") || li.textContent.trim(),
                  )
                  .filter((opt) => opt.length > 0);
              }
            }
          }

          return {
            field_id: generateFieldId(sectionName, fieldName, selector),
            row: rowIndex + 1,
            column: colIndex + 1,
            column_name: columns[colIndex]?.column_name || "",
            field_name: fieldName,
            field_type: fieldType,
            current_value: getCurrentValue(input),
            selector: selector,
            required: isFieldRequired(input),
            placeholder: getPlaceholder(input),
            help_text: getHelpText(input),
            options: options.length > 0 ? options : undefined,
          };
        }

        return {
          row: rowIndex + 1,
          column: colIndex + 1,
          column_name: columns[colIndex]?.column_name || "",
          text_content: cell.textContent.trim(),
        };
      },
    );

    rows.push({
      row_id: `row_${rowIndex + 1}`,
      row_index: rowIndex,
      cells: cells,
    });
  });

  return {
    table_id: `table_${index + 1}`,
    table_name: sectionName,
    type: "html_table",
    columns: columns,
    rows: rows,
    selector: generateSelector(table),
  };
}

/**
 * Extract structure from grid role element.
 * @param {HTMLElement} grid
 * @param {number} index
 * @returns {object}
 */
function extractGridStructure(grid, index) {
  const sectionName = resolveSectionName(grid) || "Grid";

  // Extract column headers
  const columnHeaders = grid.querySelectorAll(
    '[role="columnheader"], [class*="header"]',
  );
  const columns = Array.from(columnHeaders).map((header, colIndex) => ({
    column_id: `col_${colIndex + 1}`,
    column_name: header.textContent.trim() || `Column ${colIndex + 1}`,
    column_index: colIndex,
  }));

  // Extract rows
  const rowElements = grid.querySelectorAll('[role="row"], [class*="row"]');
  const rows = [];

  rowElements.forEach((row, rowIndex) => {
    const cells = Array.from(
      row.querySelectorAll('[role="gridcell"], [class*="cell"]'),
    ).map((cell, colIndex) => {
      const input = cell.querySelector(
        'input, select, textarea, [role="textbox"], [role="combobox"]',
      );

      if (input) {
        const fieldName =
          resolveLabel(input) ||
          input.getAttribute("name") ||
          `${columns[colIndex]?.column_name || "Field"} Row ${rowIndex + 1}`;
        const selector = generateSelector(input);
        const fieldType = getFieldType(input) || "text";

        let options = [];
        if (fieldType === "select") {
          options = getSelectOptions(input);
          // If no options found, check for custom autocomplete/dictionary pattern
          if (options.length === 0) {
            const dictionary = input.closest(
              ".autocomplete-control, .js-autocomplete-control, [role='combobox']",
            );
            if (dictionary) {
              const listItems = dictionary.querySelectorAll(
                "ul.dictionary li, ul[class*='dictionary'] li, .dropdown-menu li, [role='listbox'] li",
              );
              options = Array.from(listItems)
                .map(
                  (li) => li.getAttribute("data-name") || li.textContent.trim(),
                )
                .filter((opt) => opt.length > 0);
            }
          }
        }

        return {
          field_id: generateFieldId(sectionName, fieldName, selector),
          row: rowIndex + 1,
          column: colIndex + 1,
          column_name: columns[colIndex]?.column_name || "",
          field_name: fieldName,
          field_type: fieldType,
          current_value: getCurrentValue(input),
          selector: selector,
          required: isFieldRequired(input),
          placeholder: getPlaceholder(input),
          help_text: getHelpText(input),
          options: options.length > 0 ? options : undefined,
        };
      }

      return {
        row: rowIndex + 1,
        column: colIndex + 1,
        column_name: columns[colIndex]?.column_name || "",
        text_content: cell.textContent.trim(),
      };
    });

    rows.push({
      row_id: `row_${rowIndex + 1}`,
      row_index: rowIndex,
      cells: cells,
    });
  });

  return {
    table_id: `grid_${index + 1}`,
    table_name: sectionName,
    type: "aria_grid",
    columns: columns,
    rows: rows,
    selector: generateSelector(grid),
  };
}

/**
 * Extract structure from div-based table.
 * @param {HTMLElement} divTable
 * @param {number} index
 * @returns {object}
 */
function extractDivTableStructure(divTable, index) {
  const sectionName = resolveSectionName(divTable) || "Table";

  // Try to find header elements
  const headerElements = divTable.querySelectorAll(
    ".header, .thead, [class*='header']",
  );
  const columns = Array.from(headerElements).map((header, colIndex) => ({
    column_id: `col_${colIndex + 1}`,
    column_name: header.textContent.trim() || `Column ${colIndex + 1}`,
    column_index: colIndex,
  }));

  // Find row elements
  const rowElements = divTable.querySelectorAll(
    ".row, .tr, [class*='row']:not(.header)",
  );
  const rows = [];

  rowElements.forEach((row, rowIndex) => {
    const cells = Array.from(
      row.querySelectorAll(".cell, .td, [class*='cell']"),
    ).map((cell, colIndex) => {
      const input = cell.querySelector(
        'input, select, textarea, [role="textbox"], [role="combobox"]',
      );

      if (input) {
        const fieldName =
          resolveLabel(input) ||
          input.getAttribute("name") ||
          `${columns[colIndex]?.column_name || "Field"} Row ${rowIndex + 1}`;
        const selector = generateSelector(input);

        return {
          field_id: generateFieldId(sectionName, fieldName, selector),
          row: rowIndex + 1,
          column: colIndex + 1,
          column_name: columns[colIndex]?.column_name || "",
          field_name: fieldName,
          field_type: getFieldType(input) || "text",
          current_value: getCurrentValue(input),
          selector: selector,
          required: isFieldRequired(input),
          placeholder: getPlaceholder(input),
          help_text: getHelpText(input),
        };
      }

      return {
        row: rowIndex + 1,
        column: colIndex + 1,
        column_name: columns[colIndex]?.column_name || "",
        text_content: cell.textContent.trim(),
      };
    });

    rows.push({
      row_id: `row_${rowIndex + 1}`,
      row_index: rowIndex,
      cells: cells,
    });
  });

  return {
    table_id: `divtable_${index + 1}`,
    table_name: sectionName,
    type: "div_table",
    columns: columns,
    rows: rows,
    selector: generateSelector(divTable),
  };
}
