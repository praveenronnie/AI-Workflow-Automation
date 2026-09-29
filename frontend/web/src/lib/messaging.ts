/**
 * Chrome messaging wrapper for communicating with the extension background
 * script. The UI is extension-only: all backend API calls are made by the
 * background service worker (which owns the JWT and lock lifecycle).
 */
import { useStore } from "@/store/useStore";

export interface MessageResponse {
  success: boolean;
  data?: unknown;
  error?: string;
}

// Default timeouts in milliseconds
const TIMEOUTS = {
  scanForm: 60000, // 60s for form scanning
  generateMapping: 120000, // 120s for sync mapping (matches background API timeout)
  autoFill: 15000, // 15s for filling
  uploadFile: 120000, // 120s for file upload
  default: 30000, // 30s default
} as const;

type ActionName = keyof typeof TIMEOUTS;

/**
 * Send a message to the background script via Chrome runtime messaging.
 */
async function sendMessage(
  action: string,
  payload: Record<string, unknown> = {},
  timeoutMs?: number,
): Promise<MessageResponse> {
  if (typeof chrome === "undefined" || !chrome.runtime?.id) {
    return {
      success: false,
      error:
        "This panel must run inside the OpenQuire AI extension. " +
        "Load it via chrome://extensions (Developer mode → Load unpacked).",
    };
  }

  // Inject the currently selected domain into the payload so that
  // the background script / backend can route the request to the
  // correct domain-specific handler.
  const currentDomain = useStore.getState().domain;
  if (currentDomain) {
    payload.domain = currentDomain;
  }

  const timeout =
    timeoutMs ?? TIMEOUTS[action as ActionName] ?? TIMEOUTS.default;

  return new Promise((resolve) => {
    let resolved = false;
    const timeoutId = setTimeout(() => {
      if (!resolved) {
        resolved = true;
        resolve({
          success: false,
          error: `Operation timed out after ${timeout}ms`,
        });
      }
    }, timeout);

    chrome.runtime.sendMessage({ action, ...payload }, (response) => {
      if (!resolved) {
        resolved = true;
        clearTimeout(timeoutId);
        if (chrome.runtime.lastError) {
          resolve({ success: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve(response as MessageResponse);
      }
    });
  });
}

/**
 * Check if file is an image based on extension.
 */
function isImageFile(filename: string): boolean {
  const lowerName = filename.toLowerCase();
  return (
    lowerName.endsWith(".png") ||
    lowerName.endsWith(".jpg") ||
    lowerName.endsWith(".jpeg") ||
    lowerName.endsWith(".bmp") ||
    lowerName.endsWith(".gif")
  );
}

/**
 * Check if file is a PDF.
 */
function isPdfFile(filename: string): boolean {
  return filename.toLowerCase().endsWith(".pdf");
}

/**
 * Check if a filename is a ZIP archive.
 */
function isZipFile(filename: string): boolean {
  return filename.toLowerCase().endsWith(".zip");
}

export async function scanForm(
  domainConfig: {
    fieldAliases?: Record<string, string[]>;
    sectionTemplates?: Record<string, any>;
  } = {},
): Promise<MessageResponse> {
  return sendMessage(
    "scanForm",
    {
      fieldAliases: domainConfig.fieldAliases ?? {},
      sectionTemplates: domainConfig.sectionTemplates ?? {},
    },
    TIMEOUTS.scanForm,
  );
}

export async function generateMapping(): Promise<MessageResponse> {
  return sendMessage("generateMapping", {}, TIMEOUTS.generateMapping);
}

export async function approveMapping(
  mappings: Record<string, unknown>,
): Promise<MessageResponse> {
  return sendMessage("approveMapping", { mappings }, TIMEOUTS.default);
}

export async function autoFill(): Promise<MessageResponse> {
  return sendMessage("autoFill", {}, TIMEOUTS.autoFill);
}

/**
 * Get the current extension state from the background service worker.
 * This includes authentication state, user email, current report ID, etc.
 */
export async function getState(): Promise<any> {
  return sendMessage("getState", {}, TIMEOUTS.default);
}

/**
 * Update UI state based on background state changes.
 * In the current architecture, this is handled by a listener in App.tsx
 * that calls the zustand setters directly, but we keep this function
 * for symmetry and potential future use.
 */
export function updateUIState(_state: any): void {
  // The actual state update happens in App.tsx via the UPDATE_UI_STATE listener
  // This function is a no-op but kept for API consistency.
  console.debug(
    "[Messaging] updateUIState called - listener in App handles actual update",
  );
}

export async function getExtensionState(): Promise<MessageResponse> {
  return sendMessage("getState", {}, TIMEOUTS.default);
}

export async function getFormSchema(): Promise<MessageResponse> {
  return sendMessage("getFormSchema", {}, TIMEOUTS.default);
}

export async function uploadFile(
  file: string,
  fileName: string,
  fileType: string,
  docType: string,
): Promise<MessageResponse> {
  return sendMessage(
    "uploadFile",
    { file, fileName, fileType, docType },
    TIMEOUTS.uploadFile,
  );
}

/**
 * Upload multiple files.
 *
 * Flow:
 *  1. Collect ALL selected files into a single batch.
 *  2. Separate them by type  ->  PDFs  ->  POST /reports/{id}/upload/pdf
 *                              images/zip -> POST /reports/{id}/upload/image
 *  3. Call each endpoint independently with its own file group.
 *
 * `docType` ("scanned" | "handwritten") only applies to PDF uploads; images and
 * ZIPs are always routed to the image endpoint.
 */
export async function uploadMultipleFiles(
  base64Files: Array<{ base64: string; name: string; type: string; docType?: string }>,
  docType: string = "scanned",
): Promise<MessageResponse> {
  // 1. Collect & separate files by type (single collection -> multiple groups)
  const pdfFiles: Array<{ base64: string; name: string; type: string; docType?: string }> = [];
  const imageFiles: Array<{ base64: string; name: string; type: string; docType?: string }> = [];
  for (const f of base64Files) {
    if (isPdfFile(f.name)) {
      pdfFiles.push(f);
    } else if (isImageFile(f.name) || isZipFile(f.name)) {
      imageFiles.push(f);
    } else {
      console.warn("[Messaging] Skipping unsupported file type:", f.name);
    }
  }

  const reportId = useStore.getState().reportId;
  if (!reportId) {
    return {
      success: false,
      error: "No report ID available. Please scan a form first.",
    };
  }

  const results: MessageResponse[] = [];

  // 2a. PDFs -> POST /reports/{id}/upload/pdf  (doc_types = scanned/handwritten)
  if (pdfFiles.length > 0) {
    const fileItems = pdfFiles.map((f) => ({
      fileName: f.name,
      fileType: f.type,
      file: f.base64,
      doc_type: (f.docType || docType) === "handwritten" ? "handwritten" : "scanned",
    }));
    const res = await sendMessage(
      "UPLOAD_PDF",
      { fileItems, reportId },
      TIMEOUTS.uploadFile,
    );
    results.push(res);
    if (!res.success) return res;
  }

  // 2b. Images / ZIP -> POST /reports/{id}/upload/image
  if (imageFiles.length > 0) {
    const fileItems = imageFiles.map((f) => ({
      fileName: f.name,
      fileType: f.type,
      file: f.base64,
    }));
    const res = await sendMessage(
      "UPLOAD_IMAGE",
      { fileItems, reportId },
      TIMEOUTS.uploadFile,
    );
    results.push(res);
    if (!res.success) return res;
  }

  return {
    success: true,
    data: {
      pdfFiles: pdfFiles.length,
      imageFiles: imageFiles.length,
      results,
    },
  };
}

export async function deleteDocument(id: string): Promise<MessageResponse> {
  return sendMessage("deleteDocument", { id }, TIMEOUTS.default);
}

export async function getMappingResults(
  reportId: string,
): Promise<MessageResponse> {
  return sendMessage("getMappingResults", { reportId }, TIMEOUTS.default);
}

export async function login(
  email: string,
  password: string,
): Promise<MessageResponse> {
  return sendMessage("login", { email, password }, TIMEOUTS.default);
}

export async function signup(
  email: string,
  password: string,
  name?: string,
): Promise<MessageResponse> {
  return sendMessage("signup", { email, password, name }, TIMEOUTS.default);
}

export async function logout(): Promise<MessageResponse> {
  return sendMessage("logout", {}, TIMEOUTS.default);
}

export async function createReport(
  sourceUrl: string,
): Promise<MessageResponse> {
  return sendMessage("createReport", { sourceUrl }, TIMEOUTS.default);
}

/**
 * Switch the extension's active report (workspace -> report view). Must be
 * called before document sync/uploads so the background targets the right
 * report.
 */
export async function setActiveReport(
  reportId: string,
  status?: string,
): Promise<MessageResponse> {
  return sendMessage("setActiveReport", { reportId, status }, TIMEOUTS.default);
}

/**
 * Fetch a report document file (auth via background) and return an object
 * URL + mime for in-panel preview (popover iframe/img).
 */
export async function getSourceFileUrl(
  reportId: string,
  fileId: string,
): Promise<MessageResponse> {
  return sendMessage(
    "getSourceFileUrl",
    { reportId, fileId },
    TIMEOUTS.uploadFile,
  );
}

/**
 * Show a transient toast on the active page (used after fill completes).
 */
export async function showToast(message: string): Promise<MessageResponse> {
  return sendMessage("showToast", { message }, TIMEOUTS.default);
}

/**
 * Fetch full report detail (status, documents, source_url) — used by the
 * pipeline strip to poll report-level processing state.
 */
export async function getReport(reportId?: string): Promise<MessageResponse> {
  return sendMessage("getReport", { reportId }, TIMEOUTS.default);
}

export async function storeFormSchema(
  reportId: string,
  formSchema: unknown,
  scannedPayload?: unknown,
  triggerIntent: boolean = true,
  sourceUrl?: string,
): Promise<MessageResponse> {
  return sendMessage(
    "storeFormSchema",
    { reportId, formSchema, scannedPayload, triggerIntent, sourceUrl },
    TIMEOUTS.uploadFile,
  );
}

export async function processAndMap(): Promise<MessageResponse> {
  return sendMessage("processAndMap", {}, TIMEOUTS.uploadFile);
}

export async function getJobStatus(jobId: string): Promise<MessageResponse> {
  return sendMessage("getJobStatus", { jobId }, TIMEOUTS.default);
}

export async function submitForm(
  formSchema: unknown,
): Promise<MessageResponse> {
  return sendMessage("submitForm", { formSchema }, TIMEOUTS.default);
}

/**
 * Fetch the list of registered domains from the backend via the background
 * service worker. This is the domain-agnostic discovery call — the backend
 * returns every active domain, and the UI populates the selector from it
 * rather than hardcoding platform names.
 */
export async function getUserReports(): Promise<MessageResponse> {
  return sendMessage("getUserReports", {}, TIMEOUTS.default);
}

export async function getDomains(): Promise<MessageResponse> {
  return sendMessage("getDomains", {}, TIMEOUTS.default);
}

/**
 * Sync the document list from the backend (server-authored ids/names).
 * Use after any upload/delete so the UI reflects the server state.
 */
export async function syncDocuments(): Promise<MessageResponse> {
  return sendMessage("getDocuments", {}, TIMEOUTS.default);
}
