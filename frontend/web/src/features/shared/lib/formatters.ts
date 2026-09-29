import type {
  FormField,
  FormFieldWithOptions,
  FormSection,
  Mapping,
} from "@/store/useStore";

interface FormSchemaTable {
  tableId: number;
  tableName: string;
  fields: Array<{
    fieldName: string;
    value: string | null;
    options?: Record<string, string>;
    rowId: number;
    cellDefinitionId: number;
    columnId: number;
  }>;
}

interface FormSchemaData {
  report_id: string;
  sections: Array<{
    name: string;
    tableId: number;
  }>;
  tables: FormSchemaTable[];
}

export function transformToSections(
  formFields: FormField[],
  formSchema: FormSchemaData | any | null,
  mappings: Record<string, Mapping>,
): FormSection[] {
  if (!formSchema) {
    return buildSectionsFromFields(formFields, mappings);
  }

  const sections: FormSection[] = [];

  // --- Shape 1: tables + sections arrays (backend-normalized schema) ---
  //   { sections: [{name, tableId}], tables: [{tableId, fields:[{fieldName,...}]}] }
  if (
    Array.isArray(formSchema.tables) &&
    Array.isArray(formSchema.sections)
  ) {
    formSchema.sections.forEach((section: any) => {
      const schemaTable = formSchema.tables.find(
        (t: any) => t.tableId === section.tableId,
      );
      if (!schemaTable) return;
      const tableFields = transformTableFields(schemaTable, formFields, mappings);
      if (tableFields.length > 0) {
        sections.push({
          sectionName: section.name,
          tableId: section.tableId,
          fields: tableFields,
        });
      }
    });
    if (sections.length > 0) return sections;
  }

  // --- Shape 2: sections with inline fields (scanner payload) ---
  //   { sections: [{name, fields:[{field_id, field_name,...}]}] }
  if (Array.isArray(formSchema.sections)) {
    formSchema.sections.forEach((section: any, idx: number) => {
      const rawFields: any[] = Array.isArray(section.fields)
        ? section.fields
        : [];
      if (rawFields.length === 0) return;
      sections.push({
        sectionName: section.name || section.sectionName || `Section ${idx + 1}`,
        tableId:
          section.tableId ?? section.table_id ?? idx + 1,
        fields: rawFields.map((f) =>
          mapScannedField(f, formFields, mappings),
        ),
      });
    });
    return sections;
  }

  // --- Fallback: flatten raw scanned fields into a single section ---
  return buildSectionsFromFields(formFields, mappings);
}

function transformTableFields(
  schemaTable: any,
  formFields: FormField[],
  mappings: Record<string, Mapping>,
): FormFieldWithOptions[] {
  return (schemaTable.fields || []).map((schemaField: any) => {
    const fieldName = schemaField.fieldName || schemaField.field_name || "";
    const matchedField = formFields.find(
      (f) =>
        f.field_name === fieldName ||
        f.field_id === schemaField.field_id ||
        stripField(f.field_name) === stripField(fieldName),
    );

    const fieldId = matchedField?.field_id || schemaField.field_id || fieldName;
    const mapping = mappings[fieldId];

    return {
      field_id: fieldId,
      field_name: fieldName || fieldId,
      field_type: matchedField?.field_type || schemaField.fieldType || schemaField.field_type || "text",
      selector: matchedField?.selector || schemaField.selector,
      options: normalizeOptions(schemaField.options || (matchedField as any)?.options),
      mappedValue: mapping?.value ?? schemaField.value ?? null,
      confidence: mapping?.confidence || 0,
      source: (mapping as any)?.source,
      reasoning: (mapping as any)?.reasoning,
      source_location: (mapping as any)?.source_location,
      source_ref: (mapping as any)?.source_ref,
      source_excerpt: (mapping as any)?.source_excerpt,
    };
  });
}

function mapScannedField(
  f: any,
  formFields: FormField[],
  mappings: Record<string, Mapping>,
): FormFieldWithOptions {
  const fieldName = f.field_name || f.fieldName || f.label || "";
  const fieldId = f.field_id || f.fieldId || fieldName;
  const mapping = mappings[fieldId] || mappings[fieldName];
  return {
    field_id: fieldId,
    field_name: fieldName || fieldId,
    field_type:
      f.field_type || f.fieldType || formFields.find((x) => x.field_id === fieldId)?.field_type || "text",
    selector: f.selector,
    options: normalizeOptions(f.options),
    mappedValue: mapping?.value ?? f.value ?? null,
    confidence: mapping?.confidence || 0,
    source: (mapping as any)?.source,
    reasoning: (mapping as any)?.reasoning,
    source_location: (mapping as any)?.source_location,
    source_ref: (mapping as any)?.source_ref,
    source_excerpt: (mapping as any)?.source_excerpt,
  };
}

