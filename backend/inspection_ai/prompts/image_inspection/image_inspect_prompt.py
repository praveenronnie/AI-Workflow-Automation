

def visual_updated_prompt():
    return """

You are an expert Commercial Property Condition Assessment (PCA) image analyst.

Analyze 10 images only the visible information
Extract visible building elements, systems, equipment, materials, conditions, deficiencies, and readable metadata as structured observations.
The goal is to produce visible evidence observations only, not PCA conclusions.

For each image extract:

- building_area:
Identify from this list ( roof, exterior, foundation, garage, kitchen, bathroom, bedroom, living_room, basement, attic, hvac, electrical, plumbing, hallway, staircase, laundry, utility_room, unknown)

- view:
Describe the image viewpoint. (e.g. "wide angle", "close-up", "overhead", "corner")

- domain:
Assign the most relevant high-level building domain.

- visual_object:
Identify only the visible physical object, assembly, equipment, or building element.
Use a specific name when clearly identifiable.
Otherwise use a generic visible name.

- location:
Describe the visible location of the object.

- description:
A one sentence description of the domain and object. 

- materials:
visible construction/finish/roofing materials (up to 10). 
Include the most specific visible material type possible. 
Do not use generic classifications when a more specific classification can be identified.

Examples only:

* painted stucco finish
* fiber cement panel siding
* standing seam metal roofing
* TPO roofing membrane
* galvanized steel flashing
Do not add hidden specifications or unsupported details.
format: {"material":"<specific_material>", "condition":"<condition>"}


- overall_condition:
Provide the visible condition of the observed object. (e.g. "excellent", "good", "good-fair" "fair", "poor")

- findings:
Extract only visible damage or deficiencies associated with the object. Include type, location, severity, extent, and notes.
Do not infer hidden damage or potential issues.
(e.g. water_damage/structural/mold/cracks/peeling_paint/missing_material/rust/rot/electrical_hazard/pest_damage/none

- properties:
Extract readable key-value information from nameplates, labels, tags, stickers, panels, meters, markings, and equipment identification associated with the object.

- confidence:
Provide confidence for the observation.

Assign each observation to only one domain.
Domains:
- Site: Extract exterior site features and ground-level property improvements.
- Structural System: Extract visible load-bearing structural elements only.
- Building Envelope: Extract exterior building enclosure components only.
- Roofing System: Extract roof assembly components and roof-mounted elements attached to the roof.
- Interior: Extract interior spaces, finishes, fixtures, and architectural components.
- Mechanical Systems: Extract HVAC and mechanical equipment, piping, ductwork, and associated components.
- Electrical Systems: Extract electrical distribution equipment, wiring, lighting, and electrical components.
- Plumbing Systems: Extract water supply, drainage, plumbing equipment, fixtures, and piping.
- Fire & Life Safety: Extract fire protection, emergency, and life safety equipment.
- Vertical Transportation: Extract elevator, lift, escalator, and transportation system components.
- Accessibility: Extract accessibility-related building features and equipment.
- Site Utilities: Extract exterior utility service infrastructure and utility equipment.
- Environmental Conditions: Extract visible environmental conditions such as climate, water quality, or soil chemistry
- Security Systems: Extract security, surveillance, and access control equipment.

Caption: One sentence suitable for semantic search indexing

Mini caption:
 A highly succinct summary of maximum 6 words. It MUST contain the location (e.g., interior/exterior/room/building_area) and damage status (e.g., 'damaged' with type of damage, or 'undamaged'). Example: "Exterior facade: undamaged" or "Interior kitchen: water damaged".


RULES:
- Analyse 10 images and produce output for 10 images
- Use only visible information.
- Do not infer hidden, concealed, or uncertain details.
- Combine observations describing the same visible object into a single observation.
- Do not invent values or guess missing information.
- Do not create duplicate observations.
- Associate readable metadata with the corresponding visible object instead of creating separate observations.
- Return only valid JSON.
- No markdown fences

OUTPUT:
{
    "results": [{
        "building_area": "",
        "view": "",
        "caption": "",
        "mini_caption": "",
        "domains": [
            {
                "domain": "",
                "observations": [
                    {
                        "visual_object": "",
                        "location": "",
                        "description": "",
                        "materials": [
                            {
                                "material": "",
                                "condition": ""
                            },
                        ],
                        "overall_condition": "",
                        "findings": [],
                        "properties": {},
                        "confidence": 0.0
                    }
                ]
            }
        ]
    }]
}

"""


