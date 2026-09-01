// UI state detection and manipulation helpers

/**
 * Check if an element is visible in the viewport.
 * @param {HTMLElement} el - Element to check
 * @returns {boolean} - True if visible
 */
function isElementVisible(el) {
  if (!el) return false;

  const style = window.getComputedStyle(el);
  if (
    style.display === "none" ||
    style.visibility === "hidden" ||
    style.opacity === "0"
  ) {
    return false;
  }

  const rect = el.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
}

/**
 * Check if an element is locked by MUTEX or similar mechanism.
 * @param {HTMLElement} el - Element to check
 * @returns {boolean} - True if locked
 */
function isElementLocked(el) {
  if (!el) return false;

  const hasLockAttribute =
    el.hasAttribute("data-locked") ||
    el.hasAttribute("aria-disabled") ||
    el.classList.contains("locked") ||
    el.classList.contains("disabled");

  let parent = el.parentElement;
  while (parent && parent !== document.body) {
    if (
      parent.hasAttribute("data-locked") ||
      parent.getAttribute("aria-disabled") === "true" ||
      parent.classList.contains("locked")
    ) {
      return true;
    }
    parent = parent.parentElement;
  }

  return hasLockAttribute;
}

/**
 * Check if element is in viewport.
 * @param {HTMLElement} el - Element to check
 * @returns {boolean} - True if in viewport
 */
function isElementInViewport(el) {
  if (!el) return false;
  const rect = el.getBoundingClientRect();
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <=
      (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
}

/**
 * Scroll element into view with specified behavior.
 * @param {HTMLElement} el - Element to scroll
 * @param {string} behavior - Scroll behavior ("auto" or "smooth")
 */
function scrollIntoViewSafely(el, behavior = "auto") {
  if (!el) return;
  try {
    el.scrollIntoView({ behavior, block: "center", inline: "center" });
  } catch (e) {
    const rect = el.getBoundingClientRect();
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    const scrollLeft =
      window.pageXOffset || document.documentElement.scrollLeft;
    window.scrollTo({
      top: scrollTop + rect.top - window.innerHeight / 2 + rect.height / 2,
      left: scrollLeft + rect.left - window.innerWidth / 2 + rect.width / 2,
      behavior: behavior === "smooth" ? "smooth" : "auto",
    });
  }
}

/**
 * Detect if a dropdown is currently open.
 * @returns {HTMLElement|null}
 */
function detectOpenDropdown() {
  const openSelect = document.querySelector("select:focus");
  if (openSelect) return openSelect;

  const openCombobox = document.querySelector(
    "[role='combobox'][aria-expanded='true']",
  );
  if (openCombobox) return openCombobox;

  const openMenu = document.querySelector(
    ".dropdown-menu.show, .dropdown-menu[aria-hidden='false']",
  );
  if (openMenu) return openMenu;

  return null;
}

/**
 * Wait for UI to become idle (no animations, no locks).
 * @param {number} timeout - Max wait time in ms
 * @param {AbortSignal} [signal]
 * @returns {Promise<boolean>}
 */
async function waitForUIIdle(timeout = 2000, signal) {
  const start = Date.now();

  while (Date.now() - start < timeout) {
    if (signal?.aborted) {
      throw new Error("Operation aborted");
    }

    const lockedElements = document.querySelectorAll(
      "[data-locked], .locked, [aria-disabled='true']",
    );
    if (lockedElements.length === 0) {
      const animatedElements = document.querySelectorAll("*");
      let hasAnimation = false;
      for (const el of animatedElements) {
        const style = window.getComputedStyle(el);
        if (style.animation && style.animation !== "none") {
          hasAnimation = true;
          break;
        }
      }

      if (!hasAnimation) {
        return true;
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  return false;
}

/**
 * Expand all collapsible sections/accordions.
 * @param {AbortSignal} [signal]
 * @returns {Promise<number>}
 */
async function expandAllSections(signal) {
  const expandableSelectors = [
    "[aria-expanded='false']",
    ".collapsed",
    "details:not([open])",
    "[data-expanded='false']",
  ];

  let expandedCount = 0;

  for (const selector of expandableSelectors) {
    const elements = document.querySelectorAll(selector);
    for (const el of elements) {
      if (signal?.aborted) {
        throw new Error("Operation aborted");
      }

      try {
        el.click();
        expandedCount++;
        await new Promise((resolve) => setTimeout(resolve, 100));
      } catch (e) {
        // Element not clickable, skip
      }
    }
  }

  return expandedCount;
}

/**
 * Save minimal UI state for restoration.
 * @returns {object}
 */
function saveUIState() {
  return {
    scrollX: window.scrollX,
    scrollY: window.scrollY,
    activeElement: document.activeElement,
    openDropdown: detectOpenDropdown(),
  };
}

/**
 * Restore UI state from snapshot.
 * @param {object} state
 */
function restoreUIState(state) {
  if (!state) return;

  window.scrollTo(state.scrollX, state.scrollY);

  if (state.activeElement && state.activeElement.focus) {
    try {
      state.activeElement.focus();
    } catch (e) {
      // Element no longer focusable
    }
  }
}

/**
 * Press Escape key to close dropdowns.
 */
function closeDropdowns() {
  const event = new KeyboardEvent("keydown", {
    key: "Escape",
    keyCode: 27,
    bubbles: true,
  });
  document.dispatchEvent(event);
}

// Attach to global scope for content script access
if (typeof window !== "undefined") {
  window.isElementVisible = isElementVisible;
  window.isElementLocked = isElementLocked;
  window.isElementInViewport = isElementInViewport;
  window.scrollIntoViewSafely = scrollIntoViewSafely;
  window.detectOpenDropdown = detectOpenDropdown;
  window.waitForUIIdle = waitForUIIdle;
  window.expandAllSections = expandAllSections;
  window.saveUIState = saveUIState;
  window.restoreUIState = restoreUIState;
  window.closeDropdowns = closeDropdowns;
}
