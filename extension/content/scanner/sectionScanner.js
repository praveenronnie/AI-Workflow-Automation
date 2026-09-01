// Section scanner - detects visible sections and subsections in the form

/**
 * Scan the document for visible section containers.
 * Sections are identified by:
 * - <fieldset> elements
 * - <section> elements
 * - Elements with role="region" or role="group"
 * - Elements with data-section attributes
 * - Elements with common enterprise class names (card, panel, accordion)
 * - Heading-based grouping (h1-h6)
 * @returns {Array<{element: HTMLElement, name: string}>}
 */
function scanSections() {
  const sections = [];
  const seen = new Set();

  // Collect potential section containers
  const candidates = document.querySelectorAll(
    'fieldset, section, [role="region"], [role="group"], [data-section], .form-section, .section, .card, .panel, .accordion, [class*="card"], [class*="panel"]',
  );

  candidates.forEach((el) => {
    if (seen.has(el)) return;
    seen.add(el);

    // Skip hidden elements
    if (el.offsetParent === null) return;

    let name = "";

    // Try to extract section name
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
          // Check for aria-labelledby
          const labelledBy = el.getAttribute("aria-labelledby");
          if (labelledBy) {
            const labelEl = document.getElementById(labelledBy);
            if (labelEl) name = labelEl.textContent.trim();
          }
          if (!name) {
            name =
              el.getAttribute("data-section") ||
              el.className ||
              "Untitled Section";
          }
        }
      }
    }

    if (name) {
      sections.push({ element: el, name });
    }
  });

  // Fallback: group fields by their closest heading ancestor
  if (sections.length === 0) {
    const headings = document.querySelectorAll("h1, h2, h3, h4, h5, h6");
    headings.forEach((heading) => {
      if (heading.offsetParent === null) return;
      sections.push({
        element: heading.parentElement,
        name: heading.textContent.trim(),
      });
    });
  }

  return sections;
}

/**
 * Scan for images that may need VLM processing.
 * Filters out icons, logos, and avatars.
 * @returns {Array<{type: string, src: string, alt: string, width: number, height: number}>}
 */
function scanImages() {
  const images = [];
  const candidates = document.querySelectorAll("img, svg, canvas, picture");

  candidates.forEach((el) => {
    // Skip hidden elements
    if (el.offsetParent === null) return;

    // Get dimensions
    const rect = el.getBoundingClientRect();
    const width = rect.width;
    const height = rect.height;

    // Filter out small icons (likely not document images)
    if (width < 50 || height < 50) return;

    // Check for common icon/logo class patterns
    const className = el.className || "";
    const classStr =
      typeof className === "string" ? className : className.toString();
    if (
      classStr.match(/icon|logo|avatar|thumb|badge/i) ||
      el.getAttribute("data-icon") ||
      el.getAttribute("role") === "presentation"
    ) {
      return;
    }

    // Get source
    let src = "";
    if (el.tagName === "IMG") {
      src = el.src || el.getAttribute("data-src") || "";
    } else if (el.tagName === "SVG") {
      src = el.outerHTML.substring(0, 200);
    } else if (el.tagName === "CANVAS") {
      src = el.toDataURL ? el.toDataURL().substring(0, 200) : "";
    } else if (el.tagName === "PICTURE") {
      const img = el.querySelector("img");
      src = img ? img.src : "";
    }

    images.push({
      type: "image_reference",
      src: src,
      alt: el.getAttribute("alt") || el.getAttribute("aria-label") || "",
      width: width,
      height: height,
    });
  });

  return images;
}
