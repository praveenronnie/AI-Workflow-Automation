/* FormIQ Sample UI Test Harness - plain JS, fetch-based. */
"use strict";

/* --------------------------------------------------------- *
 *  State
 * --------------------------------------------------------- */
const state = {
  backend: "http://localhost:8000",
  token: null,
  email: null,
  reportId: null,
  lockToken: null,
  formSchema: null,        // loaded local copy (structured)
  mappings: new Map(),     // field_id -> { value, confidence, source, option_id, ... }
  decisions: new Map(),    // field_id -> { status:"accept"|"reject"|null, value }
  jobs: [],
  jobsPending: 0,          // extraction jobs still running
  jobsFailed: 0,           // extraction jobs that ended failed
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* --------------------------------------------------------- *
 *  API log
 * --------------------------------------------------------- */
function logApi(method, path, status, detail) {
  const line = `[${new Date().toLocaleTimeString()}] ${method} ${path}` +
    (status !== undefined ? `  -> ${status}` : "") +
    (detail ? `\n    ${detail}` : "");
  const body = $("#logBody");
  body.append(line + "\n");
  while (body.childNodes.length > 700) body.removeChild(body.firstChild);
  body.scrollTop = body.scrollHeight;
}

function ok(r) { return r.status >= 200 && r.status < 300; }

/* --------------------------------------------------------- *
 *  HTTP helper
 * --------------------------------------------------------- */
async function api(method, path, { body, form, headers = {}, timeoutMs = 120000 } = {}) {
  const req = { method, headers: { ...headers } };
  if (state.token) req.headers.Authorization = `Bearer ${state.token}`;
  if (form) {
    if (form instanceof FormData) {
      req.body = form;
    } else {
      req.body = new FormData();
      if (Array.isArray(form)) {
        for (const [name, value] of form) req.body.append(name, value);
      } else {
        for (const [k, v] of Object.entries(form)) req.body.append(k, v);
      }
    }
  } else if (body !== undefined) {
    req.headers["Content-Type"] = "application/json";
    req.body = JSON.stringify(body);
  }

  let res, text = "", json = null;
  try {
    res = await fetch(state.backend + path, { ...req, signal: AbortSignal.timeout(timeoutMs) });
    text = await res.text();
    try { json = text ? JSON.parse(text) : null; } catch { json = { text }; }
    logApi(method, path, res.status, text.slice(0, 900));
    return { status: res.status, ok: res.ok, json, text };
  } catch (e) {
    const msg = (e?.name === "TimeoutError" || e?.name === "AbortError")
      ? `timeout after ${timeoutMs}ms` : String(e?.message || e);
    logApi(method, path, 0, "NETWORK ERROR: " + msg);
    console.error("[harness]", method, path, e);
    return { status: 0, ok: false, json: null, text: "NETWORK ERROR: " + msg };
  }
}

/* --------------------------------------------------------- *
 *  Rendering helpers
 * --------------------------------------------------------- */
function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [children].flat()) {
    if (c === null || c === undefined) continue;
    node.append(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function optionMap(field) {
  const opts = (field.options && typeof field.options === "object" && !Array.isArray(field.options))
    ? field.options : {};
  const idToText = new Map(Object.entries(opts).map(([id, t]) => [String(id), String(t)]));
  return { idToText, size: opts.length };
}

function fieldId(table, field) {
  return String(field.rowId || field.field_id || field.id || field.fieldName || table.tableName);
}

function tablesWithFields() {
  return (state.formSchema?.tables || []).filter((t) => (t.fields || []).length > 0);
}

function autoAcceptThreshold() { return 0.8; }
/* --------------------------------------------------------- *
 *  Step navigation
 * --------------------------------------------------------- */
function goStep(n) {
  $$("section.panel").forEach((s) => (s.hidden = s.id !== `step-${n}`));
  $$("#stepNav .step-btn").forEach((b) => (b.classList.toggle("active", +b.dataset.step === n)));
}
$$("#stepNav .step-btn").forEach((b) => (b.addEventListener("click", () => goStep(+b.dataset.step))));

/* --------------------------------------------------------- *
 *  Step 0 - Connect / auth
 * --------------------------------------------------------- */
async function health() {
  const r = await api("GET", "/health", { timeoutMs: 8000 });
  const ready = await api("GET", "/ready", { timeoutMs: 8000 });
  $("#healthBody").textContent = JSON.stringify({
    health: r.json, ready: ready.json, http: { health: r.status, ready: ready.status },
  }, null, 2);
  const readyOk = ok(ready) && r.ok;
  const pill = $("#healthPill");
  if (pill) {
    pill.className = "pill " + (readyOk ? "pill-ok" : "pill-err");
    pill.textContent = readyOk ? "online" : "degraded";
  }
  return { alive: r.ok, ready: readyOk };
}

async function makeUser() {
  state.email = `tester_${Math.random().toString(36).slice(2, 10)}@test.local`;
  const pass = "S3cure-Passw0rd!";
  await api("POST", "/auth/register", { body: { email: state.email, password: pass } });
  const tok = await api("POST", "/auth/token", {
    form: [["username", state.email], ["password", pass]],
    timeoutMs: 20000,
  });
  state.token = tok.json?.access_token;
  $("#authInfo").textContent =
    `${state.email}  .  token ${state.token ? "OK acquired" : "X FAILED (status " + tok.status + ")"}`;
  return state.token;
}

async function loadDomains() {
  const r = await api("GET", "/domains/", { timeoutMs: 10000 });
  const doms = r.json || [];
  const sel = $("#domainSelect");
  sel.innerHTML = "";
  doms.forEach((d) => sel.append(el("option", { value: d.name }, [d.display_name || d.name])));
  if (doms.length === 0) sel.append(el("option", { value: "pca_site_assessment" }, ["pca_site_assessment"]));
  logApi("GET", "/domains/", r.status, `loaded ${doms.length} domains`);
}

function setConn(alive) {
  const dot = $("#connDot");
  dot.className = "dot " + (alive ? "dot-green" : "dot-red");
  $("#connText").textContent = alive
    ? `Connected . ${state.backend} . ${state.email || "no user"}`
    : "Backend unreachable";
}

$("#btnConnect").addEventListener("click", async () => {
  state.backend = $("#backendUrl").value.trim() || "http://localhost:8000";
  const h = await health();
  if (!h.alive) { setConn(false); return; }
  setConn(true);
  $("#healthCard").hidden = false;
  $("#authCard").hidden = false;
  await makeUser();
  setConn(true);
  loadDomains();
});

$("#btnResetUser").addEventListener("click", async () => { await makeUser(); setConn(true); });

/* --------------------------------------------------------- *
 *  Step 1 - Report link, lock, schema load + render + post
 * --------------------------------------------------------- */
async function loadSchemaFile() {
  const r = await fetch("form_schema.json");
  if (!r.ok) throw new Error("Could not load form_schema.json: " + r.status);
  state.formSchema = await r.json();
}

async function linkReport() {
  $("#reportCard").hidden = false;
  const url = $("#sourceUrl").value.trim();
  const r = await api("POST", "/reports/link",
    { body: { source_url: url, source_domain: "openquire" } });
  if (!ok(r)) { $("#reportBody").textContent = "link FAILED (HTTP " + r.status + "): " + r.text; return; }
  state.reportId = r.json.report_id;
  $("#reportBody").textContent = JSON.stringify(r.json, null, 2);

  const lk = await api("POST", `/reports/${state.reportId}/lock`, {});
  if (ok(lk)) {
    state.lockToken = lk.json.lock_token;
    $("#reportBody").textContent += "\n\n[lock] " + JSON.stringify(lk.json, null, 2);
  } else {
    $("#reportBody").textContent += "\n\n[lock FAILED] " + lk.text;
    return;
  }
  startLockHeartbeat();
  $("#btnPostSchema").disabled = false;
  $("#btnUpload").disabled = false;
}

$("#btnLinkReport").addEventListener("click", async () => {
  $("#reportCard").hidden = false;
  $("#reportBody").textContent = "Working...";
  if (!state.token) {
    $("#reportBody").textContent = "Not connected - do Step 0 (Connect) first, then retry this button.";
    return;
  }
  const btn = $("#btnLinkReport");
  btn.disabled = true;
  try {
    await loadSchemaFile();
    renderFormReplica();
    const tables = tablesWithFields();
    $("#schemaStatsBody").textContent = JSON.stringify({
      report_id: state.formSchema.report_id,
      tables: state.formSchema.tables.length,
      tables_with_fields: tables.length,
      total_fields: tables.reduce((n, t) => n + t.fields.length, 0),
    }, null, 2);
    $("#schemaStatsCard").hidden = false;
    await linkReport();
  } catch (e) {
    $("#reportBody").textContent = "ERROR: " + (e?.message || e);
    console.error("[harness] step1", e);
  } finally { btn.disabled = false; }
});

$("#btnPostSchema").addEventListener("click", async () => {
  const payload = {
    form_schema: state.formSchema,
    scanned_payload: { captured_at: new Date().toISOString() },
    trigger_intent: false,
    source_url: $("#sourceUrl").value.trim(),
    source_domain: "openquire",
  };
  const r = await api("POST", `/reports/${state.reportId}/form_schema`, {
    body: payload, headers: { "X-Lock-Token": state.lockToken },
  });
  $("#reportBody").textContent += "\n\n[schema POST] " +
    JSON.stringify(r.json || { text: r.text }, null, 2);
});

/* Render the editable form replica from state.formSchema. */
function buildReplica() {
  const root = el("div", { class: "form-replica" });
  for (const t of tablesWithFields()) {
    const sec = el("div", { class: "form-section" });
    const title = el("div", { class: "fs-title" }, [t.tableName]);
    title.appendChild(el("span", { class: "fs-count" }, [`${(t.fields || []).length} field${(t.fields || []).length === 1 ? "" : "s"}`]));
    sec.append(title);
    for (const f of t.fields) {
      const id = fieldId(t, f);
      const { idToText } = optionMap(f);
      const block = el("div", { class: "field-block" });
      const label = el("label", { html: escapeHtml(f.fieldName || id) });
      if (f.value) label.appendChild(el("span", { class: "badge-filled" }, ["original"]));
      block.append(label);
      const wrap = el("div", { class: "field-val" });
      let input;
      if (idToText.size > 0) {
        input = el("select", { class: "field-select" });
        input.append(el("option", { value: "" }, ["-"]));
        for (const [oid, txt] of idToText) input.append(el("option", { value: oid }, [txt]));
        if (f.value && idToText.has(String(f.value))) input.value = String(f.value);
      } else {
        input = el("textarea", { class: "field-text", rows: 1 });
        input.value = f.value || "";
      }
      input.dataset.tableId = String(t.tableId);
      input.dataset.rowId = String(f.rowId || "");
      input.dataset.fieldId = id;
      wrap.append(input);
      block.append(wrap);
      sec.append(block);
    }
    root.append(sec);
  }
  return root;
}

function renderFormReplica() {
  const host = $("#formReplica");
  host.innerHTML = "";
  host.append(buildReplica());
}

/* Keep-alive the report lock every 60 s (300 s TTL). */
let _beatTimer = null;
function startLockHeartbeat() {
  if (_beatTimer) clearInterval(_beatTimer);
  _beatTimer = setInterval(async () => {
    if (!state.reportId || !state.lockToken) return;
    const r = await api("POST", `/reports/${state.reportId}/lock/heartbeat`,
      { body: { lock_token: state.lockToken } });
    if (!ok(r)) logApi("POST", `/reports/${state.reportId}/lock/heartbeat`, r.status,
      "heartbeat FAILED: " + r.text);
    else logApi("POST", `/reports/${state.reportId}/lock/heartbeat`, r.status, "ok");
  }, 60000);
}
/* --------------------------------------------------------- *
 *  Step 2 - Upload documents (PDF / image split) + poll jobs
 * --------------------------------------------------------- */
const IMAGE_EXT = ["jpg", "jpeg", "png", "bmp", "gif", "tiff", "webp"];

function groupFiles(files) {
  const pdfs = [], images = [], zips = [], skipped = [];
  for (const f of files) {
    const ext = (f.name.split(".").pop() || "").toLowerCase();
    if (ext === "pdf") pdfs.push(f);
    else if (ext === "zip") zips.push(f);
    else if (IMAGE_EXT.includes(ext)) images.push(f);
    else skipped.push(f.name);
  }
  return { pdfs, images, zips, skipped };
}

$("#btnUpload").addEventListener("click", async () => {
  const files = Array.from($("#fileInput").files);
  if (files.length === 0) { $("#uploadStatus").textContent = "Select at least one file."; return; }
  const groups = groupFiles(files);
  $("#uploadStatus").textContent = "Uploading -> " + JSON.stringify({
    pdf: groups.pdfs.length, image: groups.images.length, zip: groups.zips.length, skipped: groups.skipped,
  });
  $("#btnUpload").disabled = true;

  const out = { input: { pdf: groups.pdfs.length, image: groups.images.length, zip: groups.zips.length },
    responses: [], jobs: [] };

  // One doc_type per PDF (scanner | handwritten), as a JSON array string.
  const docTypes = JSON.stringify(Array.from({ length: groups.pdfs.length },
    () => $("#docType").value));

  if (groups.pdfs.length > 0) {
    const fd = new FormData();
    groups.pdfs.forEach((f) => fd.append("files", f, f.name));
    fd.append("doc_types", docTypes);
    const r = await api("POST", `/reports/${state.reportId}/upload/pdf`, {
      form: fd, headers: { "X-Lock-Token": state.lockToken }, timeoutMs: 60000,
    });
    out.responses.push({ endpoint: "upload/pdf", status: r.status, body: r.json || r.text });
    if (r.json?.job_id) out.jobs.push({ job_id: r.json.job_id, type: "pdf" });
  }

  const imgZip = [...groups.images, ...groups.zips];
  if (imgZip.length > 0) {
    const fd = new FormData();
    imgZip.forEach((f) => fd.append("files", f, f.name));
    const r = await api("POST", `/reports/${state.reportId}/upload/image`, {
      form: fd, headers: { "X-Lock-Token": state.lockToken }, timeoutMs: 60000,
    });
    out.responses.push({ endpoint: "upload/image", status: r.status, body: r.json || r.text });
    if (r.json?.job_id) out.jobs.push({ job_id: r.json.job_id, type: "image" });
  }

  $("#uploadResultBody").textContent = JSON.stringify(out, null, 2);
  $("#uploadResultCard").hidden = false;
  $("#btnUpload").disabled = false;
  // Map stays locked until every extraction job reaches a terminal state (see jobsDone).

  if (out.jobs.length > 0) {
    $("#jobPollCard").hidden = false;
    $("#jobPollBody").textContent = "Waiting for job completion...\n";
    state.jobsPending = out.jobs.length;
    state.jobsFailed = 0;
    $("#mapStatus").textContent = "Extraction in progress — Map is locked until all jobs complete.";
    for (const j of out.jobs)
      pollJob(j.job_id, j.type).then((st) => {
        state.jobsPending--;
        if (st !== "completed" && st !== "success") state.jobsFailed++;
        jobsDone();
      });
  } else {
    state.jobsPending = 0; state.jobsFailed = 0;
    $("#jobPollBody").textContent = "No job_id returned (processed inline). See upload responses above.";
    $("#jobPollCard").hidden = false;
    jobsDone();
  }
});

/* Called when every tracked extraction job reached a terminal state. */
function jobsDone() {
  if (state.jobsPending > 0) return;
  if (state.jobsFailed > 0) {
    $("#mapStatus").textContent =
      `${state.jobsFailed} extraction job(s) FAILED. ` +
      "Fix/re-upload the documents, or use the override below to map anyway (negative test).";
    $("#btnMapOverride").hidden = false;
  } else {
    $("#mapStatus").textContent = "";
    $("#btnMap").disabled = false;
    $("#mapStatus").textContent = "All extraction jobs completed — ready to map.";
  }
}

async function pollJob(jobId, type) {
  const seen = new Set();
  for (let i = 0; i < 200; i++) {
    await new Promise((r) => setTimeout(r, 4000));
    const r = await api("GET", `/reports/jobs/${jobId}`, { timeoutMs: 20000 });
    if (!ok(r)) { logApi("GET", `/reports/jobs/${jobId}`, r.status, r.text); return "failed"; }
    const st = r.json?.status;
    if (seen.has(st)) continue;
    seen.add(st);
    $("#jobPollBody").textContent =
      `poll ${i}: ${type} job ${jobId} -> ${st}` + (r.json?.error ? " error=" + r.json.error : "") +
      "\n" + $("#jobPollBody").textContent;
    if (st === "completed" || st === "failed" || st === "success") {
      logApi("GET", `/reports/jobs/${jobId}`, r.status, `${type} job ${st}`);
      return st;
    }
  }
  logApi("GET", `/reports/jobs/${jobId}`, 0, `${type} job poll exhausted (still not terminal)`);
  return "failed";
}
/* --------------------------------------------------------- *
 *  Step 3 - Map
 * --------------------------------------------------------- */
async function runMappingNow() {
  $("#mapStatus").textContent = "Running mapping (can take a while)...";
  $("#btnMap").disabled = true;
  const domain = $("#domainSelect").value || "pca_site_assessment";
  const r = await api("POST", `/reports/${state.reportId}/map`, {
    body: { domain, form_schema: state.formSchema },
    headers: { "X-Lock-Token": state.lockToken }, timeoutMs: 180000,
  });
  $("#btnMap").disabled = false;
  if (!ok(r)) { $("#mapStatus").textContent = "Map FAILED: " + r.text; return; }
  $("#mapStatus").textContent = "";

  const rows = r.json.mappings || [];
  state.mappings.clear();
  rows.forEach((m) => state.mappings.set(m.field_id, m));
  const matched = rows.filter((m) => m.matched).length;
  const byMethod = {};
  rows.forEach((m) => { const k = m.mapping_method || "unknown"; byMethod[k] = (byMethod[k] || 0) + 1; });

  $("#mapResultBody").textContent = JSON.stringify({
    status: r.json.status,
    evidence_count: r.json.evidence_count,
    total: rows.length, matched, unmatched: rows.length - matched,
    by_method: byMethod,
    confidence_bins: r.json.mapping_summary?.confidence_bins || null,
  }, null, 2);
  $("#mapResultCard").hidden = false;
  logApi("POST", `/reports/${state.reportId}/map`, r.status, `mapped ${matched}/${rows.length}`);

  renderReview();
  goStep(4);
}

/* Guards + wiring: normal button checks everything; override skips job-failure checks. */
$("#btnMap").addEventListener("click", async () => {
  if (!state.reportId || !state.lockToken) {
    $("#mapStatus").textContent = "Link the report first (Step 1); upload documents before mapping.";
    return;
  }
  if (state.jobsPending > 0) {
    $("#mapStatus").textContent =
      `Extraction still in progress (${state.jobsPending} job(s) running) — wait for completion before mapping.`;
    return;
  }
  await runMappingNow();
});
/* Negative-test escape hatch: map anyway even when extraction jobs failed. */
$("#btnMapOverride").addEventListener("click", async () => {
  if (!state.reportId || !state.lockToken) {
    $("#mapStatus").textContent = "Link the report first (Step 1); upload documents before mapping.";
    return;
  }
  logApi("OVERRIDE", "map", 0, "mapping despite failed extraction jobs (intentional negative test)");
  await runMappingNow();
});

/* --------------------------------------------------------- *
 *  Step 4 - Human verification (tables)
 * --------------------------------------------------------- */
function decisionFor(id) { return state.decisions.get(id); }

function renderReview() {
  // (re)initialize decisions: keep existing edits; auto-accept high-confidence matches.
  for (const [id, m] of state.mappings) {
    const cur = state.decisions.get(id);
    if (!cur || (cur.status === null && cur.value === undefined)) {
      if (m.matched && m.confidence >= autoAcceptThreshold()) {
        state.decisions.set(id, { status: "accept", value: m.value });
      } else {
        state.decisions.set(id, { status: null, value: m.value });
      }
    }
  }

  const tabs = $("#reviewTabs");
  tabs.innerHTML = "";
  const tables = tablesWithFields();
  const tabButtons = [];
  tables.forEach((t, i) => {
    const b = el("button", { class: "decision-btn", "data-tidx": i },
      [`${t.tableName} (${(t.fields || []).length})`]);
    if (i === 0) b.classList.add("active");
    tabButtons.push(b);
    tabs.append(b);
  });
  tabButtons.forEach((b) => b.addEventListener("click", () => {
    tabButtons.forEach((x) => x.classList.remove("active"));
    b.classList.add("active");
    $$("#reviewTables .review-block").forEach((node) =>
      (node.hidden = node.dataset.tidx !== b.dataset.tidx));
  }));

  const host = $("#reviewTables");
  host.innerHTML = "";
  tables.forEach((t, ti) => {
    const box = el("div", { class: "review-block", "data-tidx": ti });
    const table = el("table", { class: "review-table" });
    const head = el("thead");
    head.append(el("tr",
      ["Field", "Value (editable)", "Conf", "Method", "Source", "Decision"]
        .map((h) => el("th", {}, [h]))));
    const body = el("tbody");
    for (const f of t.fields) {
      const id = fieldId(t, f);
      const m = state.mappings.get(id) || { value: null, confidence: 0, matched: false };
      const dec = decisionFor(id);
      const tr = el("tr");
      tr.dataset.fieldId = id;
      if (dec?.status === "accept") tr.classList.add("row-accept");
      tr.append(el("td", {}, [f.fieldName || id]));

      const valueTd = el("td", { class: "value-cell" });
      const ta = el("textarea", { rows: 1 });
      ta.value = dec?.value != null ? dec.value : "";
      ta.addEventListener("input", () => {
        const d = state.decisions.get(id) || { status: null };
        d.value = ta.value;
        state.decisions.set(id, d);
        updateCounters();
      });
      valueTd.append(ta);
      tr.append(valueTd);

      const conf = m.confidence ?? 0;
      const cls = conf >= 0.8 ? "hi" : conf >= 0.5 ? "md" : "lo";
      tr.append(el("td", {}, [el("span", { class: "conf-pill " + cls },
        [(conf * 100).toFixed(0) + "%"])]));
      tr.append(el("td", {}, [el("span", { class: "method-tag" }, [m.mapping_method || "—"])]));
      tr.append(el("td", { title: m.source_excerpt || "" },
        [el("span", { class: "src-ref" }, [m.source_ref || "—"])]));

      const decTd = el("td", {});
      const btnYes = el("button", { class: "decision-btn" }, ["OK"]);
      const btnNo = el("button", { class: "decision-btn" }, ["NO"]);
      if (dec?.status === "accept") btnYes.classList.add("ok");
      if (dec?.status === "reject") btnNo.classList.add("no");
      btnYes.addEventListener("click", () => {
        const d = state.decisions.get(id) || { value: ta.value };
        d.status = "accept"; state.decisions.set(id, d);
        refreshDecisionRow(tr, id, ta);
      });
      btnNo.addEventListener("click", () => {
        const d = state.decisions.get(id) || { value: ta.value };
        d.status = "reject"; state.decisions.set(id, d);
        refreshDecisionRow(tr, id, ta);
      });
      decTd.append(btnYes, btnNo);
      tr.append(decTd);
      body.append(tr);
    }
    table.append(head, body);
    box.append(table);
    host.append(box);
  });
  updateCounters();
  const emptyEl = $("#emptyReview");
  if (emptyEl) emptyEl.hidden = tables.length > 0;
}
function refreshDecisionRow(tr, id, ta) {
  const d = state.decisions.get(id);
  tr.classList.toggle("row-accept", d?.status === "accept");
  const btns = Array.from(tr.querySelectorAll(".decision-btn"));
  if (btns.length >= 2) {
    btns[0].classList.toggle("ok", d?.status === "accept");
    btns[1].classList.toggle("no", d?.status === "reject");
  }
  ta.value = d?.value != null ? d.value : "";
  updateCounters();
}

function acceptedCount() {
  let n = 0;
  for (const d of state.decisions.values()) if (d.status === "accept") n++;
  return n;
}
function updateCounters() {
  const n = acceptedCount();
  $("#acceptCounter").textContent = n ? ` ${n} accepted` : "";
  $("#btnFill").textContent = `Fill form (${n} fields)`;
  $("#btnFill").disabled = n === 0;
}

$("#btnAcceptAll").addEventListener("click", () => {
  state.decisions.forEach((d) => {
    if (d.status !== "reject") { d.status = "accept"; if (d.value == null) d.value = ""; }
  });
  renderReview();
});
$("#btnClearDecisions").addEventListener("click", () => { state.decisions.clear(); renderReview(); });

/* --------------------------------------------------------- *
 *  Step 5 - Submit: fill the rendered form (DOM events like extension)
 * --------------------------------------------------------- */
function setNativeValue(elInput, value) {
  const proto = elInput.tagName === "SELECT" ? HTMLSelectElement : HTMLTextAreaElement;
  const idx = elInput.tagName === "SELECT" ? "selectedIndex" : "value";
  try {
    const setter = Object.getOwnPropertyDescriptor(proto.prototype, idx)?.set;
    if (setter) setter.call(elInput, value); else elInput[idx] = value;
  } catch { elInput[idx] = value; }
}
function dispatchFillEvents(elInput) {
  elInput.dispatchEvent(new Event("focus", { bubbles: true }));
  elInput.dispatchEvent(new Event("input", { bubbles: true }));
  elInput.dispatchEvent(new Event("change", { bubbles: true }));
  elInput.dispatchEvent(new Event("blur", { bubbles: true }));
}

$("#btnFill").addEventListener("click", () => {
  const host = $("#formReplicaFilled");
  host.innerHTML = "";
  host.append(buildReplica());
  let filled = 0, skipped = 0;
  const details = [];

  const inputs = Array.from(host.querySelectorAll("[data-field-id]"));
  for (const [fid, d] of state.decisions) {
    if (d.status !== "accept") { skipped++; continue; }
    const node = inputs.find((n) => n.dataset.fieldId === fid);
    if (!node) { skipped++; continue; }
    const value = d.value == null ? "" : String(d.value);
    if (node.tagName === "SELECT") {
      const opts = Array.from(node.options);
      let match = opts.find((o) => o.value === value || o.text === value);
      if (!match) match = opts.find((o) => o.value !== "");
      if (match) { node.value = match.value; dispatchFillEvents(node); filled++; details.push([fid, value]); }
      else skipped++;
    } else {
      setNativeValue(node, value);
      dispatchFillEvents(node);
      filled++; details.push([fid, value]);
    }
  }

  Array.from(host.querySelectorAll(".field-block")).forEach((b) => {
    const input = b.querySelector("[data-field-id]");
    if (input && state.decisions.get(input.dataset.fieldId)?.status === "accept") {
      const mark = b.querySelector(".badge-filled");
      if (!mark) b.prepend(el("span", { class: "badge-filled" }, ["filled"]));
    }
  });

  $("#fillResultBody").textContent = JSON.stringify(
    { filled, skipped, total: state.decisions.size, filled_fields: details.slice(0, 40) }, null, 2);
  $("#fillResultCard").hidden = false;
  logApi("FILL", `formReplica#${state.reportId}`, 200, `filled ${filled}, skipped ${skipped}`);
  goStep(5);
});

$("#btnResetForm").addEventListener("click", () => {
  $("#formReplicaFilled").innerHTML = "";
  $("#fillResultCard").hidden = true;
});

/* --------------------------------------------------------- *
 *  Log clear
 * --------------------------------------------------------- */
$("#btnClearLog").addEventListener("click", () => { $("#logBody").textContent = ""; });
