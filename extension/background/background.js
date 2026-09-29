// Background service worker for OpenQuire AI Extension
// All backend API communication is handled here in the service worker.

const EXTENSION = {
  STORAGE_KEYS: {
    SOURCE_DATA: "sourceData",
    FORM_SCHEMA: "formSchema",
    MAPPINGS: "mappings",
    USER_REPORTS: "userReports",
    CURRENT_REPORT_ID: "currentReportId",
    ACCESS_TOKEN: "accessToken",
    USER_EMAIL: "userEmail",
  },
};

const DEFAULT_API_BASE = "http://localhost:8000";

// Resolve the API base from an admin-set storage override (options page /
// build-time), falling back to the local default. Kept async so callers stay
// uniform; reads are cheap and cached by the browser.
async function getApiBase() {
  try {
    const { apiBase } = await chrome.storage.local.get("apiBase");
    const base = (apiBase || DEFAULT_API_BASE).trim().replace(/\/+$/, "");
    return base || DEFAULT_API_BASE;
  } catch (e) {
    return DEFAULT_API_BASE;
  }
}

// Clear report-scoped state (docs, schema, mappings, active report/lock).
// Used on login/signup so a new user does not inherit the previous user's
// report context across sessions (storage is browser-wide, not per-user).
async function clearReportState() {
  if (extensionState.currentReportId) {
    await releaseReportLock().catch(() => {});
  }
  extensionState.currentReportId = null;
  extensionState.activeReport = null;
  extensionState.formSchema = null;
  extensionState.mappings = {};
  extensionState.sourceData = null;
  extensionState.userReports = [];
  extensionState.currentLockToken = null;
  extensionState.reportByUrl = new Map();
  extensionState.mappingApproved = false;
  await chrome.storage.local.remove([
    EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID,
    EXTENSION.STORAGE_KEYS.FORM_SCHEMA,
    EXTENSION.STORAGE_KEYS.MAPPINGS,
    EXTENSION.STORAGE_KEYS.SOURCE_DATA,
    EXTENSION.STORAGE_KEYS.USER_REPORTS,
  ]);
}

// Read the JWT access token previously stored by the extension (from /auth/token).
async function getAccessToken() {
  try {
    const { accessToken } = await chrome.storage.local.get(
      EXTENSION.STORAGE_KEYS.ACCESS_TOKEN,
    );
    const token = accessToken || "";
    if (token) extensionState.accessToken = token;
    return token;
  } catch (e) {
    return "";
  }
}

async function loadUserReports() {
  try {
    // Skip the request entirely when no token is present â€“ the backend would
    // reject it with 401/403 and the panel would boot into an error state.
    const token = await getAccessToken();
    if (!token) {
      console.debug("[BACKGROUND] loadUserReports skipped â€“ no access token");
      extensionState.userReports = [];
      extensionState.reportByUrl = new Map();
      return { success: true, data: [] };
    }

    const result = await apiRequest(`/reports/user`, { method: "GET" }, 10000);
    extensionState.userReports = result || [];
    extensionState.reportByUrl = new Map();
    for (const report of extensionState.userReports) {
      if (report.report_url) {
        extensionState.reportByUrl.set(report.report_url, report);
      }
    }
    await chrome.storage.local.set({
      [EXTENSION.STORAGE_KEYS.USER_REPORTS]: extensionState.userReports,
    });
    extensionState.apiOffline = false;
    notifyUIStateChange();
    return { success: true, data: extensionState.userReports };
  } catch (error) {
    // Network-level failures (API offline) are expected when the server
    // isn't running — keep the console quiet and surface the offline state.
    if (/failed to fetch|networkerror|load failed/i.test(error.message || "")) {
      console.debug("[BACKGROUND] API unreachable while loading reports");
      extensionState.apiOffline = true;
      notifyUIStateChange();
      return { success: false, error: "API offline" };
    }
    console.error("[BACKGROUND] Failed to load user reports:", error);
    return { success: false, error: error.message };
  }
}

async function getActiveReport() {
  try {
    // No endpoint calls before login
    const token = await getAccessToken();
    if (!token) return null;

    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!tab?.url) return null;

    // First check the URL map (from cached user reports fetched after login)
    const cached = extensionState.reportByUrl.get(tab.url);
    if (cached) {
      extensionState.activeReport = cached;
      extensionState.currentReportId = cached.report_id;
      extensionState.formSchema = cached.form_schema || null;
      await acquireReportLock(cached.report_id);
      notifyUIStateChange();
      return cached;
    }

    // Second try: extract report_id from URL path or query params
    const pathMatch = tab.url.match(/\/reports\/([a-zA-Z0-9_-]+)/);
    let reportId = null;
    if (pathMatch) {
      reportId = pathMatch[1];
    } else {
      const urlParams = new URLSearchParams(tab.url.split("?")[1] || "");
      reportId =
        urlParams.get("report_id") ||
        urlParams.get("reportId") ||
        urlParams.get("id") ||
        null;
    }

    if (reportId) {
      // Fetch full report details
      const detail = await apiRequest(
        `/reports/${reportId}`,
        {
          method: "GET",
        },
        10000,
      );
      extensionState.activeReport = detail;
      extensionState.currentReportId = detail.report_id;
      extensionState.formSchema = detail.form_schema || null;
      extensionState.source_url = detail.report_url;
      await acquireReportLock(detail.report_id);
      notifyUIStateChange();
      return detail;
    }

    // No match â†’ indicate scan form needed
    await releaseReportLock();
    extensionState.activeReport = null;
    extensionState.currentReportId = null;
    extensionState.formSchema = null;
    notifyUIStateChange();
    return null;
  } catch (error) {
    console.error("[BACKGROUND] Failed to get active report:", error);
    return null;
  }
}

// --- Tab/page context (Option C) ------------------------------------------
// The side panel is per-window, not per-tab. Resolve whether the ACTIVE tab
// is the page the active report was created from, so the panel can be honest
// about context mismatches instead of silently scanning page B into report A.
async function resolvePageContext() {
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!tab?.url || /^(chrome|edge|about|chrome-extension):/i.test(tab.url)) {
      return null;
    }
    const sourceUrl = extensionState.activeReport?.report_url || "";
    const matchesReport = !!sourceUrl && tab.url === sourceUrl;
    return { url: tab.url, matchesReport };
  } catch (e) {
    return null;
  }
}

async function notifyUIStateChange() {
  const payload = {
    isAuthenticated: extensionState.isAuthenticated,
    userEmail: extensionState.userEmail,
    activeReport: extensionState.activeReport,
    userReports: extensionState.userReports,
    currentReportId: extensionState.currentReportId,
    formSchema: extensionState.formSchema,
    // Report-level processing status for the UI pipeline strip
    reportStatus: extensionState.activeReport?.status || "draft",
    // Phase 6 — lock / read-only state so the side panel can render a banner
    isReadOnly: extensionState.isReadOnly,
    lockHolderUser: extensionState.lockHolderUser,
    hasLock: !!extensionState.currentLockToken,
    lockExpiresAt: extensionState.lockExpiresAt || null,
    // Option C — does the active tab match the report's source page?
    pageContext: await resolvePageContext(),
    // API reachability flag (for the workspace offline hint)
    apiOffline: !!extensionState.apiOffline,
  };
  chrome.runtime.sendMessage({
    action: MESSAGE_ACTIONS.UPDATE_UI_STATE,
    payload,
  }).catch(() => {
    // side panel may not be open — ignore
  });
}

