import { useState } from "react";
import {
  ArrowLeft,
  FileText,
  ExternalLink,
  FolderOpen,
  ListChecks,
  ScrollText,
  Lock,
  LockOpen,
} from "lucide-react";
import { useStore } from "@/store/useStore";
import { PipelineStrip } from "@/features/pipeline/PipelineStrip";
import { DocumentsSection } from "@/features/reports/components/DocumentsSection";
import { ActionsSection } from "@/features/dashboard/components/ActionsSection";
import { ReviewScreen } from "@/features/review/ReviewScreen";
import { ActivitySection } from "@/features/reports/components/ActivitySection";
import { Drawer } from "@/features/dashboard/components/Drawer";

function safeHostname(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

/**
 * Report detail view — stage-based layout:
 *   header (back · title · status · identity/lock)
 *   pipeline strip (compact, always visible)
 *   ONE stage at a time: Docs | Review | Log   (footer tab bar)
 */
export function ReportView() {
  const {
    activeReportTitle,
    reportStatus,
    setView,
    lockState,
    pageContext,
    userEmail,
    documents,
    reportTab,
    setReportTab,
    apiOffline,
  } = useStore();
  const [docsExpanded, setDocsExpanded] = useState(false);

  const statusStyle =
    reportStatus === "completed"
      ? "bg-green-100 text-green-700"
      : reportStatus === "processing"
        ? "bg-amber-100 text-amber-700"
        : reportStatus === "failed"
          ? "bg-red-100 text-red-700"
          : "bg-muted text-muted-foreground";

  const offContext = !!pageContext && !pageContext.matchesReport;
  // Documents count as "done" only after server-side processing completed —
  // a freshly-created (pending) report with no docs must NOT collapse.
  const docsDone =
    documents.length > 0 && reportStatus === "completed";

  const tabs = [
    { key: "docs" as const, label: "Docs", icon: FolderOpen, badge: documents.length || undefined },
    { key: "review" as const, label: "Review", icon: ListChecks },
    { key: "log" as const, label: "Log", icon: ScrollText },
  ];


  return (
    <div className="flex h-full flex-col">
      {/* Header: back · title · status · identity/lock */}
      <div className="flex items-center justify-between gap-2 border-b px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <button
            onClick={() => setView("workspace")}
            className="rounded-md p-1 hover:bg-muted"
            aria-label="Back to workspace"
          >
            <ArrowLeft className="size-4" />
          </button>
          <FileText className="size-4 shrink-0 text-muted-foreground" />
          <span
            className="min-w-0 truncate text-sm font-semibold"
            title={activeReportTitle}
          >
            {activeReportTitle || "Report"}
          </span>
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] capitalize ${statusStyle}`}
          >
            {reportStatus}
          </span>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {lockState.hasLock && !lockState.isReadOnly && (
            <span
              className="text-muted-foreground"
              title={`You hold the report lock${lockState.lockExpiresAt ? ` (expires ${new Date(lockState.lockExpiresAt).toLocaleTimeString()})` : ""}`}
            >
              <Lock className="size-3.5" />
            </span>
          )}
          {lockState.isReadOnly && (
            <span
              className="text-amber-600"
              title={`Read-only — locked by ${lockState.lockHolderUser || "another user"}`}
            >
              <LockOpen className="size-3.5" />
            </span>
          )}
          <div
            className="flex size-7 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary"
            title={userEmail || "You"}
          >
            {(userEmail || "U").charAt(0).toUpperCase()}
          </div>
        </div>
      </div>

      {/* Banners + pipeline */}
      <div className="space-y-2 border-b px-3 py-2">
        {apiOffline && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Can't reach the API — uploads and mapping won't work until it's
            back.
          </div>
        )}
        {offContext && (
          <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
            You're on a different page than this report's source. Scanning now
            will scan{" "}
            <span className="font-medium">{safeHostname(pageContext!.url)}</span>{" "}
            and bind it to this report.
          </div>
        )}
        {lockState.isReadOnly && (
          <div className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-800">
            Read-only — report is locked by{" "}
            {lockState.lockHolderUser || "another user"}. You can view but not
            modify until they release it.
          </div>
        )}
        <PipelineStrip />
        {activeReportTitle && activeReportTitle.startsWith("http") && (
          <a
            href={activeReportTitle}
            target="_blank"
            rel="noreferrer"
            className="flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground"
          >
            <ExternalLink className="size-3" />
            {activeReportTitle}
          </a>
        )}
      </div>

      {/* Stage content */}
      <div className="flex-1 overflow-y-auto p-3">
        {reportTab === "docs" && (
          <div className="space-y-3">
            {/* Collapsed summary once documents are processed */}
            {docsDone && !docsExpanded ? (
              <button
                onClick={() => setDocsExpanded(true)}
                className="w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted/40"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">
                    {documents.length} document
                    {documents.length !== 1 ? "s" : ""} · processed ✓
                  </span>
                  <span className="text-xs text-muted-foreground">Manage</span>
                </div>
              </button>
            ) : (
              <>
                <DocumentsSection />
                <ActionsSection />
                {docsDone && (
                  <button
                    onClick={() => setDocsExpanded(false)}
                    className="text-xs text-muted-foreground hover:text-foreground"
                  >
                    Collapse documents
                  </button>
                )}
              </>
            )}
          </div>
        )}

        {reportTab === "review" && <ReviewScreen />}

        {reportTab === "log" && <ActivitySection />}
      </div>

      {/* Footer stage tabs */}
      <div className="flex border-t">
        {tabs.map(({ key, label, icon: Icon, badge }) => (
          <button
            key={key}
            onClick={() => setReportTab(key)}
            className={`flex flex-1 items-center justify-center gap-1.5 py-2 text-xs font-medium transition-colors ${
              reportTab === key
                ? "border-b-2 border-primary text-primary"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="size-3.5" />
            {label}
            {badge !== undefined && badge > 0 && (
              <span className="rounded-full bg-muted px-1.5 text-[10px]">
                {badge}
              </span>
            )}
          </button>
        ))}
      </div>

      <Drawer />
    </div>
  );
}
