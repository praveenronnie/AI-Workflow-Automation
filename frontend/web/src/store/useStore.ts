import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { getDomains } from "@/lib/messaging";

export interface Document {
  id: string;
  name: string;
  docType: "scanned" | "handwritten" | "image" | "zip";
}

export interface FormField {
  field_id: string;
  field_name: string;
  field_type: string;
  selector?: string;
}

export interface FormFieldWithOptions extends FormField {
  options?: Record<string, string>;
  mappedValue?: string;
  confidence?: number;
  source?: string;
  reasoning?: string;
}

export interface FormSection {
  sectionName: string;
  tableId: number;
  fields: FormFieldWithOptions[];
}

export interface Mapping {
  source_key?: string;
  value?: string;
  confidence?: number;
  matched?: boolean;
  option_id?: string | null;
  source?: string;
  reasoning?: string;
  source_location?: string;
  mapping_method?: string;
}

export interface FormStats {
  fieldsDetected: number;
  fieldsMapped: number;
  missingFields: number;
}

export type DrawerType =
  | "documents"
  | "fields"
  | "fields-table"
  | "mapping"
  | null;

export interface AppState {
  // Domain management
  domain: string;
  domains: Array<{ id: string; name: string; description?: string }>;
  setDomain: (domain: string) => void;
  setDomains: (domains: Array<{ id: string; name: string; description?: string }>) => void;
  fetchDomains: () => Promise<void>;

  // Documents
  documents: Document[];
  setDocuments: (docs: Document[]) => void;
  addDocument: (doc: Document) => void;
  removeDocument: (id: string) => void;
  clearDocuments: () => void;

  // Form
  formFields: FormField[];
  setFormFields: (fields: FormField[]) => void;
  formStats: FormStats;
  setFormStats: (stats: FormStats) => void;

  // Mappings
  mappings: Record<string, Mapping>;
  setMappings: (mappings: Record<string, Mapping>) => void;
  updateMapping: (fieldId: string, mapping: Mapping) => void;

  // UI
  panelOpen: boolean;
  setPanelOpen: (open: boolean) => void;
  activeDrawer: DrawerType;
  setActiveDrawer: (drawer: DrawerType) => void;

  // Activity
  activityLog: string[];
  addActivity: (entry: string) => void;
  clearActivity: () => void;

  // Loading states
  isUploading: boolean;
  setIsUploading: (loading: boolean) => void;
  isScanning: boolean;
  setIsScanning: (loading: boolean) => void;
  isFilling: boolean;
  setIsFilling: (loading: boolean) => void;
  isMapping: boolean;
  setIsMapping: (loading: boolean) => void;

  // Upload progress & doc type
  uploadProgress: number;
  setUploadProgress: (progress: number) => void;
  uploadDocType: "scanned" | "handwritten";
  setUploadDocType: (docType: "scanned" | "handwritten") => void;

  // Auth
  isAuthenticated: boolean;
  setAuthenticated: (v: boolean) => void;
  userEmail: string;
  setUserEmail: (v: string) => void;

  // Report / jobs
  reportId: string | null;
  setReportId: (v: string | null) => void;
  mapJobId: string | null;
  setMapJobId: (v: string | null) => void;
  jobStatus: "idle" | "processing" | "completed" | "failed";
  setJobStatus: (v: "idle" | "processing" | "completed" | "failed") => void;
  mappingDone: boolean;
  setMappingDone: (v: boolean) => void;
  isProcessing: boolean;
  setIsProcessing: (v: boolean) => void;
  isSubmitting: boolean;
  setIsSubmitting: (v: boolean) => void;

  // Form schema (synced from background)
  formSchema: any;
  setFormSchema: (schema: any) => void;

  // User reports (synced from background)
  userReports: any[];
  setUserReports: (reports: any[]) => void;
}

