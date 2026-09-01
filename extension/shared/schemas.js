// Shared schema definitions for form fields and mapping data

/**
 * Field schema describing a form field discovered on the page.
 * @typedef {Object} FieldSchema
 * @property {string} section_name - Name of the section containing this field
 * @property {string} field_name - Human-readable label of the field
 * @property {string} field_type - One of FIELD_TYPES values
 * @property {string} current_value - Current value in the field
 * @property {string[]} options - Available options (for select/radio fields)
 * @property {string} selector - CSS selector to uniquely identify this field
 */

/**
 * Form schema describing the entire scanned form.
 * @typedef {Object} FormSchema
 * @property {Array<{name: string, fields: FieldSchema[]}>} sections
 */

/**
 * Mapping between form field names and source data keys.
 * @typedef {Object} FieldMapping
 * @property {string} formField - Name of the field on the form
 * @property {string} sourceKey - Key in the source data
 * @property {*} value - Value to fill
 */

// No runtime code needed - this serves as documentation
