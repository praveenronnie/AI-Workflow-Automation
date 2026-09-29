import { useStore } from "@/store/useStore";
import { LoginSection } from "@/features/auth/components/LoginSection";
import { WorkspaceView } from "@/features/workspace/WorkspaceView";
import { ReportView } from "@/features/reports/components/ReportView";
import { getState } from "@/lib/messaging";
import { useEffect } from "react";

/**
 * Root panel: a two-view shell.
 *  - Not authenticated -> LoginSection (full panel)
 *  - Authenticated     -> WorkspaceView (report list + New Report)
 *                         or ReportView (pipeline, documents, review)
 */
function App() {
  const isAuthenticated = useStore((s) => s.isAuthenticated);
  const view = useStore((s) => s.view);

  // Sync UI state from background on mount and listen for updates.
  useEffect(() => {
    async function initializeAuthState() {
      try {
        const response = await getState();
        const state = response?.data ?? null;
        if (state) applyState(state);
      } catch (error) {
        console.warn("[APP] Failed to sync auth state:", error);
      }
    }

    function applyState(state: any) {
      const s = useStore.getState();
      s.setAuthenticated(!!state.isAuthenticated);
      s.setUserEmail(state.userEmail || "");
      s.setReportId(state.currentReportId || null);
      s.setFormSchema(buildFormSchema(state) ?? null);
      s.setUserReports(state.userReports ?? []);
      if (state.apiOffline !== undefined) {
        s.setApiOffline(!!state.apiOffline);
      }
      const derivedFields = deriveFields(state.formSchema);
      if (derivedFields.length > 0) s.setFormFields(derivedFields);
      if (state.mappings && Object.keys(state.mappings).length > 0) {
        s.setMappings(state.mappings);
      } else if (state.mappings !== undefined) {
        // Background explicitly reported no mappings (e.g. after logout or
        // report switch) — clear stale values from the persisted store.
        s.setMappings({});
      }
      if (state.reportStatus) s.setReportStatus(state.reportStatus);
      // Option C — page context (active tab vs report source page)
      s.setPageContext(state.pageContext ?? null);
      // Lock / read-only state (Phase 6 banners in the report view)
      if (
        state.isReadOnly !== undefined ||
        state.hasLock !== undefined
      ) {
        s.setLockState({
          isReadOnly: !!state.isReadOnly,
          hasLock: !!state.hasLock,
          lockHolderUser: state.lockHolderUser ?? null,
          lockExpiresAt: state.lockExpiresAt ?? null,
        });
      }
    }

    initializeAuthState();

    // Listen for state updates from background
    if (typeof chrome !== "undefined" && chrome.runtime?.id) {
      const listener = (message: any) => {
        if (message.action === "UPDATE_UI_STATE") {
          applyState(message.payload);
        } else if (message.action === "LOCK_STATE_CHANGED") {
          // Lock-only updates (e.g. stolen/expired mid-session)
          const s = useStore.getState();
          const p = message.payload ?? {};
          s.setLockState({
            isReadOnly: !!p.isReadOnly,
            hasLock: !!p.hasLock,
            lockHolderUser: p.lockHolderUser ?? null,
            lockExpiresAt: p.lockExpiresAt ?? null,
          });
        }
      };
      chrome.runtime.onMessage.addListener(listener);
      return () => chrome.runtime.onMessage.removeListener(listener);
    }
  }, []);

  if (!isAuthenticated) {
    return (
      <div className="flex h-screen flex-col bg-background text-foreground">
        <div className="flex items-center justify-between border-b px-3 py-2.5">
          <h1 className="text-base font-semibold">FormIQ</h1>
        </div>
        <div className="flex-1 overflow-y-auto p-3">
          <LoginSection />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      {view === "report" ? <ReportView /> : <WorkspaceView />}
    </div>
  );
}

/**
 * Normalize the background state into the formSchema shape the UI consumes.
 * The background stores the raw scanner payload; the UI expects
 * `{ sections: [{name,tableId}], tables: [{tableId,fields}] }`.
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
 * Derive a flat FormField list from the form schema so the review screen can
 * be restored after reopening the panel. Works for both
 * { sections:[{fields}] } and { tables:[{fields}] } shapes.
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