const MESSAGE_ACTIONS = {
  STORE_FORM_SCHEMA: "STORE_FORM_SCHEMA",
  MAP_FIELDS: "MAP_FIELDS",
  UPLOAD_PDF: "UPLOAD_PDF",
  UPLOAD_IMAGE: "UPLOAD_IMAGE",
  LOAD_USER_REPORTS: "LOAD_USER_REPORTS",
  GET_ACTIVE_REPORT: "GET_ACTIVE_REPORT",
  UPDATE_UI_STATE: "UPDATE_UI_STATE",
  // Phase 6 â€” report lock lifecycle
  ACQUIRE_LOCK: "ACQUIRE_LOCK",
  RELEASE_LOCK: "RELEASE_LOCK",
  LOCK_STATE_CHANGED: "LOCK_STATE_CHANGED",
};

const extensionState = {
  accessToken: null,
  isAuthenticated: false,
  userEmail: null,
  currentReportId: null,
  userReports: [],
  reportByUrl: new Map(),
  activeReport: null,
  formSchema: null,
  mappings: null,
  sourceData: null,
  mappingApproved: false,
  // --- Phase 6: report lock lifecycle ---
  // `currentLockToken` is the opaque token returned by POST /reports/{id}/lock
  // for `currentLockId`. Sent back as `X-Lock-Token` on mutating requests so
  // the backend can verify we still hold the lock.
  currentLockId: null,
  currentLockToken: null,
  lockExpiresAt: null, // ISO string of lock expiration (for UI countdown)
  isReadOnly: false, // flipped true when another user holds the lock
  lockHolderUser: null, // email of the user currently holding the lock
  lockHeartbeatTimer: null, // ref to the heartbeat interval
};

// ---------------------------------------------------------------------------
// Phase 6 â€” Report lock lifecycle
// ---------------------------------------------------------------------------
// Only one user may mutate a shared report at a time. The background service
// worker acquires a short-lived lock (POST /reports/{id}/lock), refreshes it
// via a heartbeat, and releases it on report switch / logout. When a different
// user holds the lock the extension flips into read-only mode and surfaces a
// banner via the side-panel UI-state channel.
const LOCK_HEARTBEAT_INTERVAL_MS = 60000;

/**
 * Classify a 409 error detail as a genuine "held by another user" lock
 * conflict. The backend raises 409 with either a structured JSON body (held by
 * another user, includes `locked_by_user`) or a plain string detail (e.g.
 * "Report is deleted"). Only the structured "held by another user" variant
 * flips the extension into read-only mode.
 */
function parseLockConflict(errorText) {
  if (!errorText) return null;
  let parsed = null;
  try {
    parsed = JSON.parse(errorText);
  } catch (e) {
    parsed = null;
  }
  if (typeof parsed === "object" && parsed !== null) {
    if (parsed.locked_by_user !== undefined || parsed.locked_by !== undefined) {
      return {
        holder: parsed.locked_by_user || null,
        message: parsed.message || "Report is locked by another user",
        expires_at: parsed.expires_at || null,
      };
    }
  }
  return null;
}

function stopLockHeartbeat() {
  if (extensionState.lockHeartbeatTimer) {
    clearInterval(extensionState.lockHeartbeatTimer);
    extensionState.lockHeartbeatTimer = null;
  }
}

function startLockHeartbeat(reportId) {
  stopLockHeartbeat();
  extensionState.lockHeartbeatTimer = setInterval(async () => {
    if (
      !extensionState.currentLockToken ||
      extensionState.currentLockId !== reportId
    ) {
      stopLockHeartbeat();
      return;
    }
    try {
      await apiHeartbeatLock(reportId);
    } catch (e) {
      console.warn("[BACKGROUND] Lock heartbeat failed:", e.message);
      // If the server invalidated the lock (expired/stolen), drop it locally
      // and flip into read-only mode. The lock may now be held by another
      // user; we'll learn who on the next 409 from a mutating request.
      if (/expired|not locked|locked/i.test(e.message)) {
        extensionState.currentLockId = null;
        extensionState.currentLockToken = null;
        extensionState.lockExpiresAt = null;
        extensionState.isReadOnly = true;
        extensionState.lockHolderUser = null;
        stopLockHeartbeat();
        notifyUIStateChange();
      }
    }
  }, LOCK_HEARTBEAT_INTERVAL_MS);
}

// Drop the local lock view without notifying the server (used when the server
// tells us the lock is gone, e.g. a stale heartbeat response).
function clearLocalLock(preserveReadOnly = false) {
  extensionState.currentLockToken = null;
  extensionState.currentLockId = null;
  extensionState.lockExpiresAt = null;
  if (!preserveReadOnly) {
    extensionState.isReadOnly = false;
    extensionState.lockHolderUser = null;
  }
  stopLockHeartbeat();
  notifyUIStateChange();
}

// --- Lock REST wrappers ---------------------------------------------------
async function apiAcquireLock(reportId) {
  return apiRequest(
    `/reports/${encodeURIComponent(reportId)}/lock`,
    { method: "POST" },
    8000,
  );
}

async function apiHeartbeatLock(reportId) {
  if (!extensionState.currentLockToken) return false;
  return apiRequest(
    `/reports/${encodeURIComponent(reportId)}/lock/heartbeat`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        lock_token: extensionState.currentLockToken,
      }),
    },
    8000,
  );
}

async function apiReleaseLock(reportId) {
  const token = extensionState.currentLockToken;
  if (!token) return;
  try {
    await apiRequest(
      `/reports/${encodeURIComponent(reportId)}/unlock`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lock_token: token }),
      },
      8000,
    );
  } catch (e) {
    console.warn("[BACKGROUND] Failed to release lock:", e.message);
  }
}

/**
 * Ensure the current user holds a valid lock for `reportId` before a mutating
 * operation. Idempotent: a held, valid lock is reused. If a different user
 * holds the lock the extension enters read-only mode and returns false so the
 * caller can abort. If we were read-only but the other user's lock has since
 * expired, this silently re-acquires.
 */
async function ensureReportLock(reportId) {
  if (!reportId) return true;
  const haveValid =
    extensionState.currentLockId === reportId &&
    extensionState.currentLockToken &&
    !extensionState.isReadOnly;
  if (haveValid) return true;

  try {
    const res = await apiAcquireLock(reportId);
    if (res && res.lock_token) {
      extensionState.currentLockId = reportId;
      extensionState.currentLockToken = res.lock_token;
      extensionState.isReadOnly = false;
      // Gap 2: track server-provided lock expiration so the UI can show a
      // countdown and we can decide when a stale lock is safe to ignore.
      extensionState.lockExpiresAt = res.expires_at || null;
      extensionState.lockHolderUser = null;
      startLockHeartbeat(reportId);
      notifyUIStateChange();
      console.log("[BACKGROUND] Acquired report lock for", reportId);
      return true;
    }
    return true; // unexpected shape â€” proceed best-effort
  } catch (e) {
    if (/LOCK_CONFLICT/.test(e.message)) {
      // Held by another user â€” read-only state already set inside apiRequest.
      return false;
    }
    console.warn("[BACKGROUND] Lock acquire failed:", e.message);
    return true; // proceed; the mutation will surface a clearer error
  }
}

async function acquireReportLock(reportId) {
  await ensureReportLock(reportId);
}

