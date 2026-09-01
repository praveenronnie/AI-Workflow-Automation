// Adapter registry - loads and validates platform adapter configs.
// Adapters are declarative JSON configs that describe how a platform's
// form fields/sections are extracted and converted into a backend payload.
// Executable logic (API extractors, parsers) is registered as *named
// handlers*; adapter JSON references handlers by name, so content.js never
// needs to know which platform it is running on.

class AdapterRegistry {
  constructor() {
    this.adapters = new Map();
    this.handlers = new Map();
  }

  register(adapterConfig) {
    if (!adapterConfig || !adapterConfig.id) {
      throw new Error("Adapter config must have an id.");
    }
    this.adapters.set(adapterConfig.id, adapterConfig);
  }

  /**
   * Register an executable handler under a namespaced name, e.g.
   * "openquire.buildSchema". Adapter JSON entry points reference these names.
   * @param {string} name
   * @param {Function} fn - (adapterConfig, strategy, ...args) => Promise<any>
   */
  registerHandler(name, fn) {
    if (typeof fn !== "function") {
      throw new Error(`Handler '${name}' must be a function.`);
    }
    this.handlers.set(name, fn);
  }

  getHandler(name) {
    return this.handlers.get(name) || null;
  }

  /**
   * Run a strategy declared on the adapter.
   * @param {object} adapter - resolved adapter config
   * @param {string} strategyName - "api" | "dom" | ...
   * @param  {...any} args - forwarded to the handler after adapter/strategy
   */
  async runStrategy(adapter, strategyName, ...args) {
    if (!adapter) throw new Error("runStrategy requires a resolved adapter.");
    const strategy = adapter?.extraction?.strategies?.[strategyName];
    if (!strategy) {
      throw new Error(
        `Adapter '${adapter.id}' has no '${strategyName}' strategy.`,
      );
    }
    const handler = this.getHandler(strategy.entry);
    if (!handler) {
      throw new Error(
        `No handler registered for entry '${strategy.entry}' (adapter '${adapter.id}').`,
      );
    }
    return handler(adapter, strategy, ...args);
  }

  get(adapterId) {
    return this.adapters.get(adapterId) || null;
  }

  has(adapterId) {
    return this.adapters.has(adapterId);
  }

  match(host, url) {
    const candidates = Array.from(this.adapters.values());
    const normalizedHost = (host || "").toLowerCase();
    const normalizedUrl = url || "";
    for (const adapter of candidates) {
      const match = adapter.match || {};
      const hosts = match.hosts || [];
      if (hosts.some((h) => normalizedHost.includes(h))) {
        return adapter;
      }
      const patterns = match.urlPatterns || [];
      if (
        patterns.length > 0 &&
        patterns.some((p) => this.matchesPattern(normalizedUrl, p))
      ) {
        return adapter;
      }
    }
    return null;
  }

  matchesPattern(url, pattern) {
    const regex = pattern.replace(/\{[^}]+\}/g, "[a-zA-Z0-9_-]+");
    return new RegExp(regex).test(url);
  }

  getSupportedDomains(adapterId) {
    const adapter = this.get(adapterId);
    if (!adapter) return [];
    return adapter.supportedDomains || [];
  }

  list() {
    return Array.from(this.adapters.values());
  }
}

const adapterRegistry = new AdapterRegistry();

if (typeof window !== "undefined") {
  window.ApiExtractorRegistry = adapterRegistry;
  window.AdapterRegistry = AdapterRegistry;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { AdapterRegistry, adapterRegistry };
}