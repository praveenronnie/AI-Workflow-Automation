import { useEffect } from "react";
import {
  FileUp,
  ScanText,
  Database,
  ListChecks,
  Check,
  Loader2,
  CircleDashed,
} from "lucide-react";
import { useStore } from "@/store/useStore";
import { getReport } from "@/lib/messaging";

const POLL_INTERVAL_MS = 4000;

/**
 * Pipeline strip (Phase 2): report-level processing progress.
 * Stages: Upload -> Extract -> Embed -> Map. The Upload/Extract/Embed
 * progress is derived from the report's server-side `status` field
 * (polled while the report is processing); the Map stage reflects
 * whether mappings exist in the store.
 */
export function PipelineStrip() {
  const {
    reportId,
    reportStatus,
    setReportStatus,
    documents,
    mappings,
    isMapping,
  } = useStore();

  // Poll the report while the backend is processing uploads. When the
  // status leaves "processing" the loop stops on its own (effect deps).
  useEffect(() => {
    if (!reportId || reportStatus !== "processing") return;
    let cancelled = false;
    const timer = setInterval(async () => {
      try {
        const response = await getReport(reportId);
        if (!cancelled && response.success && response.data) {
          const status = (response.data as { status?: string }).status;
          if (status && status !== reportStatus) {
            setReportStatus(status);
          }
        }
      } catch {
        // transient network errors — keep polling
      }
    }, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [reportId, reportStatus, setReportStatus]);

  const hasMappings = Object.keys(mappings).length > 0;

  // Stage resolution: extraction/embedding happen server-side as part of
  // the "processing" status; the UI presents them as sequential stages.
  const extractedDone =
    reportStatus === "completed" ||
    (reportStatus !== "processing" && documents.length > 0);
  const processing = reportStatus === "processing";
  const failed = reportStatus === "failed";
  const mappedDone = hasMappings;
  const mappingActive = isMapping;

  const stages = [
    {
      key: "upload",
      label: documents.length > 0 ? `${documents.length} doc${documents.length !== 1 ? "s" : ""}` : "Upload",
      icon: FileUp,
      state: documents.length > 0 ? "done" : "pending",
    },
    {
      key: "extract",
      label: "Extract",
      icon: ScanText,
      state: extractedDone ? "done" : processing ? "active" : "pending",
    },
    {
      key: "embed",
      label: "Embed",
      icon: Database,
      state: extractedDone ? "done" : processing ? "active" : "pending",
    },
    {
      key: "map",
      label: "Map",
      icon: ListChecks,
      state: mappedDone
        ? "done"
        : mappingActive || processing
          ? "active"
          : "pending",
    },
  ] as const;

  const microcopy = failed
    ? "Processing failed for one or more documents. Re-upload the affected files from Manage Documents."
    : processing
      ? "Extracting text and building embeddings — this runs in the cloud and usually takes under a minute."
      : mappedDone
        ? "Documents processed and mapped. Review the values, then apply."
        : documents.length > 0
          ? "Documents ready. Scan the form, then generate the mapping."
          : "Upload a document to get started.";

  return (
    <div className="flex items-center gap-1.5 px-1 py-0.5 text-xs">
      {stages.map((stage, idx) => {
        const Icon = stage.icon;
        const isLast = idx === stages.length - 1;
        return (
          <div key={stage.key} className="flex shrink-0 items-center gap-1">
            <span
              className={`flex size-4 items-center justify-center rounded-full ${
                failed
                  ? "bg-red-100 text-red-600"
                  : stage.state === "done"
                    ? "bg-green-100 text-green-700"
                    : stage.state === "active"
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground/40"
              }`}
            >
              {stage.state === "done" ? (
                <Check className="size-2.5" />
              ) : stage.state === "active" ? (
                <Loader2 className="size-2.5 animate-spin" />
              ) : (
                <Icon className="size-2.5" />
              )}
            </span>
            <span
              className={`text-[10px] ${
                stage.state === "pending"
                  ? "text-muted-foreground/50"
                  : "text-foreground"
              }`}
            >
              {stage.label}
            </span>
            {!isLast && <span className="text-muted-foreground/40">·</span>}
          </div>
        );
      })}
      <span
        className="ml-auto flex min-w-0 items-center gap-1 truncate text-[10px] text-muted-foreground"
        title={microcopy}
      >
        {failed ? (
          <CircleDashed className="size-3 shrink-0 text-red-500" />
        ) : processing ? (
          <Loader2 className="size-3 shrink-0 animate-spin" />
        ) : (
          <CircleDashed className="size-3 shrink-0" />
        )}
        <span className="truncate">
          {failed
            ? "Processing failed"
            : processing
              ? "Processing in the cloud"
              : mappedDone
                ? "Ready to review"
                : documents.length > 0
                  ? "Ready to scan"
                  : "Upload documents to start"}
        </span>
      </span>
    </div>
  );
}
