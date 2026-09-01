// Unified scanner - single-pass DOM traversal for all form elements
// expandAllSections is available globally from uiHelpers.js

/**
 * Scan the entire form in a single DOM pass.
 * Collects sections, fields, images, tables, and multi-step info together.
 * @returns {Promise<object>}
 */
async function scanEntireForm() {
  const result = {
    sections: [],
    fields: [],
    images: [],
    tables: [],
    multiStep: null,
    scanLog: [],
    stats: {
      elementsVisited: 0,
      fieldsFound: 0,
      sectionsFound: 0,
      imagesFound: 0,
      tablesFound: 0,
      duration: 0,
    },
  };

  const startTime = performance.now();
  const processedElements = new WeakSet();
  const sectionMap = new Map(); // Map elements to their section
  const imageSrcSet = new Set(); // Track image src to avoid duplicates
  let anonymousFieldCounter = 0; // Unique counter for fields without labels

  // Pre-compute all potential section containers
  const sectionCandidates = document.querySelectorAll(
    'fieldset, section, [role="region"], [role="group"], [data-section], .form-section, .section, .section-block, .card, .panel, [class*="card"], [class*="panel"]',
  );

  // Also treat tables as potential sections for image detection
  const tableElements = document.querySelectorAll(
    'table, [role="grid"], [role="table"]',
  );
  tableElements.forEach((table, index) => {
    const sectionName = `Table ${index + 1}`;
    // Register table itself and its children in sectionMap
    const section = { element: table, name: sectionName };
    const childNodes = Array.from(table.querySelectorAll("*"));
    childNodes.forEach((child) => {
      sectionMap.set(child, section);
    });
    // Add table to sections array
    result.sections.push(section);
    result.stats.sectionsFound++;
    result.scanLog.push(`Found section: "${sectionName}"`);
  });

  // Build section map with unique names - NO FALLBACK to className
  const sectionNameCount = new Map();
  sectionCandidates.forEach((el) => {
    let name = "";
    const legend = el.querySelector("legend");
    if (legend) {
      name = legend.textContent.trim();
    } else {
      const heading = el.querySelector("h1, h2, h3, h4, h5, h6");
      if (heading) {
        name = heading.textContent.trim();
      } else {
        const ariaLabel = el.getAttribute("aria-label");
        if (ariaLabel) {
          name = ariaLabel;
        } else {
          const labelledBy = el.getAttribute("aria-labelledby");
          if (labelledBy) {
            const labelEl = document.getElementById(labelledBy);
            if (labelEl) name = labelEl.textContent.trim();
          }
        }
      }
    }

    // Skip if no semantic label found - NO FALLBACK to className
    if (!name) return;

    // Clean up section name - remove excessive whitespace/newlines
    name = name.replace(/\s+/g, " ").trim();

    // Truncate very long section names (>100 chars)
    if (name.length > 100) {
      name = name.substring(0, 97) + "...";
    }

    // Ensure unique section names by appending count for duplicates
    const count = sectionNameCount.get(name) || 0;
    sectionNameCount.set(name, count + 1);
    const uniqueName = count > 0 ? `${name} (${count + 1})` : name;

    const section = { element: el, name: uniqueName };
    result.sections.push(section);
    result.stats.sectionsFound++;
    result.scanLog.push(`Found section: "${uniqueName}"`);

    // Mark all children as belonging to this section
    const childNodes = Array.from(el.querySelectorAll("*"));
    childNodes.forEach((child) => {
      sectionMap.set(child, section);
    });
  });

  /**
   * Check if element is a decorative icon/logo that should be skipped.
   * @param {HTMLElement} el
   * @param {string} classStr
   * @returns {boolean}
   */
  function isDecorativeElement(el, classStr) {
    // Check for known icon/logo classes
    if (/icon|logo|avatar|thumb|badge|sprite|symbol/i.test(classStr)) {
      return true;
    }
    if (
      el.getAttribute("data-icon") ||
      el.getAttribute("role") === "presentation"
    ) {
      return true;
    }
    // Check dimensions (very small elements are likely decorative)
    const rect = el.getBoundingClientRect();
    if (rect.width < 20 || rect.height < 20) {
      return true;
    }
    return false;
  }

  /**
   * Check if element is inside a detected panel/section.
   * @param {HTMLElement} el
   * @returns {boolean}
   */
  function isInsidePanel(el) {
    return sectionMap.has(el);
  }

  /**
   * Extract and add an image from an element.
   * @param {HTMLElement} el
   * @param {string} src
   * @param {string} alt
   * @param {number} width
   * @param {number} height
   * @param {boolean} requirePanel - if true, only add if element is inside a panel
   */
  function addImage(el, src, alt, width, height, requirePanel = false) {
    if (!src || imageSrcSet.has(src)) return;

    const className = el.className || "";
    const classStr =
      typeof className === "string" ? className : className.toString();

    if (isDecorativeElement(el, classStr)) {
      return;
    }

    // Skip images not inside panels if required
    if (requirePanel && !isInsidePanel(el)) {
      return;
    }

    // Get section name from sectionMap
    const section = sectionMap.get(el);
    const sectionName = section ? section.name : "General";

    imageSrcSet.add(src);
    result.images.push({
      type: "image_reference",
      src: src,
      alt: alt,
      width: width,
      height: Math.round(height),
      section_name: sectionName,
    });
    result.stats.imagesFound++;
  }

  // Single DOM walk to collect everything
  function walkDOM(node) {
    if (processedElements.has(node)) return;

    if (node.nodeType !== Node.ELEMENT_NODE) {
      // Still recurse into children
      Array.from(node.childNodes).forEach(walkDOM);
      return;
    }

    processedElements.add(node);
    result.stats.elementsVisited++;

    const tag = node.tagName.toLowerCase();

    // Check for form fields
    if (
      node.matches(
        'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]), textarea, select',
      )
    ) {
      if (node.disabled) {
        Array.from(node.children).forEach(walkDOM);
        return;
      }

      const section = sectionMap.get(node) || { name: "General" };
      // Only process standard form field elements
      const validFormTags = ["INPUT", "TEXTAREA", "SELECT"];
      if (!validFormTags.includes(node.tagName)) {
        Array.from(node.children).forEach(walkDOM);
        return;
      }
      const fieldResult = createFieldFromElement(
        node,
        section.name,
        anonymousFieldCounter,
      );
      if (fieldResult) {
        anonymousFieldCounter = fieldResult.counter;
        result.fields.push(fieldResult.field);
        result.stats.fieldsFound++;
        result.scanLog.push(
          `Found field: "${fieldResult.field.field_name}" (${fieldResult.field.field_type}) in "${section.name}"`,
        );
      }
    }

    // Check for <img> elements (only inside panels)
    else if (node.matches("img")) {
      if (!isInsidePanel(node)) {
        Array.from(node.children).forEach(walkDOM);
        return;
      }
      const rect = node.getBoundingClientRect();
      if (rect.width >= 50 && rect.height >= 50) {
        const src = node.src || node.getAttribute("data-src") || "";
        const alt =
          node.getAttribute("alt") || node.getAttribute("aria-label") || "";
        addImage(node, src, alt, rect.width, rect.height, false);
      }
    }

    // Check for <svg> elements (only inside panels)
    else if (node.matches("svg, canvas, picture")) {
      if (!isInsidePanel(node)) {
        Array.from(node.children).forEach(walkDOM);
        return;
      }
      const rect = node.getBoundingClientRect();
      if (rect.width >= 50 && rect.height >= 50) {
        const src =
          node.src ||
          node.getAttribute("data-src") ||
          node.outerHTML?.substring(0, 200) ||
          "";
        const alt =
          node.getAttribute("alt") || node.getAttribute("aria-label") || "";
        addImage(node, src, alt, rect.width, rect.height, false);
      }
    }

    // Check for images inside table cells (only if cell is inside panel)
    else if (node.matches("td, th")) {
      if (!isInsidePanel(node)) {
        Array.from(node.children).forEach(walkDOM);
        return;
      }
      const imagesInCell = node.querySelectorAll("img, svg, canvas, picture");
      imagesInCell.forEach((img) => {
        const imgRect = img.getBoundingClientRect();
        // Lower threshold for images in table cells
        if (imgRect.width >= 10 && imgRect.height >= 10) {
          const src =
            img.src ||
            img.getAttribute("data-src") ||
            img.outerHTML?.substring(0, 200) ||
            "";
          const alt =
            img.getAttribute("alt") || img.getAttribute("aria-label") || "";
          addImage(img, src, alt, imgRect.width, imgRect.height, false);
        }
      });
    }

    // Check for tables
    else if (node.matches('table, [role="grid"], [role="table"]')) {
      const tableData = extractTableStructure(node, result.tables.length);
      if (tableData) {
        result.tables.push(tableData);
        result.stats.tablesFound++;
      }
    }

    // Check for multi-step indicators
    else if (
      node.matches(
        '[role="tabpanel"], .tab-panel, .accordion, .wizard, [class*="step"]',
      )
    ) {
      // Multi-step detection handled separately
    }

    // Recurse into children
    Array.from(node.children).forEach(walkDOM);
  }

  // Expand all collapsible sections before scanning
  console.log("[SCANNER] Expanding collapsible sections...");
  await expandAllSections();
  console.log("[SCANNER] Sections expanded");

  // Start walking from body
  walkDOM(document.body);

  // Post-process: detect CSS background images
  scanBackgroundImages(result, imageSrcSet, sectionMap);

  // Post-process: detect images in all remaining tables (fallback for edge cases)
  scanAllTableImages(result, imageSrcSet);

  // Post-process: multi-step detection
  result.multiStep = scanMultiStepForm();
  if (result.multiStep?.has_multi_step) {
    result.scanLog.push(
      `Multi-step form detected: ${result.multiStep.total_steps} steps`,
    );
  }

  result.stats.duration = performance.now() - startTime;
  result.scanLog.push(
    `Scan completed in ${result.stats.duration.toFixed(2)}ms`,
  );

  return result;
}

