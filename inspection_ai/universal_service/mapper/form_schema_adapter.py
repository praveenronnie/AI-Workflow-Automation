import re
from typing import List, Dict, Any, Tuple, Optional

from ..models.form_schema import FormField, FormSection, UniversalFormSchema


def normalize_token(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def normalize_form_schema(
    form_schema: Dict[str, Any], domain: str = "pca_site_assessment"
) -> Tuple[UniversalFormSchema, Dict[str, Dict]]:
    if "tables" in form_schema:
        return from_openquire_schema(form_schema, domain=domain)
    if "sections" in form_schema:
        return from_universal_schema(form_schema)
    if "fields" in form_schema:
        schema = UniversalFormSchema(
            form_id=form_schema.get("form_id") or form_schema.get("report_id") or "root",
            domain=form_schema.get("domain") or domain,
            sections=[
                FormSection(
                    id="root",
                    title=form_schema.get("title", "Root"),
                    fields=[field_from_dict(f) for f in form_schema["fields"]],
                )
            ],
        )
        return schema, {}
    raise ValueError("form_schema must contain 'tables' or 'sections' or 'fields'")


def from_openquire_schema(
    form_schema: Dict[str, Any], domain: str = "pca_site_assessment"
) -> Tuple[UniversalFormSchema, Dict[str, Dict]]:
    sections: List[FormSection] = []
    field_meta: Dict[str, Dict] = {}

    report_id = form_schema.get("report_id")
    for table in form_schema.get("tables", []):
        table_id = str(table.get("tableId", table.get("tableName", "")))
        table_name = table.get("tableName", "")
        fields: List[FormField] = []
        for fld in table.get("fields", []):
            if not fld.get("fieldName"):
                continue
            ff, meta = field_from_openquire(fld, table_id, table_name)
            fields.append(ff)
            field_meta[ff.id] = meta

        sections.append(
            FormSection(id=table_id, title=table_name, fields=fields, metadata={"tableId": table_id})
        )

    schema = UniversalFormSchema(
        form_id=report_id or "report",
        domain=form_schema.get("domain") or domain,
        sections=sections,
    )
    return schema, field_meta


def from_universal_schema(form_schema: Dict[str, Any]) -> Tuple[UniversalFormSchema, Dict[str, Dict]]:
    field_meta: Dict[str, Dict] = {}
    sections: List[FormSection] = []
    for sec in form_schema.get("sections", []):
        fields: List[FormField] = []
        for fld in sec.get("fields", []):
            ff = field_from_dict(fld)
            fields.append(ff)
            # Preserve the original id→text mapping for the resolver.
            # `ff.metadata` holds {"options_dict", "options_map", …} thanks to
            # `field_from_dict`. We copy those here so that downstream code
            # (MappingHandler.build_results → resolve_option_id) can always turn
            # an LLM value into the correct `option_id`.
            if ff.options:
                field_meta[ff.id] = {
                    "options": ff.metadata.get("options_dict", {}),
                    "options_map": ff.metadata.get("options_map", {}),
                    "options_map_exact": ff.metadata.get("options_map_exact", {}),
                    "description": ff.metadata.get("description", ""),
                }
        sections.append(
            FormSection(
                id=str(sec.get("id") or sec.get("title") or "section"),
                title=sec.get("title") or sec.get("id") or "Section",
                fields=fields,
                metadata=sec.get("metadata"),
            )
        )

    schema = UniversalFormSchema(
        form_id=form_schema.get("form_id") or form_schema.get("report_id") or "report",
        domain=form_schema.get("domain"),
        sections=sections,
    )
    return schema, field_meta


def field_from_openquire(fld: Dict[str, Any], table_id: str, table_name: str) -> Tuple[FormField, Dict]:
    options = fld.get("options") or {}
    is_dropdown = bool(options)
    field_id = str(fld.get("rowId") or fld.get("fieldName"))
    label = fld.get("fieldName", "")

    options_list = list(options.values()) if options else None

    options_map = {
        normalize_token(v): k for k, v in options.items() if v is not None
    }
    options_map_exact = {str(v).strip().lower(): k for k, v in options.items()}

    ff = FormField(
        id=field_id,
        type="dropdown" if is_dropdown else infer_type(fld),
        label=label,
        required=fld.get("value") is not None,
        options=options_list,
        metadata={
            "tableName": table_name,
            "tableId": table_id,
            "original": fld,
            "options_map": options_map,
            "options_map_exact": options_map_exact,
        },
    )
    meta = {
        "table_id": table_id,
        "table_name": table_name,
        "original": fld,
        "options": options,
        "options_map": options_map,
        "options_map_exact": options_map_exact,
    }
    return ff, meta


def infer_type(fld: Dict[str, Any]) -> str:
    options = fld.get("options")
    if isinstance(options, dict) and len(options) > 1:
        return "multi_select"
    return "text"


def _extract_options(
    raw_options: Any,
) -> Tuple[Dict[str, str], Optional[List[str]], Dict[str, str], Dict[str, str]]:
    """Return ``(options_dict, options_list, options_map, options_map_exact)``.

    ``options_dict``  – a deterministic ``option_id -> option text`` mapping.
                       When the source schema supplies only a list of option texts,
                       synthetic integer IDs are generated so downstream code
                       (``resolve_option_id``) always receives a dict, never a list.

    ``options_list``  – the ordered list of option texts used for display / UI.

    ``options_map``   – ``normalize_token(text) -> option_id`` (fuzzy / token lookup).

    ``options_map_exact`` – ``text.strip().lower() -> option_id`` (exact lookup).
    """
    if isinstance(raw_options, dict):
        options_dict = {str(k): str(v) for k, v in raw_options.items() if v is not None}
    elif isinstance(raw_options, list):
        options_dict = {str(i): str(v) for i, v in enumerate(raw_options) if v is not None}
    else:
        options_dict = {}

    options_list = list(options_dict.values()) if options_dict else None
    options_map = {normalize_token(v): k for k, v in options_dict.items()}
    options_map_exact = {str(v).strip().lower(): k for k, v in options_dict.items()}
    return options_dict, options_list, options_map, options_map_exact


def field_from_dict(fld: Dict[str, Any]) -> FormField:
    """Convert a single field dict into a :class:`FormField`.

    Works for both OpenQuire-style fields (options as ``{id: text}``) and
    universal/UI schemas (options as a list of strings). In both cases we **keep**
    a deterministic ``option_id -> text`` mapping so that
    :func:`resolve_option_id` can always turn an LLM value into the correct
    ``option_id``.
    """
    raw_options = fld.get("options")
    options_dict, options_list, options_map, options_map_exact = _extract_options(
        raw_options
    )

    if options_dict:
        ftype = "multi_select" if len(options_dict) > 1 else "dropdown"
    else:
        ftype = fld.get("type", "text")

    # Some schemas carry a per‑field description / help text.  We store it so the
    # LLM prompt can include it without touching the FormField public shape.
    description = (
        fld.get("description")
        or fld.get("help_text")
        or fld.get("hint")
        or ""
    )

    return FormField(
        id=str(fld.get("id") or fld.get("fieldName", fld.get("label", "field"))),
        type=ftype,
        label=fld.get("label") or fld.get("fieldName", ""),
        required=bool(fld.get("required", False)),
        options=options_list,
        metadata={
            "original": fld,
            "description": description,
            "options_dict": options_dict,
            "options_map": options_map,
            "options_map_exact": options_map_exact,
        },
    )


def resolve_option_id(field_meta: Dict, value) -> Tuple[Any, str]:
    """Resolve a textual ``value`` to its ``option_id``.

    ``field_meta`` is expected to contain:
        * ``options``               – {option_id: text}  (dict)
        * ``options_map``           – {normalized text: option_id} (fuzzy)
        * ``options_map_exact``     – {lower‑cased text: option_id} (exact)

    If a caller accidentally passed ``options`` as a *list*, the list is
    normalised into a synthetic id→text dict so the helper never crashes and
    always returns a deterministic id.
    """
    options = field_meta.get("options") or {}
    if not options:
        return value, None
    if value is None:
        return None, None

    # Defensive normalisation – make sure `options` is always a dict.
    if isinstance(options, list):
        options, _, _, _ = _extract_options(options)
        field_meta = dict(field_meta)
        field_meta["options"] = options

    value_norm = normalize_token(str(value))
    value_exact = str(value).strip().lower()

    options_map = field_meta.get("options_map_exact", {})
    option_id = options_map.get(value_exact)
    if option_id is None:
        option_id = field_meta.get("options_map", {}).get(value_norm)
    if option_id is None:
        best_id, best_overlap = None, 0
        for opt_id, opt_text in options.items():
            overlap = len(
                set(value_norm.split()) & set(normalize_token(opt_text).split())
            )
            if overlap > best_overlap:
                best_id, best_overlap = opt_id, overlap
        option_id = best_id

    resolved_value = options[option_id] if option_id else value
    return resolved_value, option_id