async function releaseReportLock(reportId) {
  const rid = reportId || extensionState.currentReportId;
  if (!rid) return;
  stopLockHeartbeat();
  await apiReleaseLock(rid);
  extensionState.currentLockToken = null;
  extensionState.currentLockId = null;
  extensionState.lockExpiresAt = null;
  extensionState.isReadOnly = false;
  extensionState.lockHolderUser = null;
  notifyUIStateChange();
}

function notifyLockStateChange() {
  chrome.runtime
    .sendMessage({
      action: MESSAGE_ACTIONS.LOCK_STATE_CHANGED,
      payload: {
        isReadOnly: extensionState.isReadOnly,
        lockHolderUser: extensionState.lockHolderUser,
        hasLock: !!extensionState.currentLockToken,
        lockExpiresAt: extensionState.lockExpiresAt || null,
      },
    })
    .catch(() => {});
  notifyUIStateChange();
}

async function apiRequest(endpoint, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // Attach the JWT access token (multi-tenant, user-scoped API).
  const token = await getAccessToken();
  const headers = { ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;

  // Phase 6 â€” attach the active report lock token to mutating requests on the
  // current report so the backend can verify we still hold the lock.
  const mutating = ["POST", "PUT", "DELETE"].includes(options.method);
  if (
    mutating &&
    extensionState.currentLockToken &&
    extensionState.currentReportId
  ) {
    const pathMatch = endpoint.match(/\/reports\/([a-zA-Z0-9_-]+)/);
    if (pathMatch && pathMatch[1] === extensionState.currentReportId) {
      headers["X-Lock-Token"] = extensionState.currentLockToken;
    }
  }

  try {
    const apiBase = await getApiBase();
    const response = await fetch(`${apiBase}${endpoint}`, {
      ...options,
      headers,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();

      // Session expired / invalid token -> force the UI back to the login
      // screen instead of letting every report call fail silently.
      if (response.status === 401) {
        extensionState.accessToken = null;
        extensionState.isAuthenticated = false;
        try {
          await chrome.storage.local.remove([
            EXTENSION.STORAGE_KEYS.ACCESS_TOKEN,
          ]);
        } catch (e) {
          /* ignore */
        }
        throw new Error(`AUTH_REQUIRED: ${errorText || "Session expired"}`);
      }

      // Phase 6 â€” a structured 409 "held by another user" flips the extension
      // into read-only mode (banner via the UI-state channel). Non-lock 409s
      // (e.g. "Report is deleted") fall through to the generic error below.
      if (response.status === 409) {
        const conflict = parseLockConflict(errorText);
        if (conflict) {
          extensionState.isReadOnly = true;
          extensionState.lockHolderUser = conflict.holder;
          notifyLockStateChange();
          throw new Error(`LOCK_CONFLICT: ${conflict.message}`);
        }
      }

      throw new Error(
        `API error: ${response.status} ${response.statusText} - ${errorText}`,
      );
    }

    return await response.json();
  } catch (error) {
    clearTimeout(timeoutId);
    if (error.name === "AbortError") {
      throw new Error(`Request timed out after ${timeoutMs}ms`);
    }
    throw error;
  }
}

async function apiLinkReport(sourceUrl) {
  // Find-or-create the report for this URL and link the current user.
  // The backend dedups by (org, source_url): the same report page opened by
  // several users maps to ONE shared report with every user linked.
  const result = await apiRequest(
    "/reports/link",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source_url: sourceUrl || "",
        source_domain: "openquire",
      }),
    },
    10000,
  );
  if (result.report_id) {
    extensionState.currentReportId = result.report_id;
    await chrome.storage.local.set({
      [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: result.report_id,
    });
    await acquireReportLock(result.report_id);
    // The link response is the source of truth â€” refresh the URL->report
    // cache so a user linked to an existing report sees it immediately.
    await loadUserReports();
  }
  return result;
}

async function apiStoreFormSchema(
  reportId,
  formSchema,
  scannedPayload,
  triggerIntent,
) {
  if (!(await ensureReportLock(reportId))) {
    throw new Error(
      `LOCK_CONFLICT: Report is locked by ${
        extensionState.lockHolderUser || "another user"
      }`,
    );
  }
  // The backend requires source_url (website URL of the report). If the
  // report doesn't exist yet it is auto-created with this URL.
  let sourceUrl = "";
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    sourceUrl = tab?.url || "";
  } catch (e) {
    console.warn("[BACKGROUND] Could not resolve active tab URL:", e.message);
  }
  const result = await apiRequest(
    `/reports/${reportId}/form_schema`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        form_schema: formSchema,
        scanned_payload: scannedPayload || undefined,
        trigger_intent: triggerIntent !== false,
        source_url: sourceUrl,
      }),
    },
    15000,
  );
  await loadUserReports();
  return result;
}

// Fetch the list of registered domains from the backend.
async function apiGetDomains() {
  return apiRequest(`/domains/`, { method: "GET" }, 10000);
}

async function apiGetFormSchema(reportId) {
  const result = await apiRequest(
    `/reports/${reportId}/form_schema`,
    {
      method: "GET",
    },
    10000,
  );

  if (result?.form_schema) {
    extensionState.formSchema = result.form_schema;
  }
  return result?.form_schema || null;
}

async function apiUpdateFormSchema(reportId, formSchema) {
  const result = await apiRequest(
    `/reports/${reportId}/form_schema`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ form_schema: formSchema }),
    },
    10000,
  );

  if (result?.form_schema) {
    extensionState.formSchema = result.form_schema;
  }
  await loadUserReports();
  return { success: true, data: result };
}

async function apiMapFormFields(reportId, domain) {
  console.log("[API] Mapping form fields for report:", reportId, "domain:", domain);
  if (!(await ensureReportLock(reportId))) {
    throw new Error(
      `LOCK_CONFLICT: Report is locked by ${
        extensionState.lockHolderUser || "another user"
      }`,
    );
  }
  // Mapping is synchronous server-side (no Celery job): pass the selected
  // domain NAME — the backend resolves it to its id. Long timeout because a
  // report may map hundreds of fields (retrieval + rules + LLM fallback).
  const body = { domain: domain || "pca_site_assessment" };
  const result = await apiRequest(
    `/reports/${reportId}/map`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
    120000,
  );
  return result;
}

async function apiGetMappingResults(reportId) {
  return apiRequest(`/reports/${reportId}/mapping`, { method: "GET" });
}

async function apiGetJobStatus(jobId) {
  return apiRequest(`/reports/jobs/${jobId}`, { method: "GET" });
}

async function apiLogin(email, password) {
  const params = new URLSearchParams();
  params.append("username", email);
  params.append("password", password);
  const result = await apiRequest("/auth/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: params.toString(),
  });
  if (result.access_token) {
    extensionState.accessToken = result.access_token;
    await chrome.storage.local.set({
      [EXTENSION.STORAGE_KEYS.ACCESS_TOKEN]: result.access_token,
    });
    await loadUserReports();
  }
  return result;
}

async function apiSignup(email, password, name) {
  return apiRequest("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, name: name || "" }),
  });
}

