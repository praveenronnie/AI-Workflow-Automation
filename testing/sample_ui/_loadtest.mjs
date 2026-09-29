import { readFileSync } from "fs";
const src = readFileSync("testing/sample_ui/app.js", "utf8");
const handlers = [];
const makeEl = () => new Proxy({}, {
  get(t, p) {
    if (p === "addEventListener") return (ev, fn) => handlers.push(ev);
    if (p === "classList") return { add(){}, remove(){}, toggle(){}, contains(){return false;} };
    if (p === "style") return {};
    if (p === "appendChild" || p === "removeChild" || p === "cloneNode") return () => makeEl();
    if (p === "querySelector" || p === "querySelectorAll") return p === "querySelectorAll" ? () => [] : () => makeEl();
    if (p === "getBoundingClientRect") return () => ({});
    if (typeof p === "string") return t[p] ?? makeEl();
    return undefined;
  },
  set() { return true; }
});
globalThis.document = {
  getElementById: () => makeEl(),
  createElement: () => makeEl(),
  querySelector: () => makeEl(),
  querySelectorAll: () => [],
  addEventListener: (ev, fn) => handlers.push(ev),
  visibilityState: "visible",
  body: makeEl()
};
globalThis.window = globalThis;
globalThis.fetch = async () => ({ ok: true, status: 200, headers: { get(){ return "application/json"; } }, json: async () => ({}) });
globalThis.setInterval = () => 0;
globalThis.clearInterval = () => {};
globalThis.alert = () => {};
globalThis.confirm = () => true;
await import("file://" + process.cwd().replace(/\\/g, "/") + "/testing/sample_ui/app.js");
console.log("LOAD_OK, handlers:", handlers.length);