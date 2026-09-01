import { useStore } from "@/store/useStore";
import { LoginSection } from "@/features/auth/components/LoginSection";
import { DocumentsSection } from "@/features/reports/components/DocumentsSection";
import { FormStatusSection } from "@/features/form-mapping/components/FormStatusSection";
import { ActionsSection } from "@/features/dashboard/components/ActionsSection";
import { ActivitySection } from "@/features/reports/components/ActivitySection";
import { ReportsSection } from "@/features/reports/components/ReportsSection";
import { Drawer } from "@/features/dashboard/components/Drawer";
import { DomainSelector } from "@/features/form-mapping/components/DomainSelector";
import { X } from "lucide-react";
import { useEffect } from "react";
import { getState } from "@/lib/messaging";

function App() {
  const {
    panelOpen,
    setPanelOpen,
    isAuthenticated,
    setAuthenticated,
    setUserEmail,
    setReportId,
    setFormSchema,
    setUserReports,
    setMappings,
    setFormFields,
  } = useStore();

  // Sync UI state from background on mount and listen for updates.
  useEffect(() => {
    async function initializeAuthState() {
      try {
        const state = await getState();
        if (state) {
          // Update local store with background state. Auth is derived from the
          // background (single source of truth) so the UI never optimistically
          // marks a user logged in before a real token exists.
          setAuthenticated(!!state.isAuthenticated);
          setUserEmail(state.userEmail || "");
          setReportId(state.currentReportId || null);
          setFormSchema(buildFormSchema(state) ?? null);
          setUserReports(state.userReports ?? []);
          if (state.mappings && Object.keys(state.mappings).length > 0) {
            setMappings(state.mappings);
          }
          const derivedFields = deriveFields(state.formSchema);
          if (derivedFields.length > 0) {
            setFormFields(derivedFields);
          }
        }
      } catch (error) {
        console.warn("[APP] Failed to sync auth state:", error);
      }
    }
    initializeAuthState();

    // Listen for state updates from background
    if (typeof chrome !== "undefined" && chrome.runtime?.id) {
      const listener = (message: any) => {
        if (message.action === "UPDATE_UI_STATE") {
          const p = message.payload;
          setAuthenticated(!!p.isAuthenticated);
          setUserEmail(p.userEmail || "");
          setReportId(p.currentReportId || null);
          setFormSchema(buildFormSchema(p) ?? null);
          setUserReports(p.userReports ?? []);
          if (p.mappings && Object.keys(p.mappings).length > 0) {
            setMappings(p.mappings);
          }
          const derivedFields = deriveFields(p.formSchema);
          if (derivedFields.length > 0) {
            setFormFields(derivedFields);
          }
        }
      };
      chrome.runtime.onMessage.addListener(listener);
      return () => chrome.runtime.onMessage.removeListener(listener);
    }
  }, [
    setAuthenticated,
    setUserEmail,
    setReportId,
    setFormSchema,
    setUserReports,
    setMappings,
    setFormFields,
  ]);

  // Render the panel - respects persisted panelOpen state
  if (!panelOpen) {
    return null;
  }

  return (
    <div className="fixed right-0 top-0 z-[9999] flex h-full w-full max-w-[460px] min-w-[320px] flex-col border-l bg-background shadow-lg">
      {/* Header */}
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
        <h1 className="text-base font-semibold truncate">
          OpenQuire Assistant
        </h1>
        {isAuthenticated && <DomainSelector />}
        <button
          onClick={() => setPanelOpen(false)}
          className="rounded-md p-1 hover:bg-muted"
          aria-label="Close panel"
        >
          <X className="size-5" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto space-y-5 p-3">
        <LoginSection />
        {isAuthenticated && (
          <>
            <DocumentsSection />
            <FormStatusSection />
            <ActionsSection />
            <ReportsSection />
            <ActivitySection />
          </>
        )}
      </div>

      {/* Drawer overlay */}
      <Drawer />
    </div>
  );
}

/**
 * Normalize the background state into the formSchema shape the UI consumes.
 * The background stores the raw scanner payload; the UI expects
 * `{ sections: [{name,tableId}], tables: [{tableId,fields}] }`.
 * `formSchema` may come as either `payload.formSchema` or be a structured
 * object already. We defensively pull `sections`/`tables` from whichever
 * field actually contains them.
 */
function buildFormSchema(state: any) {
  const raw = state?.formSchema;
  if (!raw) return null;
  if (raw.sections || raw.tables) return raw;
  if (state?.form_schema?.sections || state?.form_schema?.tables) {
    return state.form_schema;
  }
  return raw;
}

/**
 * Derive a flat list of FormFields from the formSchema so the "Detected
 * Fields" view / mapping flow can be restored after reopening the panel.
 * Works for both { sections:[{fields}] } and { tables:[{fields}] } shapes.
 */
function deriveFields(formSchema: any): any[] {
  if (!formSchema) return [];
  const out: any[] = [];
  const push = (f: any) => {
    if (!f) return;
    const name = f.field_name || f.fieldName || f.label;
    if (!name) return;
    out.push({
      field_id: f.field_id || f.fieldId || name,
      field_name: name,
      field_type: f.field_type || f.fieldType || "text",
      selector: f.selector,
    });
  };
  if (Array.isArray(formSchema.sections)) {
    formSchema.sections.forEach((s: any) => {
      if (Array.isArray(s.fields)) s.fields.forEach(push);
    });
  }
  if (Array.isArray(formSchema.tables)) {
    formSchema.tables.forEach((t: any) => {
      if (Array.isArray(t.fields)) t.fields.forEach(push);
    });
  }
  return out;
}

export default App;