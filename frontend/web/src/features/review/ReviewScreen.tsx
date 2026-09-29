import { useEffect, useMemo, useState } from "react";
import {
  Check,
  X,
  Eye,
  FileText,
  MousePointerClick,
} from "lucide-react";
import { useStore } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import { transformToSections } from "@/features/shared/lib/formatters";
import {
  getFormSchema,
  approveMapping,
  autoFill,
  showToast,
} from "@/lib/messaging";
import { SourcePopover } from "@/features/review/SourcePopover";
import type { FormFieldWithOptions } from "@/store/useStore";

const AUTO_ACCEPT_CONFIDENCE = 0.8;

/** Short label for a source button: filename (or page ref), truncated. */
function shortSourceRef(ref: string): string {
  const name = ref.split("#")[0].trim();
  const page = ref.match(/page\s*(\d+)/i);
  const base = name || (page ? `p${page[1]}` : ref);
  return base.length > 14 ? `${base.slice(0, 12)}…` : base;
}

/**
 * Review & Apply screen — section tables.
 * Field | Value (editable) | Conf | Src | accept/reject
 */
export function ReviewScreen() {
  const {
    formFields,
    mappings,
    addActivity,
    setMappingDone,
    reportId,
    documents,
  } = useStore();
  const [formSchema, setFormSchema] = useState<any>(null);
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [userDecisions, setUserDecisions] = useState<
    Record<string, "accept" | "reject">
  >({});
  const [preview, setPreview] = useState(false);
  const [applying, setApplying] = useState(false);
  const [selectedSection, setSelectedSection] = useState(0);
  const [openSourceId, setOpenSourceId] = useState<string | null>(null);
  const mappingsKey = Object.keys(mappings).length;

  useEffect(() => {
    getFormSchema().then((response) => {
      if (response.success && response.data) {
        setFormSchema(response.data);
      }
    });
  }, [mappingsKey, formFields.length]);

  // Guardrail: when the active report changes (workspace switch or the
  // background following a known report page after a tab switch), drop any
  // in-progress edits/decisions so values never leak across reports.
  const activeReportId = useStore((s) => s.activeReportId);
  const contextReportId = useStore((s) => s.reportId);
  const contextKey = `${activeReportId ?? ""}|${contextReportId ?? ""}`;
  useEffect(() => {
    setOverrides({});
    setUserDecisions({});
    setPreview(false);
    setFormSchema(null);
  }, [contextKey]);

  // Esc closes the preview modal.
  useEffect(() => {
    if (!preview) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPreview(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [preview]);

  const sections = useMemo(
    () =>
      formSchema ? transformToSections(formFields, formSchema, mappings) : [],
    [formSchema, formFields, mappings],
  );

  // A re-scan can shrink the section list — clamp the selection so the
  // table never silently vanishes.
  useEffect(() => {
    if (selectedSection >= sections.length && sections.length > 0) {
      setSelectedSection(sections.length - 1);
    }
  }, [sections.length, selectedSection]);

  // Re-scan / re-map: drop user overrides that no longer match the new mapped
  // value (stale edits must not silently mask fresh results), keep overrides
  // on fields the new mapping didn't touch.
  useEffect(() => {
    setOverrides((prev) => {
      const next: Record<string, string> = {};
      Object.entries(prev).forEach(([fieldId, value]) => {
        const mapping = mappings[fieldId] || mappings[fieldId];
        const mapped = mapping?.value;
        if (mapped === undefined || mapped === value) next[fieldId] = value;
      });
      return next;
    });
  }, [mappingsKey]);

  // Accept/reject model: >=80% confidence is auto-accepted (unless the user
  // rejects it); everything else needs an explicit accept.
  const decisions = useMemo(() => {
    const out: Record<string, "accept" | "reject"> = {};
    sections.forEach((s) =>
      s.fields.forEach((f) => {
        out[f.field_id] =
          (f.confidence ?? 0) >= AUTO_ACCEPT_CONFIDENCE ? "accept" : "reject";
      }),
    );
    Object.keys(userDecisions).forEach((id) => {
      if (out[id] !== undefined) out[id] = userDecisions[id];
    });
    return out;
  }, [sections, userDecisions]);

  const totalFields = sections.reduce((n, s) => n + s.fields.length, 0);
  const acceptedCount = totalFields
    ? sections.reduce(
        (n, s) =>
          n +
          s.fields.filter((f) => decisions[f.field_id] === "accept").length,
        0,
      )
    : 0;

  const valueOf = (field: FormFieldWithOptions) =>
    overrides[field.field_id] ?? field.mappedValue ?? field.value ?? "";

  const isEdited = (field: FormFieldWithOptions) =>
    overrides[field.field_id] !== undefined;

  const setValue = (fieldId: string, value: string) =>
    setOverrides((prev) => ({ ...prev, [fieldId]: value }));

  const setDecision = (fieldId: string, decision: "accept" | "reject") =>
    setUserDecisions((prev) => ({ ...prev, [fieldId]: decision }));


  // Build the final mapping set from accepted rows (with edits applied) and
  // approve + fill via the background service worker.
  const buildAcceptedMappings = () => {
    const out: Record<string, any> = {};
    sections.forEach((s) =>
      s.fields.forEach((field) => {
        if (decisions[field.field_id] !== "accept") return;
        const base =
          mappings[field.field_id] || mappings[field.field_name] || {};
        const value = valueOf(field);
        if (!value) return;
        out[field.field_id] = { ...base, value, matched: true };
        if (field.field_name && !out[field.field_name]) {
          out[field.field_name] = out[field.field_id];
        }
      }),
    );
    return out;
  };

  const handleApply = async () => {
    setApplying(true);
    try {
      const acceptedMappings = buildAcceptedMappings();
      // Count accepted rows that carry a value (typed overrides on unmapped
      // fields count too — they are included in acceptedMappings above).
      const count = sections
        .flatMap((s) => s.fields)
        .filter(
          (f) => decisions[f.field_id] === "accept" && valueOf(f),
        ).length;
      if (count === 0) {
        addActivity("Nothing to apply â€” accept at least one field");
        return;
      }
      const approval = await approveMapping(acceptedMappings);
      if (!approval.success) {
        addActivity(`Approval failed: ${approval.error || "Unknown error"}`);
        return;
      }
      setMappingDone(true);
      addActivity(`Approved ${count} fields â€” filling form...`);
      const fill = await autoFill();
      if (fill.success) {
        const stats = (fill.data ?? {}) as { filled?: number; skipped?: number };
        const filled = stats.filled ?? count;
        const skipped = stats.skipped ?? 0;
        addActivity(`Form filling complete: ${filled} filled, ${skipped} skipped`);
        // Page-level receipt with REAL counts — never claim more than
        // actually landed on the page.
        showToast(
          `FormIQ — ${filled} field${filled !== 1 ? "s" : ""} filled${
            skipped ? ` · ${skipped} skipped` : ""
          }`,
        );
      } else {
        addActivity(`Fill failed: ${fill.error || "Unknown error"}`);
      }
      setPreview(false);
    } catch (err) {
      addActivity(
        `Apply failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    } finally {
      setApplying(false);
    }
  };

  if (totalFields === 0) {
    return (
      <div className="rounded-lg border border-dashed p-5 text-center">
        <MousePointerClick className="mx-auto size-6 text-muted-foreground/50" />
        <p className="mt-2 text-xs text-muted-foreground">
          No mappings yet. Scan the form on the page, then run{" "}
          <span className="font-medium text-foreground">Review Mapping</span> to
          match your documents against the detected fields.
        </p>
      </div>
    );
  }


  const confBadge = (field: FormFieldWithOptions) => {
    const conf = field.confidence ?? 0;
    const label =
      conf >= AUTO_ACCEPT_CONFIDENCE
        ? "High"
        : conf >= 0.5
          ? `${Math.round(conf * 100)}%`
          : "â€”";
    const cls =
      conf >= AUTO_ACCEPT_CONFIDENCE
        ? "bg-green-100 text-green-700"
        : conf >= 0.5
          ? "bg-amber-100 text-amber-700"
          : "bg-muted text-muted-foreground";
    return (
      <span
        className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] ${cls}`}
        title={field.reasoning || undefined}
      >
        {label}
      </span>
    );
  };

  const srcBadge = (field: FormFieldWithOptions) => {
    const src = field.source || "";
    if (!src || src === "none" || src === "unknown") {
      return <span className="text-[10px] text-muted-foreground/50">â€”</span>;
    }
    const label =
      src === "both" ? "pdf+img" : src === "image" ? "image" : "pdf";
    return (
      <span
        className="text-[10px] text-muted-foreground"
        title={field.source_location || undefined}
      >
        {label}
      </span>
    );
  };

  const renderRow = (field: FormFieldWithOptions) => {
    const decision = decisions[field.field_id] ?? "reject";
    const hasOptions = field.options && Object.keys(field.options).length > 0;
    const edited = isEdited(field);
    return (
      <tr
        key={field.field_id}
        className={`border-t ${decision === "reject" ? "opacity-55" : ""} ${
          edited ? "bg-primary/5" : ""
        }`}
      >
        <td className="max-w-[130px] px-2 py-1.5 align-middle">
          <span className="block truncate text-xs font-medium" title={field.field_name}>
            {field.field_name}
          </span>
        </td>
        <td className="px-1 py-1.5 align-middle">
          {hasOptions ? (
            <select
              value={valueOf(field)}
              onChange={(e) => setValue(field.field_id, e.target.value)}
              className={`w-full min-w-[110px] rounded border bg-background px-1.5 py-1 text-xs ${
                edited ? "border-primary/60" : ""
              }`}
            >
              <option value="">Not found in documents</option>
              {Object.entries(field.options!).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          ) : (
            <input
              value={valueOf(field)}
              onChange={(e) => setValue(field.field_id, e.target.value)}
              placeholder="Not found in documents"
              className={`w-full min-w-[110px] rounded border bg-background px-1.5 py-1 text-xs placeholder:text-muted-foreground/50 ${
                edited ? "border-primary/60" : ""
              }`}
            />
          )}
        </td>
        <td className="px-1 py-1.5 text-center align-middle">{confBadge(field)}</td>
        <td className="relative px-1 py-1.5 text-center align-middle">
          {field.source_ref && decision === "accept" ? (
            <>
              <button
                onClick={() =>
                  setOpenSourceId(
                    openSourceId === field.field_id ? null : field.field_id,
                  )
                }
                className={`inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-[10px] transition-colors hover:bg-muted ${
                  openSourceId === field.field_id
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground"
                }`}
                title="View source"
              >
                <FileText className="size-2.5" />
                {shortSourceRef(field.source_ref)}
              </button>
              {openSourceId === field.field_id && (
                <SourcePopover
                  field={field}
                  reportId={reportId}
                  documents={documents}
                  onClose={() => setOpenSourceId(null)}
                />
              )}
            </>
          ) : (
            srcBadge(field)
          )}
        </td>
        <td className="px-1 py-1.5 text-right align-middle">
          <button
            onClick={() =>
              setDecision(
                field.field_id,
                decision === "accept" ? "reject" : "accept",
              )
            }
            className={`rounded p-1 ${
              decision === "accept"
                ? "bg-green-100 text-green-700"
                : "bg-muted text-muted-foreground"
            }`}
            aria-label={decision === "accept" ? "Reject field" : "Accept field"}
            title={decision === "accept" ? "Accepted â€” click to reject" : "Click to accept"}
          >
            {decision === "accept" ? (
              <Check className="size-3.5" />
            ) : (
              <X className="size-3.5" />
            )}
          </button>
        </td>
      </tr>
    );
  };




  return (
    <div className="space-y-3">
      {/* Summary header */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium">Review &amp; Apply</h2>
        <span className="text-xs text-muted-foreground">
          {acceptedCount}/{totalFields} accepted
        </span>
      </div>

      {/* Section switcher chips — one full-width table at a time */}
      <div className="flex flex-wrap gap-1.5">
        {sections.map((section, idx) => {
          const ready = section.fields.filter(
            (f) => decisions[f.field_id] === "accept" && valueOf(f),
          ).length;
          const active = idx === selectedSection;
          return (
            <button
              key={section.tableId}
              onClick={() => setSelectedSection(idx)}
              className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors ${
                active
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-muted"
              }`}
              title={section.sectionName}
            >
              <span className="max-w-[160px] truncate">
                {section.sectionName}
              </span>{" "}
              <span className="text-[10px] opacity-70">
                {ready}/{section.fields.length}
              </span>
            </button>
          );
        })}
      </div>

      {/* Selected section table (full width) */}
      {sections[selectedSection] && (
        <div className="overflow-hidden rounded-lg border">
          <div className="flex items-center justify-between border-b bg-muted/40 px-2.5 py-1.5">
            <h3 className="truncate text-xs font-semibold">
              {sections[selectedSection].sectionName}
            </h3>
            <span className="shrink-0 text-[10px] text-muted-foreground">
              Section {selectedSection + 1}/{sections.length}
            </span>
          </div>
          <table className="w-full">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                <th className="px-2 py-1 font-medium">Field</th>
                <th className="px-1 py-1 font-medium">Value</th>
                <th className="px-1 py-1 text-center font-medium">Conf</th>
                <th className="px-1 py-1 text-center font-medium">Src</th>
                <th className="px-1 py-1" />
              </tr>
            </thead>
            <tbody>{sections[selectedSection].fields.map(renderRow)}</tbody>
          </table>
        </div>
      )}

      {/* Sticky action bar â€” always reachable in the scrollable panel */}
      {/* Hero action: Apply is the terminal action */}
      <div className="sticky bottom-0 -mx-3 mt-2 space-y-2 border-t bg-background px-3 py-2">
        <Button
          variant="outline"
          size="xs"
          className="w-full"
          onClick={() => setPreview(true)}
          disabled={acceptedCount === 0}
        >
          <Eye className="size-3" />
          Preview what will be filled ({acceptedCount})
        </Button>
        <Button
          size="lg"
          className="w-full"
          onClick={handleApply}
          disabled={applying || acceptedCount === 0}
        >
          {applying ? "Applying..." : `Apply to Form (${acceptedCount})`}
        </Button>
      </div>

      {/* Preview modal */}
      {preview && (
        <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[80%] w-full max-w-sm overflow-y-auto rounded-lg border bg-background p-4 shadow-lg">
            <h3 className="text-sm font-semibold">
              Preview â€” what will be filled
            </h3>
            <div className="mt-3 space-y-1.5">
              {sections
                .flatMap((s) => s.fields)
                .filter((field) => decisions[field.field_id] === "accept")
                .map((field) => (
                  <div
                    key={field.field_id}
                    className="flex items-baseline justify-between gap-2 text-xs"
                  >
                    <span className="min-w-0 shrink truncate text-muted-foreground">
                      {field.field_name}
                    </span>
                    <span className="shrink-0 text-muted-foreground">â†</span>
                    <span className="min-w-0 flex-1 truncate text-right font-medium">
                      {valueOf(field)}
                    </span>
                  </div>
                ))}
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPreview(false)}
              >
                Back
              </Button>
              <Button size="sm" onClick={handleApply} disabled={applying}>
                {applying ? "Applying..." : "Confirm & Fill"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

