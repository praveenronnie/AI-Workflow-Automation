"""
Mapping Service - Maps extracted values to Quire fields using aliases.
Supports field name variations across different projects.
"""

from typing import Optional

from inspection_ai.models.dto import FieldDTO


class MappingService:
    FIELD_ALIASES = {
        "owner_name": ["owner", "property_owner", "client_name", "name"],
        "address": ["property_address", "location", "site_address"],
        "roof_type": ["roof", "roofing", "roof_material"],
        "wall_type": ["wall", "walls", "wall_material"],
        "building_condition": ["condition", "building_status", "overall_condition"],
        "damage": ["damage_type", "damage_description", "issues"],
    }

    def __init__(self, project_manager):
        self.project_manager = project_manager

    def map_fields(
        self, extracted_data: dict, quire_fields: list, user_approved: bool = False
    ) -> dict:
        if not user_approved:
            return {
                "field_mappings": [],
                "unmapped_fields": [],
                "confidence_score": 0.0,
                "evidence": "Awaiting user approval",
            }

        mappings = []
        unmapped = []

        for field in quire_fields:
            field_name = field.get("name", "")
            canonical = self._find_canonical_name(field_name)

            if canonical and canonical in extracted_data:
                value = extracted_data[canonical]
                mapping = FieldDTO(
                    canonical_name=canonical,
                    aliases=self.FIELD_ALIASES.get(canonical, []),
                    value=value,
                    confidence_score=0.9,
                    evidence=f"Mapped from {field_name}",
                )
                mappings.append(mapping.to_dict())
            else:
                unmapped.append(field_name)

        return {
            "field_mappings": mappings,
            "unmapped_fields": unmapped,
            "confidence_score": 0.9,
            "evidence": f"Mapped {len(mappings)} fields",
        }

    def _find_canonical_name(self, field_name: str) -> Optional[str]:
        field_lower = field_name.lower().replace(" ", "_").replace("-", "_")

        for canonical, aliases in self.FIELD_ALIASES.items():
            if field_lower == canonical or field_lower in [a.lower() for a in aliases]:
                return canonical

        return None

    def get_aliases(self, canonical_name: str) -> list:
        return self.FIELD_ALIASES.get(canonical_name, [])