function buildSectionsFromFields(
  formFields: FormField[],
  mappings: Record<string, Mapping>,
): FormSection[] {
  if (!formFields || formFields.length === 0) return [];
  return [
    {
      sectionName: "Detected Fields",
      tableId: 1,
      fields: formFields.map((f) => {
        const fieldId = f.field_id || f.field_name;
        const mapping = mappings[fieldId] || mappings[f.field_name];
        return {
          ...f,
          options: normalizeOptions((f as any).options),
          mappedValue: mapping?.value ?? null,
          confidence: mapping?.confidence || 0,
          source: (mapping as any)?.source,
          reasoning: (mapping as any)?.reasoning,
          source_location: (mapping as any)?.source_location,
          source_ref: (mapping as any)?.source_ref,
          source_excerpt: (mapping as any)?.source_excerpt,
        } as FormFieldWithOptions;
      }),
    },
  ];
}

/** Normalize `options`, which may be an array of strings, an object, or undefined. */
function normalizeOptions(options: any): Record<string, string> {
  if (!options) return {};
  if (typeof options === "object" && !Array.isArray(options)) return options;
  if (Array.isArray(options)) {
    const out: Record<string, string> = {};
    options.forEach((o: any) => {
      if (typeof o === "string") out[o] = o;
      else if (o && typeof o === "object") {
        const v = o.value ?? o.label ?? o.text ?? String(o);
        const k = o.value ?? String(v);
        out[String(k)] = String(v);
      }
    });
    return out;
  }
  return {};
}

function stripField(s: string): string {
  return (s || "").toLowerCase().replace(/\s+/g, " ").trim();
}

export function getConfidenceColor(confidence: number): string {
  if (confidence >= 0.8) return "text-green-600";
  if (confidence >= 0.5) return "text-amber-600";
  return "text-destructive";
}

export function getConfidenceLabel(confidence: number): string {
  if (confidence >= 0.8) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}

export function formatOptions(
  options: Record<string, string> | undefined,
): string {
  if (!options || Object.keys(options).length === 0) return "—";
  return Object.values(options).slice(0, 3).join(", ");
}

export function formatValue(value: string | null | undefined): string {
  return value || "—";
}

export interface BackendMapping {
  field_id?: string;
  field_name?: string;
  section_name?: string;
  table_id?: string;
  matched?: boolean;
  value?: unknown;
  option_id?: string | null;
  confidence?: number;
  reasoning?: string;
  source?: string;
  mapping_method?: string;
  source_location?: string;
}

/**
 * Normalize the backend `/map` response (an array of per-field mapping rows)
 * into the store's field-keyed lookup `Record<string, Mapping>`.
 *
 * The backend keys rows by `field_id` (derived from the scanned form), so we
 * index by both field_id and field_name to survive the scanner↔backend key
 * differences (the FormFieldsTable / transformToSections resolve via
 * `mappings[fieldId] || mappings[fieldName]`).
 */
export function normalizeMappings(
  arr: BackendMapping[] | null | undefined,
): Record<string, { value?: string; confidence?: number; matched?: boolean; option_id?: string | null; source?: string; reasoning?: string; source_location?: string; mapping_method?: string }> {
  const out: Record<string, { value?: string; confidence?: number; matched?: boolean; option_id?: string | null; source?: string; reasoning?: string; source_location?: string; mapping_method?: string }> = {};
  if (!Array.isArray(arr)) return out;
  for (const m of arr) {
    const value = (m.value === null || m.value === undefined) ? undefined : String(m.value);
    const entry = {
      value,
      confidence: m.confidence ?? 0,
      matched: m.matched ?? (value !== undefined),
      option_id: m.option_id ?? undefined,
      source: m.source,
      reasoning: m.reasoning,
      source_location: m.source_location,
      source_ref: (m as any).source_ref,
      source_excerpt: (m as any).source_excerpt,
      mapping_method: m.mapping_method,
    };
    if (m.field_id) out[m.field_id] = entry;
    if (m.field_name && !out[m.field_name]) out[m.field_name] = entry;
  }
  return out;
}
