import { useStore } from "@/store/useStore";
import { Button } from "@/components/ui/button";
import { useEffect, useState } from "react";
import { transformToSections } from "@/lib/formatters";
import { getFormSchema } from "@/lib/messaging";

export function FormStatusSection() {
  const { formStats, formFields, mappings, setActiveDrawer } = useStore();
  const [formSchema, setFormSchema] = useState<any>(null);
  const mappingsKey = Object.keys(mappings).length;

  // Re-fetch the schema when the form / mapping state changes so the
  // section list (and its "View Tables" entry point) stays current after
  // a scan or mapping run instead of showing the initial mount snapshot.
  useEffect(() => {
    getFormSchema().then((response) => {
      if (response.success && response.data) {
        setFormSchema(response.data);
      } else {
        console.warn("Failed to load form schema:", response.error);
      }
    });
  }, [formFields.length, mappingsKey]);

  const sections = formSchema
    ? transformToSections(formFields, formSchema, mappings)
    : [];

  return (
    <div className="space-y-3">
      <h2 className="text-sm font-medium">Form Status</h2>

      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md border p-2 text-center">
          <div className="text-lg font-bold">{formStats.fieldsDetected}</div>
          <div className="text-xs text-muted-foreground">Detected</div>
        </div>
        <div className="rounded-md border p-2 text-center">
          <div className="text-lg font-bold text-green-600">
            {formStats.fieldsMapped}
          </div>
          <div className="text-xs text-muted-foreground">Mapped</div>
        </div>
        <div className="rounded-md border p-2 text-center">
          <div className="text-lg font-bold text-destructive">
            {formStats.missingFields}
          </div>
          <div className="text-xs text-muted-foreground">Missing</div>
        </div>
      </div>

      <div className="space-y-2">
        <Button
          variant="outline"
          size="sm"
          className="w-full"
          onClick={() => setActiveDrawer("fields")}
        >
          View Fields ({formFields.length})
        </Button>
        {sections.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            className="w-full"
            onClick={() => setActiveDrawer("fields-table")}
          >
            View Tables ({sections.length})
          </Button>
        )}
      </div>
    </div>
  );
}
