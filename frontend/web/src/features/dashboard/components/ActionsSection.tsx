import { normalizeMappings, type BackendMapping } from "@/features/shared/lib/formatters";
import { Scan, ListChecks } from "lucide-react";
import { useStore } from "@/store/useStore";
import { Button } from "@/features/shared/components/ui/button";
import { DomainSelector } from "@/features/form-mapping/components/DomainSelector";
import {
  scanForm,
  generateMapping,
} from "@/lib/messaging";
import { useState, useEffect } from "react";

export function ActionsSection() {
  // Use selector-based subscriptions to avoid unnecessary re-renders
  const isScanning = useStore((state) => state.isScanning);
  const setIsScanning = useStore((state) => state.setIsScanning);
  const isMapping = useStore((state) => state.isMapping);
  const setIsMapping = useStore((state) => state.setIsMapping);
  const setFormFields = useStore((state) => state.setFormFields);
  const setFormStats = useStore((state) => state.setFormStats);
  const setMappings = useStore((state) => state.setMappings);
  const addActivity = useStore((state) => state.addActivity);
  const documents = useStore((state) => state.documents);

  // Progress state
  const [scanProgress, setScanProgress] = useState<{
    stage: string;
    found: number;
    total?: number;
  } | null>(null);

  // Listen for progress updates
  useEffect(() => {
    const handleMessage = (msg: any) => {
      if (msg.action === "updateScanProgress") {
        setScanProgress(msg.progress);
      }
    };

    if (typeof chrome !== "undefined" && chrome.runtime?.id) {
      chrome.runtime.onMessage.addListener(handleMessage);
      return () => chrome.runtime.onMessage.removeListener(handleMessage);
    }
  }, []);


  const handleScanForm = async () => {
    setIsScanning(true);
    setScanProgress(null);
    addActivity("Scanning Form...");
    try {
      // Scan is DOM-driven; platform config lives in the extension's
      // declarative adapter JSONs, not in frontend code.
      const response = await scanForm({});
      if (response.success && response.data) {
        const data = response.data as {
          fields?: Array<{
            field_id: string;
            field_name: string;
            field_type: string;
          }>;
          sections?: Array<{
            fields: Array<{
              field_id: string;
              field_name: string;
              field_type: string;
            }>;
          }>;
          scanLog?: string[];
          stats?: {
            fieldsFound: number;
            sectionsFound: number;
            imagesFound: number;
            tablesFound: number;
            duration: number;
          };
        };
        const fields =
          data.fields || data.sections?.flatMap((s) => s.fields) || [];
        setFormFields(fields);
        setFormStats({
          fieldsDetected: fields.length,
          fieldsMapped: 0,
          missingFields: fields.length,
        });

        // Log scan statistics
        if (data.stats) {
          addActivity(
            `Scan complete: ${data.stats.fieldsFound} fields, ${data.stats.sectionsFound} sections, ${data.stats.duration.toFixed(0)}ms`,
          );
        } else {
          addActivity("Form Scan Complete");
        }
      } else {
        addActivity(`Scan failed: ${response.error || "Unknown error"}`);
      }
    } catch (err) {
      addActivity(
        `Scan failed: ${err instanceof Error ? err.message : "Unknown error"}`,
      );
    }
    setIsScanning(false);
    setScanProgress(null);
  };

  const handleReviewMapping = async () => {
    // Always regenerate: the backend map call is synchronous and cheap to
    // re-run, and the user expects fresh results after a re-scan.
    setIsMapping(true);
    addActivity("Generating Mappings...");
      try {
        const response = await generateMapping();
        if (response.success && response.data) {
          // Synchronous mapping: the backend returns
          // { report_id, mappings: [...], populated_schema, evidence_count }
          // in `data` (surfaced by the background service worker).
          const payload = (response.data ?? {}) as {
            mappings?: BackendMapping[];
            populated_schema?: unknown;
            evidence_count?: number;
          };
          const newMappings = normalizeMappings(payload.mappings);
          setMappings(newMappings);
          const list = payload.mappings || [];
          const mapped = list.filter((m) => m.matched).length;
          const total = list.length;
          setFormStats({
            fieldsDetected: total,
            fieldsMapped: mapped,
            missingFields: total - mapped,
          });
          // Surface the review stage immediately — the user's next step.
          useStore.getState().setReportTab("review");
          addActivity(
            `Mapping generated: ${mapped}/${total} fields matched — review before applying`,
          );
        } else {
          addActivity(`Mapping failed: ${response.error || "Unknown error"}`);
        }
      } catch (err) {
        addActivity(
          `Mapping failed: ${err instanceof Error ? err.message : "Unknown error"}`,
        );
      }
    setIsMapping(false);
  };

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium">Actions</h2>

      {/* Domain routing for /map (required by the backend) */}
      <DomainSelector />

      {/* Progress indicator */}
      {isScanning && scanProgress && (
        <div className="text-xs text-muted-foreground">
          Scanning {scanProgress.stage}... Found {scanProgress.found}
          {scanProgress.total && `/${scanProgress.total}`}
        </div>
      )}

      <div className="space-y-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={handleScanForm}
          disabled={isScanning}
        >
          <Scan className="size-4" />
          {isScanning ? "Scanning..." : "Scan Form"}
        </Button>

        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={handleReviewMapping}
          disabled={isMapping || documents.length === 0}
        >
          <ListChecks className="size-4" />
          {isMapping ? "Generating..." : "Review Mapping"}
        </Button>
      </div>
    </div>
  );
}
