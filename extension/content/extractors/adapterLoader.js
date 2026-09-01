// Adapter loader - loads adapter config JSON files and registers them into
// the global ApiExtractorRegistry. Adapter JSON files are the declarative
// source of truth for how a platform's forms are extracted.

const ADAPTER_INDEX_PATH = "adapters/index.json";

let loadPromise = null;

function getRegistry() {
  if (window.ApiExtractorRegistry) return window.ApiExtractorRegistry;
  throw new Error("ApiExtractorRegistry is not available.");
}

async function loadAdapterConfig(path) {
  const url = chrome.runtime.getURL(path);
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to load adapter config ${path}: ${response.status}`);
  }
  return response.json();
}

async function loadAdapters() {
  if (loadPromise) return loadPromise;
  loadPromise = (async () => {
    const registry = getRegistry();
    const index = await loadAdapterConfig(ADAPTER_INDEX_PATH);
    const adapterIds = index?.adapters || [];
    for (const id of adapterIds) {
      const path = `adapters/${id}.adapter.json`;
      try {
        const config = await loadAdapterConfig(path);
        registry.register(config);
        console.log("[ADAPTER] Registered:", config.id);
      } catch (error) {
        console.warn("[ADAPTER] Failed to load", path, error);
      }
    }
    return registry;
  })();
  return loadPromise;
}

async function resolveAdapter(host, url) {
  const registry = await loadAdapters();
  return registry.match(host, url);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { loadAdapters, resolveAdapter, ADAPTER_INDEX_PATH };
}