/**
 * Scan all tables for images (fallback detection).
 * @param {object} result
 * @param {Set} imageSrcSet
 */
function scanAllTableImages(result, imageSrcSet) {
  const allTables = document.querySelectorAll(
    'table, [role="grid"], [role="table"]',
  );
  allTables.forEach((table, index) => {
    const imagesInTable = table.querySelectorAll("img, svg, canvas, picture");
    const sectionName = `Table ${index + 1}`;
    imagesInTable.forEach((img) => {
      const imgRect = img.getBoundingClientRect();
      // Lower threshold for table images
      if (imgRect.width >= 10 && imgRect.height >= 10) {
        const src =
          img.src ||
          img.getAttribute("data-src") ||
          img.outerHTML?.substring(0, 200) ||
          "";
        if (!src || imageSrcSet.has(src)) return;
        imageSrcSet.add(src);
        result.images.push({
          type: "image_reference",
          src: src,
          alt: img.getAttribute("alt") || img.getAttribute("aria-label") || "",
          width: imgRect.width,
          height: Math.round(imgRect.height),
          section_name: sectionName,
        });
        result.stats.imagesFound++;
      }
    });
  });
}

/**
 * Scan all visible elements for CSS background images.
 * Catches images applied via style attribute or CSS classes.
 * @param {object} result
 * @param {Set} imageSrcSet
 * @param {Map} sectionMap
 */
