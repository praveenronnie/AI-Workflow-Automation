from datetime import datetime
from typing import Any, Dict, List, Optional


def tag_ocr_data(data: Dict[str, Any]) -> Dict[str, Any]:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = tag_ocr_data(value)
        elif isinstance(value, list):
            result[key] = [
                (
                    tag_ocr_data(item)
                    if isinstance(item, dict)
                    else {"value": item, "source": "ocr", "page_number": "Notavailable"}
                )
                for item in value
            ]
        else:
            result[key] = {
                "value": value,
                "source": "ocr",
                "page_number": "Notavailable",
            }
    return result


def tag_pca_data(data: Dict[str, Any], page_number: str) -> Dict[str, Any]:
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            if "value" in value and "source" in value:
                result[key] = value
            else:
                result[key] = tag_pca_data(value, page_number)
        elif isinstance(value, list):
            result[key] = [
                (
                    tag_pca_data(item, page_number)
                    if isinstance(item, dict)
                    else {"value": item, "source": "pca", "page_number": page_number}
                )
                for item in value
            ]
        else:
            result[key] = {"value": value, "source": "pca", "page_number": page_number}
    return result


def merge_tagged(target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in source.items():
        if (
            key in target
            and isinstance(target[key], dict)
            and isinstance(value, dict)
            and "value" not in target[key]
        ):
            merge_tagged(target[key], value)
        else:
            target[key] = value
    return target


def merge_tagged_records(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = {}
    for record in records:
        merge_tagged(result, record)
    return result


def aggregate_building_systems(
    systems_list: List[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    domains = {}
    for systems in systems_list:
        for system in systems:
            domain_raw = system.get("domain", "Unknown")
            if isinstance(domain_raw, dict) and "value" in domain_raw:
                domain_name = domain_raw["value"]
            else:
                domain_name = domain_raw
            if domain_name not in domains:
                domains[domain_name] = {"domain": domain_name, "information": {}}
            information = system.get("information", {})
            if isinstance(information, dict):
                merge_tagged(domains[domain_name]["information"], information)
    return list(domains.values())


def aggregate_pdf_data(
    ocr_responses: Optional[List[Dict[str, Any]]] = None,
    pca_responses: Optional[List[Dict[str, Any]]] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    records = []
    sources = []

    if existing:
        records.append(
            {
                "property_information": existing.get("property_information", {}),
                "building_information": existing.get("building_information", {}),
                "building_systems": existing.get("building_systems", []),
                "financial_regulatory_information": existing.get(
                    "financial_regulatory_information", {}
                ),
                "documents_metadata": existing.get("document_metadata", {}),
            }
        )
        sources = existing.get("source_metadata", {}).get("sources", [])

    for response in ocr_responses or []:
        records.append(tag_ocr_data(response))
        sources.append("ocr")

    for page in pca_responses or []:
        page_number = f"page-{page['image_id']}"
        records.append(tag_pca_data(page["image_data"], page_number))
        sources.append(page_number)

    return {
        "source_metadata": {
            "sources": sources,
            "aggregation_timestamp": datetime.now().isoformat(),
        },
        "property_information": merge_tagged_records(
            [r.get("property_information", {}) for r in records]
        ),
        "building_information": merge_tagged_records(
            [r.get("building_information", {}) for r in records]
        ),
        "building_systems": aggregate_building_systems(
            [r.get("building_systems", []) for r in records]
        ),
        "financial_regulatory_information": merge_tagged_records(
            [r.get("financial_regulatory_information", {}) for r in records]
        ),
        "document_metadata": merge_tagged_records(
            [r.get("documents_metadata", {}) for r in records]
        ),
    }
