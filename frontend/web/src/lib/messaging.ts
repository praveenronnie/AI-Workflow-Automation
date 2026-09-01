/**
 * Chrome messaging wrapper for communicating with the extension background script.
 * Also supports direct API calls for standalone mode.
 */
import { useStore } from "@/store/useStore";

export interface MessageResponse {
  success: boolean;
  data?: unknown;
  error?: string;
}

// API base URL for standalone mode — override via localStorage "apiBase".
const API_BASE =
  (typeof window !== "undefined" &&
    (window.localStorage?.getItem("apiBase") || "").trim().replace(/\/+$/, "")) ||
  "http://localhost:8000";

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
    console.warn(
      "[Messaging] chrome.runtime not available. Running in standalone mode.",
    );
    return { success: false, error: "Extension context not available" };
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
 * Direct API upload for standalone mode.
 * Sends FormData to the backend API directly.
 */
async function directApiUpload(
  files: File[],
  docTypes: string[],
  reportId: string,
  isImage: boolean = false,
): Promise<MessageResponse> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUTS.uploadFile);

  try {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });
    if (!isImage) {
      // PDF endpoint requires a JSON array of "scanned"/"handwritten" strings.
      formData.append(
        "doc_types",
        JSON.stringify(
          docTypes.map((dt) =>
            dt === "handwritten" ? "handwritten" : "scanned",
          ),
        ),
      );
    }

    const endpoint = isImage
      ? `/reports/${reportId}/upload/image`
      : `/reports/${reportId}/upload/pdf`;

    const headers: Record<string, string> = {};
    const token = localStorage.getItem("accessToken");
    if (token) headers.Authorization = `Bearer ${token}`;

    const response = await fetch(`${API_BASE}${endpoint}`, {
      method: "POST",
      headers,
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      return {
        success: false,
        error: `API error: ${response.status} - ${errorText}`,
      };
    }

    const result = await response.json();
    return { success: true, data: result };
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error) {
      if (error.name === "AbortError") {
        return {
          success: false,
          error: `Upload timed out after ${TIMEOUTS.uploadFile}ms`,
        };
      }
      return { success: false, error: error.message };
    }
    return { success: false, error: "Unknown error during upload" };
  }
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

  const isExtension = typeof chrome !== "undefined" && chrome.runtime?.id;

  // Extension context: route through the typed background handlers
  if (isExtension) {
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

  // Standalone mode: upload directly to the API with File objects.
  const reportId = useStore.getState().reportId || crypto.randomUUID();

  const makeFile = (f: { base64: string; name: string; type: string; docType?: string }) => {
    const byteCharacters = atob(f.base64);
    const byteNumbers = new Array(byteCharacters.length);
    for (let i = 0; i < byteCharacters.length; i++) {
      byteNumbers[i] = byteCharacters.charCodeAt(i);
    }
    const byteArray = new Uint8Array(byteNumbers);
    const blob = new Blob([byteArray], { type: f.type });
    return new File([blob], f.name, { type: f.type });
  };

  if (pdfFiles.length > 0) {
    const pdfResult = await directApiUpload(
      pdfFiles.map(makeFile),
      pdfFiles.map((f) => f.docType || docType),
      reportId,
      false,
    );
    if (!pdfResult.success) return pdfResult;
  }

  if (imageFiles.length > 0) {
    const imageResult = await directApiUpload(
      imageFiles.map(makeFile),
      imageFiles.map((f) => f.docType || docType),
      reportId,
      true,
    );
    if (!imageResult.success) return imageResult;
  }

  return {
    success: true,
    data: { pdfFiles: pdfFiles.length, imageFiles: imageFiles.length },
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