function scanBackgroundImages(result, imageSrcSet, sectionMap) {
  const allElements = document.querySelectorAll("*");

  allElements.forEach((el) => {
    // Skip if already processed or not inside a panel
    if (
      !el.offsetParent ||
      el.tagName.toLowerCase() === "img" ||
      !sectionMap.has(el)
    )
      return;

    const style = window.getComputedStyle(el);
    const backgroundImage = style.backgroundImage;

    if (backgroundImage && backgroundImage !== "none") {
      // Extract URL from background-image
      const urlMatch = backgroundImage.match(/url\(["']?([^"')]+)["']?\)/);
      if (urlMatch && urlMatch[1]) {
        const bgSrc = urlMatch[1];
        const rect = el.getBoundingClientRect();

        // Only add if it's reasonably sized
        if (rect.width >= 20 && rect.height >= 20) {
          // Resolve relative URLs
          let absoluteSrc = bgSrc;
          if (bgSrc.startsWith("http")) {
            absoluteSrc = bgSrc;
          } else if (bgSrc.startsWith("/")) {
            absoluteSrc = window.location.origin + bgSrc;
          } else {
            absoluteSrc = new URL(bgSrc, window.location.href).href;
          }

          // Skip if already tracked by a DOM image element
          if (!imageSrcSet.has(absoluteSrc) && !imageSrcSet.has(bgSrc)) {
            imageSrcSet.add(absoluteSrc);

            const className = el.className || "";
            const classStr =
              typeof className === "string" ? className : className.toString();

            const section = sectionMap.get(el);
            const sectionName = section ? section.name : "General";

            result.images.push({
              type: "background_image",
              src: absoluteSrc,
              alt:
                el.getAttribute("aria-label") || el.getAttribute("alt") || "",
              width: rect.width,
              height: Math.round(rect.height),
              location: el.tagName.toLowerCase(),
              section_name: sectionName,
            });
            result.stats.imagesFound++;
          }
        }
      }
    }
  });
}

/**
 * Create field object from element.
 * @param {HTMLElement} el
 * @param {string} sectionName
 * @returns {object|null}
 */
