import { useState } from "react";
import {
  Plus,
  RefreshCw,
  FileText,
  LogOut,
  ExternalLink,
  Loader2,
} from "lucide-react";
import { useStore } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import {
  createReport,
  getUserReports,
  syncDocuments,
  logout,
  setActiveReport,
} from "@/lib/messaging";
import type { Document } from "@/store/useStore";

/**
 * Workspace shell (Phase 1): the landing view after login. Shows the user's
 * reports as cards plus a prominent [New Report] action. Opening a card
 * switches the panel to the report detail view.
 */
export function WorkspaceView() {
  const {
    userEmail,
    userReports,
    setUserReports,
    setActiveReportId,
    setActiveReportTitle,
    setReportStatus,
    setReportId,
    setDocuments,
    setView,
    addActivity,
    setAuthenticated,
    setUserEmail,
    setMappings,
    setFormFields,
    setFormStats,
    setReportTab,
    apiOffline,
  } = useStore();
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const response = await getUserReports();
      if (response.success && Array.isArray(response.data)) {
        setUserReports(response.data);
      }
    } finally {
      setLoading(false);
    }
  };

  const openReport = async (
    reportId: string,
    title: string,
    status: string,
  ) => {
    // Point the background at this report FIRST so document sync and any
    // uploads land on the right report.
    await setActiveReport(reportId, status);
    // Reset per-report UI state: persisted mappings/fields from the previous
    // report must never render against this report's schema.
    setMappings({});
    setFormFields([]);
    setFormStats({ fieldsDetected: 0, fieldsMapped: 0, missingFields: 0 });
    setReportTab("docs");
    setActiveReportId(reportId);
    setActiveReportTitle(title);
    setReportStatus(status);
    setReportId(reportId);
    // Load this report's documents before switching views.
    const synced = await syncDocuments();
    if (synced.success && Array.isArray(synced.data)) {
      setDocuments(synced.data as Document[]);
    }
    setView("report");
  };

  const handleCreateReport = async () => {
    setCreating(true);
    try {
      let sourceUrl = "";
      try {
        const [tab] = await chrome.tabs.query({
          active: true,
          currentWindow: true,
        });
        const url = tab?.url || "";
        // Restricted pages can never be a report source — treat as URL-less.
        const restricted =
          !url ||
          /^(chrome|edge|about|chrome-extension|https:\/\/chromewebstore\.google)/i.test(
            url,
          );
        sourceUrl = restricted ? "" : url;
      } catch {
        // non-extension context (vite dev) — leave empty
      }

      // Empty-URL dedup: re-open a recent pending, doc-less report instead of
      // piling up empty ones when the user clicks New Report on a page we
      // cannot bind to.
      if (!sourceUrl) {
        const candidate = userReports.find((r: any) => {
          const recent =
            r.created_at &&
            Date.now() - new Date(r.created_at).getTime() < 30 * 60 * 1000;
          return (
            (r.status || "pending") === "pending" &&
            !r.report_url &&
            recent
          );
        });
        if (candidate) {
          addActivity("Reopened your recent empty report");
          await openReport(
            candidate.report_id,
            "New report",
            candidate.status || "pending",
          );
          return;
        }
      }

      const response = await createReport(sourceUrl);
      if (response.success && response.data) {
        const report = response.data as {
          report_id: string;
          report_url?: string;
          status?: string;
        };
        addActivity("Report created");
        await refresh();
        openReport(
          report.report_id,
          report.report_url || "New report",
          report.status || "draft",
        );
      } else {
        addActivity(
          `Create report failed: ${response.error || "Unknown error"}`,
        );
      }
    } finally {
      setCreating(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    setAuthenticated(false);
    setUserEmail("");
    setView("workspace");
  };

  return (
    <div className="flex h-full flex-col">
      {/* Account bar */}
      <div className="flex items-center justify-between border-b px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
            {(userEmail || "U").charAt(0).toUpperCase()}
          </div>
          <span className="truncate text-xs text-muted-foreground">
            {userEmail || "Logged in"}
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={handleLogout}
          aria-label="Log out"
        >
          <LogOut className="size-3.5" />
        </Button>
      </div>

      {/* New report */}
      <div className="space-y-3 border-b p-3">
        <Button
          className="w-full"
          size="sm"
          onClick={handleCreateReport}
          disabled={creating}
        >
          {creating ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Plus className="size-4" />
          )}
          {creating ? "Creating..." : "New Report"}
        </Button>
        <p className="text-[11px] leading-snug text-muted-foreground">
          A new report starts empty and adopts the current page as its source
          when you scan a form.
        </p>
      </div>

      {/* Report list */}
      <div className="flex items-center justify-between px-3 pt-3">
        <h2 className="text-sm font-medium">Your Reports</h2>
        <Button
          variant="ghost"
          size="icon-xs"
          onClick={refresh}
          disabled={loading}
          aria-label="Refresh reports"
        >
          <RefreshCw className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
        </Button>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-3">
        {apiOffline && userReports.length === 0 && (
          <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-3 text-center text-xs text-amber-800">
            Can't reach the API at localhost:8000 — is the server running?
            Start it with <span className="font-mono">docker compose up -d</span>.
          </div>
        )}
        {!apiOffline && userReports.length === 0 && (
          <div className="rounded-lg border border-dashed p-6 text-center">
            <FileText className="mx-auto size-6 text-muted-foreground/50" />
            <p className="mt-2 text-xs text-muted-foreground">
              No reports yet. Create your first report to start uploading
              documents.
            </p>
          </div>
        )}
        {userReports.map((report: any, idx: number) => {
          const status = report.status || "pending";
          const statusStyle =
            status === "completed"
              ? "bg-green-100 text-green-700"
              : status === "processing"
                ? "bg-amber-100 text-amber-700"
                : status === "failed"
                  ? "bg-red-100 text-red-700"
                  : "bg-muted text-muted-foreground";
          return (
            <button
              key={report.report_id || idx}
              onClick={() =>
                openReport(
                  report.report_id,
                  report.report_url || report.title || `Report ${idx + 1}`,
                  status,
                )
              }
              className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/40"
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
                  <FileText className="size-4 shrink-0 text-muted-foreground" />
                  <span className="truncate">
                    {report.title || report.report_url || `Report ${idx + 1}`}
                  </span>
                </span>
                <span
                  className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] capitalize ${statusStyle}`}
                >
                  {status}
                </span>
              </div>
              {report.report_url && (
                <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
                  <ExternalLink className="size-3 shrink-0" />
                  <span className="truncate">{report.report_url}</span>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