export const useStore = create<AppState>()(
  persist(
    (set) => ({
      // Domain management
      domain: "pca_site_assessment",
      domains: [],
      setDomain: (domain) => set({ domain }),
      setDomains: (domains) => set({ domains }),
      fetchDomains: async () => {
        try {
          const response = await getDomains();
          if (response.success && Array.isArray(response.data)) {
            const list = response.data.map((d) => ({
              id: String(d.id),
              name: d.name,
              description: d.description,
            }));
            set({ domains: list });
            // If the currently selected domain isn't in the fetched list,
            // fall back to the first available domain (domain-agnostic default).
            const state = useStore.getState();
            if (list.length > 0 && !list.some((d) => d.name === state.domain)) {
              state.setDomain(list[0].name);
            }
          }
        } catch (error) {
          console.error("[STORE] fetchDomains failed:", error);
        }
      },

      // Documents
      documents: [],
      setDocuments: (docs) => set({ documents: docs }),
      addDocument: (doc) =>
        set((state) => ({ documents: [...state.documents, doc] })),
      removeDocument: (id) =>
        set((state) => ({
          documents: state.documents.filter((d) => d.id !== id),
        })),
      clearDocuments: () => set({ documents: [] }),

      // Form
      formFields: [],
      setFormFields: (fields) => set({ formFields: fields }),
      formStats: { fieldsDetected: 0, fieldsMapped: 0, missingFields: 0 },
      setFormStats: (stats) => set({ formStats: stats }),

      // Form schema (synced from background)
      formSchema: null,
      setFormSchema: (schema) => set({ formSchema: schema }),

      // User reports (synced from background)
      userReports: [],
      setUserReports: (reports) => set({ userReports: reports }),

      // Mappings
      mappings: {},
      setMappings: (mappings) => set({ mappings }),
      updateMapping: (fieldId, mapping) =>
        set((state) => ({
          mappings: { ...state.mappings, [fieldId]: mapping },
        })),

      // UI
      panelOpen: true,
      setPanelOpen: (open) => set({ panelOpen: open }),
      activeDrawer: null,
      setActiveDrawer: (drawer) => set({ activeDrawer: drawer }),

      // Activity - capped at 50 entries
      activityLog: ["Ready"],
      addActivity: (entry) =>
        set((state) => ({
          activityLog: [...state.activityLog, entry].slice(-50),
        })),
      clearActivity: () => set({ activityLog: ["Ready"] }),

      // Loading states
      isUploading: false,
      setIsUploading: (loading) => set({ isUploading: loading }),
      isScanning: false,
      setIsScanning: (loading) => set({ isScanning: loading }),
      isFilling: false,
      setIsFilling: (loading) => set({ isFilling: loading }),
      isMapping: false,
      setIsMapping: (loading) => set({ isMapping: loading }),

      // Upload progress & doc type
      uploadProgress: 0,
      setUploadProgress: (progress) => set({ uploadProgress: progress }),
      uploadDocType: "scanned",
      setUploadDocType: (docType) => set({ uploadDocType: docType }),

      // Auth
      isAuthenticated: false,
      setAuthenticated: (v) => set({ isAuthenticated: v }),
      userEmail: "",
      setUserEmail: (v) => set({ userEmail: v }),

      // Report / jobs
      reportId: null,
      setReportId: (v) => set({ reportId: v }),
      mapJobId: null,
      setMapJobId: (v) => set({ mapJobId: v }),
      jobStatus: "idle",
      setJobStatus: (v) => set({ jobStatus: v }),
      mappingDone: false,
      setMappingDone: (v) => set({ mappingDone: v }),
      isProcessing: false,
      setIsProcessing: (v) => set({ isProcessing: v }),
      isSubmitting: false,
      setIsSubmitting: (v) => set({ isSubmitting: v }),
    }),
    {
      name: "openquire-panel-state",
      storage: createJSONStorage(() => sessionStorage),
      partialize: (state) => ({
        documents: state.documents,
        formFields: state.formFields,
        formStats: state.formStats,
        mappings: state.mappings,
        activityLog: state.activityLog,
        panelOpen: state.panelOpen,
      }),
    },
  ),
);