def handwritten_pdf_extraction_prompt():
    return """

You are an expert Commercial Property Condition Assessment (PCA) document analyst.

Analyze the PDF page image.

Extract only information that has been handwritten, selected, checked, filled, or answered.

Ignore blank fields, printed template text, unanswered questions, crossed-out responses, overwritten or cancelled answers, and information that cannot be read confidently.

Organize the extracted information into:

Property Information:
Property details including property identifiers, address, location, parcel information, ownership, jurisdictions, site contacts, land information, occupancy information, and general property details.

Building Information:
General building characteristics including building type, construction, year built, size, square footage, floors, occupancy, style, parking, and other building-level information.
Group related information into nested objects where appropriate.

Building Systems:
Store building system information under the appropriate domain.
Group related information together within the same domain.
Associate manufacturer names, equipment details, utility providers, specifications, capacities, warranties, maintenance information, and other system-related details with the corresponding system.

Domains:
- Structural System: Structural components, framing, foundations, and structural construction information.
- Roofing System: Roof construction, roof coverings, roof materials, roof condition, warranties, and roof-related information.
- Building Envelope: Exterior walls, windows, doors, facade, exterior finishes, insulation, and enclosure information.
- Interior: Interior spaces, finishes, ceilings, walls, floors, partitions, and interior building information.
- Mechanical Systems: HVAC, heating, cooling, ventilation, mechanical equipment, and related information.
- Electrical Systems: Electrical service, distribution, panels, lighting, electrical equipment, and related information.
- Plumbing Systems: Water supply, sanitary systems, plumbing fixtures, piping, water heaters, and related information.
- Fire & Life Safety: Fire protection, alarms, sprinklers, extinguishers, emergency systems, and life safety information.
- Vertical Transportation: Elevators, lifts, escalators, and related transportation systems.
- Accessibility: Accessibility features and accessibility-related information.
- Site Utilities: Utility providers, utility services, utility connections, and site utility information.
- Security Systems: Security, surveillance, access control, and security-related systems.
- Environmental Conditions: Environmental observations, hazardous materials, contamination, moisture, and environmental information.

Financial / Regulatory Information:
Financial, tax, assessment, valuation, permit, inspection, jurisdiction, and regulatory information.

Documents Metadata:
Document-level information including title, type, page information, dates, revision information, source, and other document metadata.

OUTPUT:

{
    "property_information": {},
    "building_information": {},
    "building_systems": [
        {
            "domain": "",
            "information": {}
        }
    ],
    "financial_regulatory_information": {},
    "documents_metadata": {}
}

Return only valid JSON.

"""


def pdf_evidence_extraction_prompt(chunks):
    chunks_text = "\n\n---CHUNK SEPARATOR---\n\n".join(
        f"[CHUNK_ID: {c['chunk_id']}]\n[PAGE: {c['page_no']}]\n{c['content']}"
        for c in chunks
    )

    return f"""
You are a property document evidence extraction engine.

DOCUMENT_TYPE: property inspection report (PCA/ESA/tax records)

DOCUMENT CHUNKS:
{chunks_text}

TASK:
Extract ALL visible evidence related to building/site inspection from EACH chunk.
Process each chunk independently. Do not mix evidence between chunks.
Focus on: property details, building characteristics, systems, materials,
conditions, measurements, contacts, financial data, regulatory info.

EXCLUDE (filter these out):
- Legal disclaimers and liability statements
- Generic instructions or form templates
- Empty fields (underscores, blank lines)
- Page numbers, headers, footers
- Confidentiality notices
- Signature blocks without content

EXTRACTION RULES:
1. Extract EVERY data point that describes the property, building, or site
2. Preserve exact text for names, numbers, dates, serial numbers
3. Include units when visible (SF, tons, volts, gallons, etc.)
4. Confidence: 0.9-1.0 for explicit text, 0.7-0.89 for clear context, 0.5-0.69 inferred
5. Do not invent values - use null
6. Keep raw_text as exact substring from chunk

OUTPUT FORMAT:
{{
    "batch_results": [
        {{
            "chunk_id": "chunk_0",
            "page": 1,
            "evidence": [
                {{
                    "evidence_id": "evt_1",
                    "field_name": "owner_name",
                    "value": "HOUSTON INFILL INDUSTRIAL INVESTORS II LLC",
                    "unit": null,
                    "confidence": 0.95,
                    "raw_text": "Owner: HOUSTON INFILL INDUSTRIAL INVESTORS II LLC",
                    "evidence_type": "textual"
                }}
            ]
        }}
    ]
}}

Return ONLY valid JSON.
"""


def intent_detection_prompt(section_id, section_name, fields) -> str:

    return f"""
        You are an intent detector for property-inspection report forms.
        Convert the form section below into ONE concise search intent and 3-4
        semantic search queries that will retrieve the matching extracted evidence.

        SECTION ID: {section_id}
        SECTION NAME: {section_name}
        FIELDS: 
        {fields}

        Guidelines:
        - "intent": one short phrase (12 words or fewer) naming the section topic,
        e.g. "property ownership and sale" or "roofing materials and condition".
        - "semantic_queries": 3-4 diverse, SELF-CONTAINED phrases for vector search.
        Use plain, real-world vocabulary (include synonyms/variants) so they match
        the extracted text; mention concrete attributes or units when useful. Do NOT
        use field ids, internal codes, or abbreviations.
        - Spread the queries across the different sub-topics the fields hint at, and
        keep each query short (5-12 words).
        - Return ONLY valid JSON, no markdown, no extra explanation:
        {{"intent": "...", "semantic_queries": ["query1", "query2", "query3"]}}
        """
