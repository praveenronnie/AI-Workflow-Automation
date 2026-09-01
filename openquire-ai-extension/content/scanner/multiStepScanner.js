// Multi-step form scanner - detects wizard-style forms

/**
 * Scan for multi-step form structures.
 * Detects tabs, accordions, wizards, and step indicators.
 * @returns {object}
 */
function scanMultiStepForm() {
  const steps = [];

  // Detect tab-based forms
  const tabPanels = document.querySelectorAll(
    '[role="tabpanel"], .tab-panel, .tab-content, [class*="step"]',
  );

  tabPanels.forEach((panel, index) => {
    if (panel.offsetParent === null) return;

    const stepName =
      panel.getAttribute("aria-label") ||
      panel.getAttribute("data-step-name") ||
      `Step ${index + 1}`;

    // Check if this is the current/visible step
    const isSelected =
      panel.getAttribute("aria-selected") === "true" ||
      panel.classList.contains("active") ||
      panel.classList.contains("show");

    steps.push({
      step_id: `step_${index + 1}`,
      step_name: stepName,
      step_index: index,
      is_current: isSelected,
      element: panel,
      selector: generateSelector(panel),
    });
  });

  // Detect accordion-based forms
  const accordions = document.querySelectorAll(
    '[role="region"][aria-expanded], .accordion, [class*="accordion"]',
  );

  accordions.forEach((accordion, index) => {
    if (accordion.offsetParent === null) return;

    const stepName =
      accordion.getAttribute("aria-label") ||
      accordion.getAttribute("aria-labelledby") ||
      accordion.querySelector("h1,h2,h3,h4,h5,h6")?.textContent.trim() ||
      `Section ${index + 1}`;

    const isExpanded = accordion.getAttribute("aria-expanded") === "true";

    // Avoid duplicates with tab panels
    const existing = steps.find(
      (s) => s.selector === generateSelector(accordion),
    );
    if (!existing) {
      steps.push({
        step_id: `accordion_${index + 1}`,
        step_name: stepName,
        step_index: index,
        is_current: isExpanded,
        element: accordion,
        selector: generateSelector(accordion),
      });
    }
  });

  // Detect wizard progress indicators
  const progressIndicators = document.querySelectorAll(
    '.wizard, .progress, [class*="wizard"], [class*="stepper"], [role="progressbar"]',
  );

  let wizardSteps = [];
  progressIndicators.forEach((indicator) => {
    const stepItems = indicator.querySelectorAll(
      '.step, .wizard-step, [role="tab"], [class*="step"]',
    );

    stepItems.forEach((item, index) => {
      const stepName =
        item.getAttribute("aria-label") ||
        item.textContent.trim() ||
        `Step ${index + 1}`;

      const isComplete =
        item.classList.contains("complete") ||
        item.classList.contains("done") ||
        item.getAttribute("data-status") === "complete";

      const isCurrent =
        item.classList.contains("active") ||
        item.classList.contains("current") ||
        item.getAttribute("aria-selected") === "true";

      wizardSteps.push({
        step_id: `wizard_${index + 1}`,
        step_name: stepName,
        step_index: index,
        is_current: isCurrent,
        is_complete: isComplete,
        selector: generateSelector(item),
      });
    });
  });

  // Merge wizard steps with detected steps
  if (wizardSteps.length > 0) {
    // Add wizard metadata to steps
    steps.forEach((step, index) => {
      const wizardStep = wizardSteps[index];
      if (wizardStep) {
        step.wizard_info = {
          is_complete: wizardStep.is_complete,
          total_steps: wizardSteps.length,
        };
      }
    });
  }

  return {
    has_multi_step: steps.length > 0,
    total_steps: steps.length,
    current_step: steps.find((s) => s.is_current)?.step_index || 0,
    steps: steps,
  };
}

/**
 * Get the current step element.
 * @returns {HTMLElement|null}
 */
function getCurrentStepElement() {
  const multiStep = scanMultiStepForm();
  return multiStep.steps[multiStep.current_step]?.element || null;
}

/**
 * Get all step elements.
 * @returns {Array<HTMLElement>}
 */
function getAllStepElements() {
  const multiStep = scanMultiStepForm();
  return multiStep.steps.map((s) => s.element);
}
