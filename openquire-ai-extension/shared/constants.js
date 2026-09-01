// Constants shared across the extension
const EXTENSION = {
  NAME: "OpenQuire AI Form Automation",
  VERSION: "1.0.0",
  STORAGE_KEYS: {
    SOURCE_DATA: "sourceData",
    FORM_SCHEMA: "formSchema",
    MAPPINGS: "mappings",
    STATE: "extensionState",
    CURRENT_REPORT_ID: "currentReportId",
    ACCESS_TOKEN: "accessToken",
    USER_EMAIL: "userEmail",
  },
  EVENTS: {
    FORM_SCANNED: "form:scanned",
    DATA_UPLOADED: "data:uploaded",
    MAPPING_GENERATED: "mapping:generated",
    MAPPING_APPROVED: "mapping:approved",
    AUTO_FILL_STARTED: "autofill:started",
    AUTO_FILL_COMPLETED: "autofill:completed",
  },
};

const FIELD_TYPES = {
  TEXT: "text",
  TEXTAREA: "textarea",
  SELECT: "select",
  CHECKBOX: "checkbox",
  RADIO: "radio",
  MULTISELECT: "multiselect",
  FILE: "file",
};

const FILL_EVENTS = ["input", "change", "blur"];