async function apiUploadPdf(reportId, fileItems) {
  console.log("[API] Uploading PDFs for report:", reportId);
  if (!(await ensureReportLock(reportId))) {
    throw new Error(
      `LOCK_CONFLICT: Report is locked by ${
        extensionState.lockHolderUser || "another user"
      }`,
    );
  }
  const formData = new FormData();

  fileItems.forEach((item) => {
    formData.append("files", item.file);
  });

  // Backend expects `doc_types` as a JSON array of STRINGS ("scanned"/"handwritten"),
  // one entry per file. Do NOT send objects â€” that triggers a 400.
  formData.append(
    "doc_types",
    JSON.stringify(
      fileItems.map((item) => {
        const dt =
          item.contains_handwritten || item.doc_type === "handwritten"
            ? "handwritten"
            : "scanned";
        return dt;
      }),
    ),
  );

  return apiRequest(
    `/reports/${reportId}/upload/pdf`,
    { method: "POST", body: formData },
    120000,
  );
}

/**
 * Convert a base64-encoded string into a Blob with the given MIME type.
 */
function base64ToBlob(base64, mimeType) {
  try {
    const byteCharacters = atob(base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    return new Blob([byteArray], {
      type: mimeType || "application/octet-stream",
    });
  } catch (e) {
    console.error("[BACKGROUND] base64 decode failed:", e);
    return new Blob([], { type: mimeType || "application/octet-stream" });
  }
}

async function apiUploadImage(reportId, files) {
  console.log("[API] Uploading image(s) for report:", reportId);
  if (!(await ensureReportLock(reportId))) {
    throw new Error(
      `LOCK_CONFLICT: Report is locked by ${
        extensionState.lockHolderUser || "another user"
      }`,
    );
  }
  const formData = new FormData();

  // Support both single file and multiple files (incl. ZIP bulk upload).
  const fileList = Array.isArray(files) ? files : [files];
  fileList.forEach((file) => {
    formData.append("files", file);
  });

  return apiRequest(
    `/reports/${reportId}/upload/image`,
    { method: "POST", body: formData },
    120000,
  );
}

const injectedTabs = new Set();

const CONTENT_SCRIPT_FILES = [
  "shared/constants.js",
  "shared/schemas.js",
  "content/dom/helpers.js",
  "content/utils/throttling.js",
  "content/utils/uiHelpers.js",
  "content/scanner/labelResolver.js",
  "content/scanner/sectionScanner.js",
  "content/scanner/fieldScanner.js",
  "content/scanner/multiStepScanner.js",
  "content/scanner/tableScanner.js",
  "content/scanner/dropdownScanner.js",
  "content/extractors/registry.js",
  "content/extractors/apiExtractor.js",
  "content/extractors/adapterLoader.js",
  "content/scanner/unifiedScanner.js",
  "content/observer/mutationObserver.js",
  "content/filler/textFiller.js",
  "content/filler/dropdownFiller.js",
  "content/filler/checkboxFiller.js",
  "content/filler/radioFiller.js",
  "content/filler/multiselectFiller.js",
  "content/content.js",
];

const RESTRICTED_URL_PATTERN =
  /^(chrome|edge|about|chrome-extension|https:\/\/chromewebstore\.google)/i;

async function isRestrictedUrl(url) {
  return !url || RESTRICTED_URL_PATTERN.test(url);
}

async function ensureContentScript(tabId, url) {
  if (await isRestrictedUrl(url)) {
    return false;
  }
  if (injectedTabs.has(tabId)) {
    return true;
  }
  try {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: CONTENT_SCRIPT_FILES,
    });
    injectedTabs.add(tabId);
    console.log("[BACKGROUND] Content script injected for tab", tabId);
    await new Promise((resolve) => setTimeout(resolve, 100));
    return true;
  } catch (error) {
    console.error("[BACKGROUND] Failed to inject content script:", error);
    return false;
  }
}

async function sendToContent(action, payload = {}) {
  const [tab] = await chrome.tabs.query({
    active: true,
    currentWindow: true,
  });

  if (!tab || !tab.id) {
    throw new Error("No active tab found");
  }

  // Content scripts are never injected on chrome:// (and similar restricted)
  // pages, so messaging there would always fail with
  // "Receiving end does not exist". Bail out early instead.
  if (!tab.url || /^(chrome|edge|about|chrome-extension):/i.test(tab.url)) {
    console.warn(
      "[BACKGROUND] Skipping content-script message on restricted URL:",
      tab.url,
    );
    return { success: false, error: "No content script on this page" };
  }

  await ensureContentScript(tab.id, tab.url);

  return chrome.tabs.sendMessage(tab.id, { action, ...payload });
}

async function generateMappings(reportId, domain) {
  console.log(
    "[SOURCE DATA] Extracted from document:",
    JSON.stringify(extensionState.sourceData, null, 2),
  );

  // Synchronous mapping: the backend returns the full mapping result
  // { report_id, mappings: [...], populated_schema, evidence_count } directly.
  // No Celery job is involved — the mappings array is ready to consume.
  const mappingResults = await apiMapFormFields(reportId, domain);

  extensionState.mappings = mappingResults.mappings || {};
  extensionState.mappingApproved = false;
  await chrome.storage.local.set({
    [EXTENSION.STORAGE_KEYS.MAPPINGS]: mappingResults.mappings || {},
    mappingApproved: false,
  });
  return mappingResults;
}

