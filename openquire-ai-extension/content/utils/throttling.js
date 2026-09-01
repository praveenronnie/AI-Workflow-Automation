// Throttling utility for dropdown scanning

/**
 * Create a throttle function that limits how often a function can be called.
 * @param {Function} fn - Function to throttle
 * @param {number} delay - Minimum delay between calls in ms
 * @returns {Function} Throttled function
 */
function throttle(fn, delay) {
  let lastCall = 0;
  return function (...args) {
    const now = Date.now();
    if (now - lastCall >= delay) {
      lastCall = now;
      return fn.apply(this, args);
    }
  };
}

/**
 * Sleep for a specified duration.
 * @param {number} ms - Milliseconds to sleep
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<void>}
 */
function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new Error("Operation aborted"));
      return;
    }
    const timeoutId = setTimeout(() => resolve(), ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timeoutId);
      reject(new Error("Operation aborted"));
    });
  });
}

/**
 * Wait for a condition to become true, polling at intervals.
 * @param {Function} condition - Function returning boolean
 * @param {number} interval - Polling interval in ms
 * @param {number} timeout - Max wait time in ms
 * @param {AbortSignal} [signal] - Optional abort signal
 * @returns {Promise<boolean>} - True if condition met, false on timeout
 */
async function waitFor(condition, interval = 100, timeout = 5000, signal) {
  const start = Date.now();
  while (Date.now() - start < timeout) {
    if (signal?.aborted) {
      throw new Error("Operation aborted");
    }
    if (condition()) {
      return true;
    }
    await sleep(interval, signal);
  }
  return false;
}

// Attach to global scope for content script access
if (typeof window !== "undefined") {
  window.throttle = throttle;
  window.sleep = sleep;
  window.waitFor = waitFor;
}