function createFieldFromElement(el, sectionName, counter) {
  let newCounter = counter;
  const type = (el.getAttribute("type") || "text").toLowerCase();
  let fieldType;

  if (el.tagName.toLowerCase() === "textarea") {
    fieldType = FIELD_TYPES.TEXTAREA;
  } else if (el.tagName.toLowerCase() === "select") {
    fieldType = FIELD_TYPES.SELECT;
  } else if (
    el.closest(
      "[role='combobox'], .autocomplete-control, .js-autocomplete-control, [class*='autocomplete'], [class*='dropdown']",
    )
  ) {
    fieldType = FIELD_TYPES.SELECT;
  } else {
    switch (type) {
      case "text":
      case "email":
      case "tel":
      case "url":
      case "number":
      case "date":
      case "password":
      case "search":
      case "color":
      case "range":
      case "datetime-local":
      case "time":
      case "month":
      case "week":
        fieldType = FIELD_TYPES.TEXT;
        break;
      case "checkbox":
        fieldType = FIELD_TYPES.CHECKBOX;
        break;
      case "radio":
        fieldType = FIELD_TYPES.RADIO;
        break;
      case "file":
        fieldType = FIELD_TYPES.FILE;
        break;
      default:
        // Log unknown field types for debugging instead of silently dropping
        console.warn(`Unknown field type: "${type}" for element`, el);
        fieldType = FIELD_TYPES.TEXT;
    }
  }

  let fieldName =
    resolveLabel(el) || el.getAttribute("name") || "Unnamed Field";

  // For truly anonymous fields, append a unique counter to ensure unique field_id
  const isAnonymous = fieldName === "Unnamed Field" && !el.getAttribute("name");
  if (isAnonymous) {
    newCounter = counter + 1;
    fieldName = `Unnamed Field ${newCounter}`;
  }

  // For select/autocomplete elements, extract options from custom dropdowns
  let options = [];
  if (fieldType === FIELD_TYPES.SELECT) {
    options = getSelectOptions(el);

    // If no options found, check for custom autocomplete/dictionary pattern
    if (options.length === 0) {
      const dictionary = el.closest(
        ".autocomplete-control, .js-autocomplete-control, [role='combobox']",
      );
      if (dictionary) {
        const listItems = dictionary.querySelectorAll(
          "ul.dictionary li, ul[class*='dictionary'] li, .dropdown-menu li, [role='listbox'] li",
        );
        options = Array.from(listItems)
          .map((li) => {
            const name = li.getAttribute("data-name") || li.textContent.trim();
            const value = li.getAttribute("data-id") || name;
            return name;
          })
          .filter((opt) => opt.length > 0);
      }
    }
  }

  // Note: selector NOT generated here for performance - will be generated on-demand

  return {
    counter: newCounter,
    field: {
      field_id: generateFieldId(
        sectionName,
        fieldName,
        `${el.tagName.toLowerCase()}|${el.getAttribute("type") || ""}|${el.getAttribute("name") || ""}|${isAnonymous ? newCounter : ""}`,
      ),
      section_name: sectionName,
      field_name: fieldName,
      qualified_label: getQualifiedLabel(sectionName, fieldName),
      field_type: fieldType,
      current_value: getCurrentValue(el),
      options: options,
      required: isFieldRequired(el),
      placeholder: getPlaceholder(el),
      help_text: getHelpText(el),
    },
  };
}

/**
 * Extract table structure (simplified version).
 * @param {HTMLElement} table
 * @param {number} index
 * @returns {object|null}
 */
function extractTableStructure(table, index) {
  const sectionName = resolveSectionName(table) || "Table";
  const headerCells = table.querySelectorAll("thead th, tr:first-child th");
  const columns = Array.from(headerCells).map((cell, colIndex) => ({
    column_id: `col_${colIndex + 1}`,
    column_name: cell.textContent.trim() || `Column ${colIndex + 1}`,
    column_index: colIndex,
  }));

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
                  .map((li) => {
                    const name =
                      li.getAttribute("data-name") || li.textContent.trim();
                    const value = li.getAttribute("data-id") || name;
                    return name;
                  })
                  .filter((opt) => opt.length > 0);
              }
            }
          }

          return {
            field_id: generateFieldId(sectionName, fieldName, ""),
            row: rowIndex + 1,
            column: colIndex + 1,
            column_name: columns[colIndex]?.column_name || "",
            field_name: fieldName,
            field_type: fieldType,
            current_value: getCurrentValue(input),
            // selector: generateSelector(input), // Deferred
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
    // selector: generateSelector(table), // Deferred
  };
}