async function storeFormSchema(
  reportId,
  formSchema,
  scannedPayload,
  triggerIntent,
) {
  const result = await apiStoreFormSchema(
    reportId,
    formSchema,
    scannedPayload,
    triggerIntent,
  );
  if (result.report_id) {
    await apiGetFormSchema(result.report_id);
  }
  return result;
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  const handler = {
    async scanForm() {
      try {
        const result = await sendToContent("scanForm");
        if (result.success && result.data) {
          extensionState.formSchema = result.data;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.FORM_SCHEMA]: result.data,
          });

          const scannedPayload = result.data;
          const formSchema = {
            sections: scannedPayload.sections || [],
            tables: scannedPayload.tables || [],
            multi_step: scannedPayload.multiStep || null,
            stats: scannedPayload.stats || {},
          };

          let reportId = extensionState.currentReportId;
          if (!reportId) {
            let sourceUrl = "";
            try {
              const [tab] = await chrome.tabs.query({
                active: true,
                currentWindow: true,
              });
              sourceUrl = tab?.url || "";
            } catch (e) {
              // leave empty
            }
            // Check cached user reports for a URL match first.
            const cached = sourceUrl
              ? extensionState.reportByUrl.get(sourceUrl)
              : null;
            if (cached) {
              reportId = cached.report_id;
            } else {
              // No report for this URL â†’ create one before schema upload.
              const created = await apiLinkReport(sourceUrl);
              reportId = created.report_id;
            }
            extensionState.currentReportId = reportId;
            await chrome.storage.local.set({
              [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: reportId,
            });
            await loadUserReports();
          }

          try {
            await apiStoreFormSchema(
              reportId,
              formSchema,
              scannedPayload,
              true,
            );
            console.log("[BACKGROUND] Form schema stored to backend");
          } catch (storeError) {
            console.warn(
              "[BACKGROUND] Could not store form schema to backend:",
              storeError.message,
            );
          }
        }
        return {
          success: result?.success,
          data: result?.data,
          reportId: extensionState.currentReportId,
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async uploadData(message) {
      extensionState.sourceData = message.data;
      await chrome.storage.local.set({
        [EXTENSION.STORAGE_KEYS.SOURCE_DATA]: message.data,
      });
      return { success: true };
    },

    async uploadFile(message) {
      try {
        const {
          file,
          fileName,
          fileType,
          docType,
          files,
          fileItems,
          reportId: messageReportId,
        } = message;
        console.log("uploadFile received:", {
          fileName,
          fileType,
          docType,
          hasFile: !!file,
          hasFiles: !!files,
          hasFileItems: !!fileItems,
          filesCount: files ? files.length : 0,
          fileItemsCount: fileItems ? fileItems.length : 0,
        });

        const reportId = messageReportId || extensionState.currentReportId;
        if (reportId) {
          extensionState.currentReportId = reportId;
        }

        // Support new schema: [{doc_type, file}, ...]
        if (fileItems && fileItems.length > 0) {
          const fileObjects = await Promise.all(
            fileItems.map(async (item, idx) => {
              const byteCharacters = atob(item.file);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: "application/pdf" });
              const fName = item.fileName || `file_${Date.now()}_${idx}.pdf`;
              return {
                doc_type: item.doc_type || "scanned",
                file: new File([blob], fName, { type: "application/pdf" }),
              };
            }),
          );

          const result = await apiUploadPdf(reportId, fileObjects);
          console.log(
            "[EXTRACTED DATA] From uploaded file(s):",
            JSON.stringify(result.data, null, 2),
          );

          extensionState.sourceData = result.data;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.SOURCE_DATA]: result.data,
          });
          return { success: true, data: result.data, reportId };
        }

        // Legacy: single file or multiple files with single docType
        const fileList = files || (file ? [file] : []);
        if (!fileList || fileList.length === 0) {
          throw new Error("No file provided");
        }

        const isPdf =
          fileType === "application/pdf" ||
          (fileName && fileName.toLowerCase().endsWith(".pdf"));

        // Convert base64 files to File objects
        const fileObjects = await Promise.all(
          fileList.map(async (fileData) => {
            const byteCharacters = atob(fileData);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
              byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: fileType });
            const fName = fileName || `file_${Date.now()}`;
            return new File([blob], fName, { type: fileType });
          }),
        );

        const result = isPdf
          ? await apiUploadPdf(
              reportId,
              fileObjects.map((f) => ({ doc_type: docType, file: f })),
            )
          : await apiUploadImage(reportId, fileObjects);

        console.log(
          "[EXTRACTED DATA] From uploaded file(s):",
          JSON.stringify(result.data, null, 2),
        );

        extensionState.sourceData = result.data;
        await chrome.storage.local.set({
          [EXTENSION.STORAGE_KEYS.SOURCE_DATA]: result.data,
        });
        return { success: true, data: result.data, reportId };
      } catch (error) {
        console.error("Upload error:", error);
        if (error.name === "AbortError") {
          return { success: false, error: "Upload timed out (120s)" };
        }
        return { success: false, error: error.message };
      }
    },

    async STORE_FORM_SCHEMA(message) {
      try {
        const { reportId, formSchema, scannedPayload, triggerIntent } = message;

        if (!formSchema) {
          throw new Error("No formSchema provided");
        }

        // Resolve report ID â€“ fall back to currentReportId or create a new one
        let rid = reportId || extensionState.currentReportId;
        if (!rid) {
          let sourceUrl = "";
          try {
            const [tab] = await chrome.tabs.query({
              active: true,
              currentWindow: true,
            });
            sourceUrl = tab?.url || "";
          } catch (e) {
            // leave empty
          }
          const created = await apiLinkReport(sourceUrl);
          rid = created.report_id;
          extensionState.currentReportId = rid;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: rid,
          });
        }

        const result = await apiStoreFormSchema(
          rid,
          formSchema,
          scannedPayload,
          triggerIntent,
        );
        return { success: true, data: result };
      } catch (error) {
        console.error("[BACKGROUND] Failed to store form schema:", error);
        return { success: false, error: error.message };
      }
    },

    async MAP_FORM_FIELDS(message) {
      try {
        const { reportId, formSchema } = message;
        const actualReportId = reportId || extensionState.currentReportId;

        if (!actualReportId) {
          throw new Error("No reportId provided or available in state");
        }
        if (!formSchema) {
          throw new Error("No formSchema provided");
        }

        const mappings = await generateMappings(actualReportId, message?.domain);
        return { success: true, data: mappings };
      } catch (error) {
        console.error("[BACKGROUND] Failed to map fields:", error);
        return { success: false, error: error.message };
      }
    },

    async UPLOAD_PDF(message) {
      try {
        const { reportId, file, files, docType, docTypes, fileItems } = message;
        const actualReportId = reportId || extensionState.currentReportId;

        if (!actualReportId) {
          throw new Error("No reportId provided or available in state");
        }

        // Support new schema: [{doc_type, file}, ...] where `file` may be a
        // base64 string. Convert each entry into a real File object before
        // uploading so FormData.append("files", file) sends binary data.
        if (fileItems && fileItems.length > 0) {
          const fileObjects = await Promise.all(
            fileItems.map(async (item, idx) => {
              const isBase64 = typeof item.file === "string";
              const blob = isBase64
                ? base64ToBlob(item.file, item.fileType || "application/pdf")
                : item.file;
              const fName = item.fileName || `file_${Date.now()}_${idx}.pdf`;
              return {
                doc_type: item.doc_type || "scanned",
                file:
                  blob instanceof Blob
                    ? new File([blob], fName, { type: "application/pdf" })
                    : blob,
              };
            }),
          );

          const result = await apiUploadPdf(actualReportId, fileObjects);
          console.log(
            "[EXTRACTED DATA] From uploaded file(s):",
            JSON.stringify(result.data, null, 2),
          );
          return {
            success: true,
            data: result.data,
            reportId: actualReportId,
          };
        }

        // Legacy: single file or multiple files with single docType
        const fileList = files || (file ? [file] : []);
        const typeList = docTypes || (docType ? [docType] : ["scanned"]);

        if (!fileList || fileList.length === 0) {
          throw new Error("No file provided");
        }

        // Detect whether `fileList` entries are base64 strings or File/Blob objects.
        const first = fileList[0];
        const isBase64 = typeof first === "string";
        const fileObjects = await Promise.all(
          fileList.map(async (fileData, idx) => {
            const blob = isBase64
              ? base64ToBlob(fileData, fileType || "application/pdf")
              : fileData;
            const fName = fileName || `file_${Date.now()}_${idx}`;
            return blob instanceof Blob
              ? new File([blob], fName, { type: fileType || "application/pdf" })
              : blob;
          }),
        );

        const result = await apiUploadPdf(
          actualReportId,
          fileObjects.map((f, idx) => ({
            doc_type: typeList[idx] || "scanned",
            file: f,
          })),
        );
        return {
          success: true,
          data: result.data,
          reportId: actualReportId,
        };
      } catch (error) {
        console.error("[BACKGROUND] Failed to upload PDF:", error);
        return { success: false, error: error.message };
      }
    },

    async UPLOAD_IMAGE(message) {
      try {
        const { reportId, file, files, fileItems } = message;
        const actualReportId = reportId || extensionState.currentReportId;

        if (!actualReportId) {
          throw new Error("No reportId provided or available in state");
        }

        let fileList;
        if (fileItems && fileItems.length > 0) {
          // New schema: [{fileName, fileType, file}, ...] where `file` is a
          // base64 string. Convert each into a real File/Blob.
          fileList = await Promise.all(
            fileItems.map(async (item, idx) => {
              const isBase64 = typeof item.file === "string";
              const blob = isBase64
                ? base64ToBlob(
                    item.file,
                    item.fileType || "application/octet-stream",
                  )
                : item.file;
              const fName = item.fileName || `image_${Date.now()}_${idx}`;
              return blob instanceof Blob
                ? new File([blob], fName, { type: item.fileType || blob.type })
                : blob;
            }),
          );
        } else {
          fileList = files || (file ? [file] : []);
        }
        if (!fileList || fileList.length === 0) {
          throw new Error("No file provided");
        }

        const result = await apiUploadImage(actualReportId, fileList);
        return {
          success: true,
          data: result,
          reportId: actualReportId,
        };
      } catch (error) {
        console.error("[BACKGROUND] Failed to upload image:", error);
        return { success: false, error: error.message };
      }
    },

    async generateMapping() {
      try {
        if (!extensionState.formSchema) {
          throw new Error("Form schema not found. Please scan the form first.");
        }

        const reportId = extensionState.currentReportId;
        if (!reportId) {
          throw new Error(
            "No report ID found. Please upload a document first.",
          );
        }

        const result = await generateMappings(reportId, message?.domain);
        return {
          success: true,
          data: result,
          status: result.status || "completed",
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async processAndMap() {
      try {
        let reportId = extensionState.currentReportId;
        if (!reportId) {
          let sourceUrl = "";
          try {
            const [tab] = await chrome.tabs.query({
              active: true,
              currentWindow: true,
            });
            sourceUrl = tab?.url || "";
          } catch (e) {
            // leave empty
          }
          const created = await apiLinkReport(sourceUrl);
          reportId = created.report_id;
          extensionState.currentReportId = reportId;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: reportId,
          });
        }

        if (!extensionState.formSchema) {
          throw new Error("Form schema not found. Please scan the form first.");
        }

        const result = await generateMappings(reportId, message?.domain);
        extensionState.jobStatus = result.status || "completed";
        await chrome.storage.local.set({
          jobStatus: extensionState.jobStatus,
        });
        return {
          success: true,
          data: result,
          status: result.status || "completed",
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async storeFormSchema(message) {
      try {
        const {
          reportId,
          formSchema,
          scannedPayload,
          triggerIntent,
          sourceUrl,
        } = message;
        let rid = reportId || extensionState.currentReportId;
        if (!rid) {
          // Resolve the current page URL (UI may pass it explicitly).
          let url = sourceUrl || "";
          if (!url) {
            try {
              const [tab] = await chrome.tabs.query({
                active: true,
                currentWindow: true,
              });
              url = tab?.url || "";
            } catch (e) {
              // leave empty
            }
          }
          // Check cached user reports for a URL match first.
          const cached = url ? extensionState.reportByUrl.get(url) : null;
          if (cached) {
            rid = cached.report_id;
          } else {
            // No report for this URL â†’ create one before uploading schema.
            const created = await apiLinkReport(url);
            rid = created.report_id;
          }
          extensionState.currentReportId = rid;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: rid,
          });
        }
        const res = await apiStoreFormSchema(
          rid,
          formSchema,
          scannedPayload,
          triggerIntent !== false,
        );
        if (res.report_id) {
          extensionState.currentReportId = res.report_id;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: res.report_id,
          });
        }
        return { success: true, data: res };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async getFormSchema(message) {
      try {
        const reportId = message?.reportId || extensionState.currentReportId;
        const formSchema = extensionState.formSchema;
        if (!formSchema && reportId) {
          const fetched = await apiGetFormSchema(reportId);
          extensionState.formSchema = fetched;
        }
        return { success: true, data: extensionState.formSchema };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async deleteDocument(message) {
      try {
        const { id } = message;
        console.log("[BACKGROUND] deleteDocument:", id);
        return { success: true, data: { id } };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async getJobStatus(message) {
      try {
        const { jobId } = message;
        if (!jobId) {
          throw new Error("jobId is required");
        }
        const result = await apiGetJobStatus(jobId);
        const status = result.status;
        extensionState.jobStatus = status;
        await chrome.storage.local.set({ jobStatus: status });
        return { success: true, data: result };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async login(message) {
      try {
        const res = await apiLogin(message.email, message.password);
        if (res.access_token) {
          extensionState.isAuthenticated = true;
          extensionState.userEmail = message.email;
          await chrome.storage.local.set({
            [EXTENSION.STORAGE_KEYS.USER_EMAIL]: message.email,
          });
          // Clear any previous user's report state — storage is browser-wide,
          // so we must NOT inherit the prior user's currentReportId/schema/
          // mappings. This user's reports are loaded fresh below.
          await clearReportState();
          await loadUserReports();
          notifyUIStateChange();
          return { success: true, data: { email: message.email } };
        }
        return {
          success: false,
          error: res.detail || res.message || "Login failed",
        };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async logout() {
      extensionState.isAuthenticated = false;
      await releaseReportLock();
      extensionState.userEmail = null;
      extensionState.accessToken = null;
      extensionState.userReports = [];
      extensionState.activeReport = null;
      extensionState.currentReportId = null;
      extensionState.formSchema = null;
      extensionState.mappings = null;
      extensionState.sourceData = null;
      extensionState.mappingApproved = false;
      await chrome.storage.local.remove([
        EXTENSION.STORAGE_KEYS.ACCESS_TOKEN,
        EXTENSION.STORAGE_KEYS.USER_EMAIL,
        EXTENSION.STORAGE_KEYS.USER_REPORTS,
        EXTENSION.STORAGE_KEYS.SOURCE_DATA,
        EXTENSION.STORAGE_KEYS.FORM_SCHEMA,
        EXTENSION.STORAGE_KEYS.MAPPINGS,
        EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID,
      ]);
      notifyUIStateChange();
      return { success: true };
    },

    async signup(message) {
      try {
        // 1) Register the account.
        await apiSignup(message.email, message.password, message.name || "");

        // 2) Auto-login so the new user is immediately authenticated with a
        //    real access token stored in chrome.storage.local. Without this the
        //    UI shows "logged in" but the background has no token, so every
        //    auth-gated action (scanForm, upload, etc.) is rejected.
        const res = await apiLogin(message.email, message.password);
        if (!res.access_token) {
          return {
            success: false,
            error: res.detail || res.message || "Account created, but login failed",
          };
        }
        extensionState.isAuthenticated = true;
        extensionState.userEmail = message.email;
        await chrome.storage.local.set({
          [EXTENSION.STORAGE_KEYS.USER_EMAIL]: message.email,
        });
        // New account == fresh context; never inherit a previous user's state.
        await clearReportState();
        // Load the new user's (empty) report list so the UI hydrates correctly.
        await loadUserReports();
        notifyUIStateChange();
        return { success: true, data: { email: message.email } };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async createReport(message) {
      try {
        const res = await apiLinkReport(message.sourceUrl || "");
        return { success: true, data: res };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async submitForm(message) {
      try {
        const { formSchema, mappings, scannedPayload } = message;
        const reportId = extensionState.currentReportId;
        if (!reportId) {
          throw new Error("No report ID found. Please scan a form first.");
        }
        await apiStoreFormSchema(reportId, formSchema, scannedPayload, false);

        // Build a content-script-compatible mapping array from the backend
        // dict (keyed by field_id) and trigger live form fill on the page.
        let fillResult = { success: true };
        const activeMappings = mappings || extensionState.mappings;
        if (
          extensionState.mappingApproved &&
          activeMappings &&
          Object.keys(activeMappings).length > 0
        ) {
          const fieldMappings = [];
          const schema = formSchema || extensionState.formSchema;
          schema.sections.forEach((section) => {
            section.fields.forEach((field) => {
              const mapping = activeMappings[field.field_id];
              if (mapping && mapping.source_key) {
                const value =
                  mapping.value !== undefined
                    ? mapping.value
                    : extensionState.sourceData[mapping.source_key];
                if (value !== undefined) {
                  fieldMappings.push({
                    field_id: field.field_id,
                    formField: field.field_name,
                    sourceKey: mapping.source_key,
                    value: value,
                    selector: field.selector,
                    field_type: field.field_type,
                  });
                }
              }
            });
          });
          try {
            fillResult = await sendToContent("autoFill", {
              mappings: fieldMappings,
            });
          } catch (fillError) {
            console.warn(
              "[BACKGROUND] autoFill content fill skipped:",
              fillError.message,
            );
          }
        }
        return { success: true, data: fillResult };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async getMappingResults(message) {
      try {
        const { reportId } = message;
        const actualReportId = reportId || extensionState.currentReportId;

        if (!actualReportId) {
          throw new Error("No reportId provided or available in state");
        }

        const result = await apiGetMappingResults(actualReportId);
        return { success: true, data: result };
      } catch (error) {
        console.error("[BACKGROUND] Failed to get mapping results:", error);
        return { success: false, error: error.message };
      }
    },

    async getDomains() {
      try {
        const domains = await apiGetDomains();
        return { success: true, data: domains };
      } catch (error) {
        console.error("[BACKGROUND] Failed to load domains:", error);
        return { success: false, error: error.message };
      }
    },

    async approveMapping(message) {
      if (message && message.mappings) {
        extensionState.mappings = message.mappings;
      }
      extensionState.mappingApproved = true;
      await chrome.storage.local.set({
        mappingApproved: true,
      });
      return { success: true };
    },

    async autoFill() {
      try {
        console.log("[AUTO FILL] Starting autoFill...");

        if (!extensionState.formSchema) {
          throw new Error("Form schema not found. Please scan the form first.");
        }

        const [tab] = await chrome.tabs.query({
          active: true,
          currentWindow: true,
        });
        if (!tab.id) {
          throw new Error("No active tab found");
        }

        const injected = await ensureContentScript(tab.id, tab.url);
        if (!injected) {
          throw new Error(
            "Cannot inject content script on this page (restricted URL).",
          );
        }

        const fieldMappings = [];
        const schema = extensionState.formSchema;

        if (
          extensionState.mappings &&
          extensionState.mappingApproved &&
          Object.keys(extensionState.mappings).length > 0
        ) {
          schema.sections.forEach((section) => {
            section.fields.forEach((field) => {
              const mapping = extensionState.mappings[field.field_id];
              if (mapping && mapping.source_key) {
                const value =
                  mapping.value !== undefined
                    ? mapping.value
                    : extensionState.sourceData[mapping.source_key];
                if (value !== undefined) {
                  fieldMappings.push({
                    field_id: field.field_id,
                    formField: field.field_name,
                    sourceKey: mapping.source_key,
                    value: value,
                    selector: field.selector,
                    field_type: field.field_type,
                  });
                }
              }
            });
          });
        }

        console.log(
          "[AUTO FILL] Field mappings to apply:",
          JSON.stringify(fieldMappings, null, 2),
        );

        const result = await sendToContent("autoFill", {
          mappings: fieldMappings,
        });
        return result;
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Full report detail (status, documents, source_url) — used by the UI
    // pipeline strip to poll report-level processing state.
    // Switch the extension's active report (workspace -> report view).
    // Sets currentReportId so document sync/uploads target the right report.
    async setActiveReport(message) {
      try {
        const { reportId, status } = message;
        if (!reportId) {
          return { success: false, error: "reportId is required" };
        }
        extensionState.currentReportId = reportId;
        extensionState.activeReport = {
          ...(extensionState.activeReport || {}),
          report_id: reportId,
          status: status || extensionState.activeReport?.status || "draft",
        };
        await chrome.storage.local.set({
          [EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID]: reportId,
        });
        notifyUIStateChange();
        return { success: true };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Fetch a report document file with auth and return an object URL the
    // panel can use in <iframe>/<img> previews (iframes cannot send headers).
    async getSourceFileUrl(message) {
      try {
        const { reportId, fileId } = message;
        if (!reportId || !fileId) {
          return { success: false, error: "reportId and fileId are required" };
        }
        const token = await getAccessToken();
        if (!token) {
          return { success: false, error: "Please sign in to continue" };
        }
        const apiBase = await getApiBase();
        const resp = await fetch(
          `${apiBase}/reports/${encodeURIComponent(reportId)}/documents/${encodeURIComponent(fileId)}/file`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!resp.ok) {
          const text = await resp.text().catch(() => "");
          return { success: false, error: `HTTP ${resp.status} ${text.slice(0, 120)}` };
        }
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        return { success: true, data: { url, mime: blob.type } };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    // Show a transient toast on the active page (fill summary).
    async showToast(message) {
      try {
        const result = await sendToContent("showToast", {
          message: message?.message || "Done",
        });
        return result;
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async getReport(message) {
      try {
        const reportId = message?.reportId || extensionState.currentReportId;
        if (!reportId) {
          return { success: false, error: "No report selected" };
        }
        const report = await apiRequest(
          `/reports/${encodeURIComponent(reportId)}`,
          { method: "GET" },
          15000,
        );
        return { success: true, data: report };
      } catch (error) {
        return { success: false, error: error.message };
      }
    },

    async getDocuments() {
      // Server-authored document list: GET /reports/{id} is the source of
      // truth for document ids/names — the UI never invents local ids.
      try {
        const reportId = extensionState.currentReportId;
        if (!reportId) {
          return { success: true, data: [] };
        }
        const report = await apiRequest(
          `/reports/${encodeURIComponent(reportId)}`,
          { method: "GET" },
          15000,
        );
        const docs = (report.documents || []).map((d) => ({
          id: d.document_id,
          name: d.name,
          docType:
            (d.type || "").includes("pdf")
              ? "scanned"
              : (d.name || "").toLowerCase().endsWith(".zip")
                ? "zip"
                : "image",
          size: d.size,
          uploadedAt: d.uploaded_at,
        }));
        await chrome.storage.local.set({ documents: docs });
        return { success: true, data: docs };
      } catch (error) {
        console.error("[BACKGROUND] Failed to load documents:", error);
        return { success: false, error: error.message, data: [] };
      }
    },

    async deleteDocument(message) {
      // Delete on the backend (requires the report lock for mutations), then
      // re-sync the authoritative server list.
      try {
        const { id } = message;
        const reportId = extensionState.currentReportId;
        if (!reportId) {
          throw new Error("No active report — cannot delete document");
        }
        if (!(await ensureReportLock(reportId))) {
          throw new Error("LOCK_CONFLICT: could not acquire the report lock");
        }
        await apiRequest(
          `/reports/${encodeURIComponent(reportId)}/documents/${encodeURIComponent(id)}`,
          { method: "DELETE" },
          15000,
        );
        return await handler.getDocuments();
      } catch (error) {
        console.error("[BACKGROUND] Failed to delete document:", error);
        return { success: false, error: error.message };
      }
    },

    async getToken() {
      const token = await getAccessToken();
      return {
        success: true,
        data: {
          authenticated: !!token,
          email: extensionState.userEmail || "",
        },
      };
    },

    async getState() {
      // Phase 6 â€” never leak internal lock bookkeeping (tokens,
      // timers) to the side-panel; expose only the derived view.
      const { currentLockToken, currentLockId, lockHeartbeatTimer, ...safe } =
        extensionState;
      return {
        success: true,
        data: {
          ...safe,
          isReadOnly: extensionState.isReadOnly,
          lockHolderUser: extensionState.lockHolderUser,
          hasLock: !!extensionState.currentLockToken,
          lockExpiresAt: extensionState.lockExpiresAt || null,
          pageContext: await resolvePageContext(),
        },
      };
    },

    async getFormSchema() {
      try {
        if (!extensionState.formSchema) {
          throw new Error("Form schema not found. Please scan the form first.");
        }
        return { success: true, data: extensionState.formSchema };
      } catch (error) {
        console.error("[BACKGROUND] Failed to get form schema:", error);
        return { success: false, error: error.message };
      }
    },

    async getUserReports() {
      try {
        const result = await loadUserReports();
        return { success: true, data: result.data || [] };
      } catch (error) {
        console.error("[BACKGROUND] Failed to get user reports:", error);
        return { success: false, error: error.message, data: [] };
      }
    },
  };

  const actionHandler = handler[message.action];
  if (actionHandler) {
    // Report-scoped actions require a signed-in user. Without a token every
    // one of these would 401 server-side; fail fast so the UI shows login.
    const AUTH_ACTIONS = new Set([
      "scanForm",
      "uploadFile",
      "STORE_FORM_SCHEMA",
      "MAP_FORM_FIELDS",
      "UPLOAD_PDF",
      "UPLOAD_IMAGE",
      "generateMapping",
      "processAndMap",
      "storeFormSchema",
      "getFormSchema",
      "deleteDocument",
      "getJobStatus",
      "createReport",
      "submitForm",
      "getMappingResults",
      "approveMapping",
      "autoFill",
      "getUserReports",
      "getDocuments",
    ]);
    if (AUTH_ACTIONS.has(message.action)) {
      getAccessToken().then((token) => {
        if (!token) {
          console.warn(
            "[BACKGROUND] blocked unauthenticated action:",
            message.action,
          );
          sendResponse({
            success: false,
            authRequired: true,
            error: "Please sign in to continue",
          });
          return;
        }
        actionHandler(message).then(sendResponse);
      });
      return true;
    }
    actionHandler(message).then(sendResponse);
    return true;
  }

  if (message.action === "scanProgress") {
    chrome.runtime.sendMessage({
      action: "updateScanProgress",
      progress: message.progress,
    });
    return true;
  }

  sendResponse({ success: false, error: `Unknown action: ${message.action}` });
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete") {
    if (changeInfo.url) {
      injectedTabs.delete(tabId);
    }
    const token = await getAccessToken();
    if (token) {
      await getActiveReport();
    } else {
      console.debug(
        "[BACKGROUND] Skipping getActiveReport â€“ not authenticated",
      );
    }
  }
});

chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) return;

  chrome.sidePanel.open({ tabId: tab.id });

  // Only prefetch user data when a session exists; otherwise the calls would
  // 401 and the panel would boot into an error state instead of the login UI.
  const token = await getAccessToken();
  if (token) {
    await loadUserReports();
    await getActiveReport();
  } else {
    extensionState.isAuthenticated = false;
    notifyUIStateChange();
  }

  await ensureContentScript(tab.id, tab.url);
});

chrome.tabs.onRemoved.addListener((tabId) => {
  injectedTabs.delete(tabId);
});

// Option C — on tab switch: if the newly-active tab is a known report page,
// follow it (switch active report + acquire its lock). Otherwise keep the
// current report pinned but refresh the page-context flag so the panel can
// show the "different page" banner instead of silently mismatching.
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (!tab?.url || /^(chrome|edge|about|chrome-extension):/i.test(tab.url)) {
      await notifyUIStateChange();
      return;
    }
    const token = await getAccessToken();
    const cached = extensionState.reportByUrl.get(tab.url);
    if (cached && token) {
      await getActiveReport();
    } else {
      await notifyUIStateChange();
    }
  } catch (e) {
    console.debug("[BACKGROUND] onActivated context failed:", e.message);
  }
});

// When the user opens or navigates to a page, check whether it is a report
// webpage (e.g. https://app.openquire.com/reports/1809720) and match it
// against the user reports already fetched after login. If a match is found,
// populate the extension state (active report, docs, scanned fields, etc.).
// If no match exists, ignore â€” a report will be created on form scan.
chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" && !changeInfo.url) return;
  if (!tab?.url) return;
  if (!/\/reports\/[a-zA-Z0-9_-]+/.test(tab.url)) return;

  const token = await getAccessToken();
  if (!token) return; // not logged in â†’ no endpoint calls

  // Refresh the cached list only if we don't have one yet (e.g. SW restarted)
  if (!extensionState.userReports || extensionState.userReports.length === 0) {
    await loadUserReports();
  }
  await getActiveReport();
});

// onPanelShown is Chrome â‰¥ 116 only; guard so older Chrome doesn't crash the SW.
if (chrome.sidePanel?.onPanelShown) {
  chrome.sidePanel.onPanelShown.addListener(async (details) => {
    try {
      const tab = await chrome.tabs.get(details.tabId);
      await ensureContentScript(tab.id, tab.url);
    } catch (e) {
      console.debug(
        "[BACKGROUND] sidePanel.onPanelShown â€” inject skipped:",
        e.message,
      );
    }
  });
}

chrome.storage.local.get(
  [
    EXTENSION.STORAGE_KEYS.SOURCE_DATA,
    EXTENSION.STORAGE_KEYS.FORM_SCHEMA,
    EXTENSION.STORAGE_KEYS.MAPPINGS,
    EXTENSION.STORAGE_KEYS.USER_REPORTS,
    EXTENSION.STORAGE_KEYS.CURRENT_REPORT_ID,
    EXTENSION.STORAGE_KEYS.ACCESS_TOKEN,
    "mappingApproved",
  ],
  (items) => {
    if (items.sourceData) extensionState.sourceData = items.sourceData;
    if (items.formSchema) extensionState.formSchema = items.formSchema;
    if (items.mappings) extensionState.mappings = items.mappings;
    if (items.mappingApproved) extensionState.mappingApproved = true;

    // Restore cached user reports and current report ID
    if (items.userReports) {
      extensionState.userReports = items.userReports;
      extensionState.reportByUrl = new Map();
      for (const report of extensionState.userReports) {
        if (report.report_url) {
          extensionState.reportByUrl.set(report.report_url, report);
        }
      }
    }
    if (items.currentReportId) {
      extensionState.currentReportId = items.currentReportId;
    }
    if (items.accessToken) {
      extensionState.accessToken = items.accessToken;
    }
  },
);

// On startup/install: restore cached data only. Do NOT eagerly hit the API —
// a stale token + offline API would surface "Failed to fetch" before the user
// does anything. Fresh data loads when the panel opens (action.onClicked /
// onPanelShown) or when navigating to a known report page.
chrome.runtime.onStartup.addListener(async () => {
  await getActiveReport();
});

chrome.runtime.onInstalled.addListener(async () => {
  await getActiveReport();
});
