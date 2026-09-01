from inspection_ai.ai.providers.llm_client import LLMClient
import logging


logger = logging.getLogger(__name__)


async def detect_section_intent(section_id, section_name, fields, llm_client=None):
    if llm_client is None:
        llm_client = LLMClient()

    field_names = [f.label for f in fields if f]
    field_list = "\n".join(f"- {name}" for name in field_names)

    prompt = f"""Analyze this form section and fields to determine data retrieval strategy.

SECTION_ID: {section_id}
SECTION: {section_name}

FIELDS:
{field_list}

DATA SOURCES AVAILABLE:
- ocr_extracted: Raw OCR text from PDF documents
- pca_aggregated: Structured PCA inspection data with building systems (property_information, building_information, building_systems with domains like Site Utilities, Roofing System, Electrical Systems, etc.)
- image_aggregated: Image-based findings organized by building_area (exterior, roof, hvac, kitchen, utility_room, interior) and domain (Building Envelope, Roofing System, Mechanical Systems, etc.)

Return JSON with:
{{
    "section_id":{section_id}
    "section_intent": "brief description of what this section captures",
    "required_sources": ["ocr", "pca", "image"],
    "building_areas": ["exterior", "roof", "hvac", "kitchen", "utility_room", "interior"],
    "domains": ["Building Envelope", "Roofing System", "Mechanical Systems", "Site", "Structural System", "Electrical Systems", "Plumbing Systems", "Fire & Life Safety"],
    "semantic_queries": ["query 1", "query 2"]
}}

RULES:
- No markdown fences
- Include only relevant building_areas for this section
- Include only relevant domains for this section
- semantic_queries should be specific search queries to find relevant data
- For property/building info fields, include "ocr"
- For systems/condition fields, include "pca" and "image"
- For site/exterior fields, include "image" with building_area "exterior"
"""

    try:
        response = await llm_client.process_llm_request_async(content=prompt)
        if response:
            return response
    except Exception as e:
        logger.error(f"Intent detection failed: {e}")

    return {
        "section_intent": f"Data for {section_name}",
        "required_sources": ["ocr", "pca", "image"],
        "building_areas": ["exterior", "interior"],
        "domains": [],
        "semantic_queries": [section_name],
    }
