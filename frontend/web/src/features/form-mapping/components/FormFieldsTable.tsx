import { useState, useEffect } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { FormSection } from "@/store/useStore";
import {
  getConfidenceColor,
  formatOptions,
  formatValue,
} from "@/features/shared/lib/formatters";

interface FormFieldsTableProps {
  sections: FormSection[];
  viewMode?: "raw" | "filled";
}

export function FormFieldsTable({
  sections,
  viewMode = "filled",
}: FormFieldsTableProps) {
  const [expandedSections, setExpandedSections] = useState<Set<number>>(
    new Set(sections.map((s) => s.tableId).slice(0, 1)),
  );

  // Keep expansion state in sync when the sections list reloads (e.g. after
  // mapping completes): drop stale ids, keep the user's open sections, and
  // guarantee at least the first section is expanded.
  useEffect(() => {
    setExpandedSections((prev) => {
      const valid = new Set(sections.map((s) => s.tableId));
      const kept = new Set([...prev].filter((id) => valid.has(id)));
      if (kept.size === 0 && sections.length > 0) {
        kept.add(sections[0].tableId);
      }
      return kept;
    });
  }, [sections]);

  const toggleSection = (tableId: number) => {
    const newExpanded = new Set(expandedSections);
    if (newExpanded.has(tableId)) {
      newExpanded.delete(tableId);
    } else {
      newExpanded.add(tableId);
    }
    setExpandedSections(newExpanded);
  };

  if (sections.length === 0) {
    return (
      <div className="text-xs text-muted-foreground text-center py-8">
        No form sections available. Scan a form first.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="text-xs font-medium text-muted-foreground mb-3">
        {viewMode === "filled" ? "Filled Form Fields" : "Detected Form Fields"}
      </div>

      {sections.map((section) => {
        const isExpanded = expandedSections.has(section.tableId);
        const mappedCount = section.fields.filter((f) => f.mappedValue).length;

        return (
          <div key={section.tableId} className="border rounded-md">
            {/* Section Header */}
            <button
              onClick={() => toggleSection(section.tableId)}
              className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="size-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="size-4 text-muted-foreground" />
              )}
              <span className="flex-1 text-left text-sm font-medium">
                {section.sectionName}
              </span>
              <span className="text-xs text-muted-foreground">
                {mappedCount}/{section.fields.length}
              </span>
            </button>

            {/* Section Content */}
            {isExpanded && (
              <div className="border-t overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-muted/50 border-b">
                      <th className="text-left px-3 py-2 font-medium">
                        Field Name
                      </th>
                      <th className="text-left px-3 py-2 font-medium">
                        Options
                      </th>
                      {viewMode === "filled" && (
                        <>
                          <th className="text-left px-3 py-2 font-medium">
                            Mapped Value
                          </th>
                          <th className="text-center px-3 py-2 font-medium">
                            Confidence
                          </th>
                        </>
                      )}
                    </tr>
                  </thead>
                  <tbody>
                    {section.fields.map((field) => (
                      <tr
                        key={field.field_id}
                        className="border-b hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-3 py-2">
                          <div className="font-medium text-foreground">
                            {field.field_name}
                          </div>
                          {field.source && (
                            <div className="text-xs text-muted-foreground">
                              {field.source}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          <div className="text-muted-foreground max-w-xs truncate">
                            {formatOptions(field.options)}
                          </div>
                        </td>
                        {viewMode === "filled" && (
                          <>
                            <td className="px-3 py-2">
                              <div
                                className={
                                  field.mappedValue
                                    ? "font-medium text-foreground"
                                    : "text-muted-foreground"
                                }
                              >
                                {formatValue(field.mappedValue)}
                              </div>
                              {field.reasoning && (
                                <div className="text-xs text-muted-foreground mt-1 line-clamp-2">
                                  {field.reasoning}
                                </div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-center">
                              {(field.confidence ?? 0) > 0 ? (
                                <div
                                  className={`font-medium ${getConfidenceColor(field.confidence ?? 0)}`}
                                >
                                  {((field.confidence ?? 0) * 100).toFixed(0)}%
                                </div>
                              ) : (
                                <span className="text-muted-foreground">—</span>
                              )}
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
