"""
Field Transformer - Transforms extracted data from PDFs and images into a flat dictionary.
"""

from typing import Dict, Any, List


def transform_extracted_data(
    pdf_results: dict,
    image_results: list,
) -> Dict[str, Any]:
    extracted = {}

    handwritten = pdf_results.get("handwritten", {})
    if handwritten and "fields" in handwritten:
        for field in handwritten.get("fields", []):
            extracted.update(_extract_field_values(field))

    scanned = pdf_results.get("scanned", {})
    if scanned and "fields" in scanned:
        for field in scanned.get("fields", []):
            extracted.update(_extract_field_values(field))

    for img_result in image_results:
        extracted.update(_extract_image_values(img_result))

    return extracted


def _extract_field_values(field: dict) -> Dict[str, Any]:
    result = {}

    if "owner_name" in field:
        result["owner_name"] = field["owner_name"]
    if "property_address" in field:
        result["address"] = field["property_address"]
    if "inspection_date" in field:
        result["inspection_date"] = field["inspection_date"]
    if "inspector_name" in field:
        result["inspector_name"] = field["inspector_name"]

    return result


def _extract_image_values(img_result: dict) -> Dict[str, Any]:
    result = {}

    if "room" in img_result:
        result["room"] = img_result["room"]
    if "category" in img_result:
        result["category"] = img_result["category"]
    if "view" in img_result:
        result["view"] = img_result["view"]
    if "materials" in img_result:
        result["materials"] = img_result["materials"]
    if "systems" in img_result:
        result["systems"] = img_result["systems"]
    if "objects" in img_result:
        result["objects"] = img_result["objects"]
    if "visible_damage" in img_result:
        result["damage"] = img_result["visible_damage"]
    if "overall_condition" in img_result:
        result["building_condition"] = img_result["overall_condition"]
    if "caption" in img_result:
        result["caption"] = img_result["caption"]
    if "mini_caption" in img_result:
        result["mini_caption"] = img_result["mini_caption"]
    if "notes" in img_result:
        result["notes"] = img_result["notes"]

    return result


def get_quire_fields_from_extraction(extraction_result: dict) -> List[dict]:
    return extraction_result.get("all_fields_flat", [])
