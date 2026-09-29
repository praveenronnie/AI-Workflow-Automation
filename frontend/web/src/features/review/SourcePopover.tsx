import { useEffect, useRef, useState } from "react";
import { X, FileWarning } from "lucide-react";
import { getSourceFileUrl } from "@/lib/messaging";
import type { FormFieldWithOptions } from "@/store/useStore";

interface SourcePopoverProps {
  field: FormFieldWithOptions;
  reportId: string | null;
  documents: Array<{ id: string; name: string; docType?: string }>;
  onClose: () => void;
}

/** Pull the source filename out of a ref like "photo2.jpg#a1b2c3d4" or "page 3". */
function refFilename(ref: string): string {
  const withoutPage = /^(?:page\s*\d+;?\s*)/i.test(ref)
    ? ref.replace(/^(?:page\s*\d+;?\s*)+/i, "")
    : ref;
  const name = withoutPage.split("#")[0].trim();
  return name.replace(/[;,]+$/, "");
}

function refPage(ref: string): number | null {
  const match = ref.match(/page\s*(\d+)/i);
  return match ? Number(match[1]) : null;
}

/**
 * In-panel popover that previews the source document for a mapped field.
 * Anchored top-right of its trigger button; lazy-loads the file (fetched
 * with auth by the background, surfaced as an object URL).
 */
export function SourcePopover({
  field,
  reportId,
  documents,
  onClose,
}: SourcePopoverProps) {
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [mime, setMime] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const ref = useRef<HTMLSpanElement>(null);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Resolve which report document matches this field's source ref
  const sourceRef = field.source_ref || field.source_location || "";
  const filename = sourceRef ? refFilename(sourceRef) : "";
  const doc =
    (filename &&
      documents.find(
        (d) =>
          d.name === filename ||
          d.name.toLowerCase() === filename.toLowerCase(),
      )) ||
    null;
  const page = sourceRef ? refPage(sourceRef) : null;

  useEffect(() => {
    let revoked: string | null = null;
    (async () => {
      if (!reportId || !doc) {
        setLoading(false);
        return;
      }
      try {
        const response = await getSourceFileUrl(reportId, doc.id);
        if (response.success && response.data) {
          const data = response.data as { url: string; mime: string };
          setFileUrl(data.url);
          setMime(data.mime || "");
          revoked = data.url;
        } else {
          setError(response.error || "Could not load source");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not load source");
      } finally {
        setLoading(false);
      }
    })();
    return () => {
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [reportId, doc?.id]);

  // Close on Escape / outside click
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    const onClick = (e: MouseEvent) => {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(e.target as Node) &&
        ref.current &&
        !ref.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onClick);
    };
  }, [onClose]);

  const isPdf =
    (mime && mime.includes("pdf")) ||
    (!mime && /\.pdf$/i.test(filename || doc?.name || ""));

  return (
    <span ref={ref} className="relative inline-flex">
      <div
        ref={popoverRef}
        className="absolute bottom-full right-0 z-[10002] mb-1 w-[320px] overflow-hidden rounded-lg border bg-background shadow-lg"
      >
        <div className="flex items-center justify-between gap-2 border-b bg-muted/40 px-2.5 py-1.5">
          <span className="min-w-0 flex-1 truncate text-[11px] font-medium">
            {doc?.name || filename || field.source_location || "Source"}
            {page ? ` · page ${page}` : ""}
          </span>
          <button
            onClick={onClose}
            className="shrink-0 rounded p-0.5 hover:bg-muted"
            aria-label="Close source preview"
          >
            <X className="size-3" />
          </button>
        </div>

        <div className="flex h-[300px] items-center justify-center bg-muted/20">
          {loading ? (
            <span className="text-xs text-muted-foreground">Loading source…</span>
          ) : error ? (
            <span className="flex items-center gap-1.5 px-4 text-center text-xs text-destructive">
              <FileWarning className="size-4 shrink-0" />
              {error}
            </span>
          ) : !fileUrl ? (
            <span className="px-4 text-center text-xs text-muted-foreground">
              No matching document found for this source.
            </span>
          ) : isPdf ? (
            <iframe
              src={`${fileUrl}${page ? `#page=${page}` : ""}`}
              className="h-full w-full border-0"
              title="Source document preview"
            />
          ) : (
            <img
              src={fileUrl}
              alt="Source document preview"
              className="max-h-full max-w-full object-contain"
            />
          )}
        </div>

        {field.source_excerpt && (
          <p className="border-t px-2.5 py-1.5 text-[10px] leading-snug text-muted-foreground">
            “{field.source_excerpt}”
          </p>
        )}
      </div>
    </span>
  );
}
