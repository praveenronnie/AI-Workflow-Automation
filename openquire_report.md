# OpenQuire Evidence Analysis Report

**Report ID:** 1790151
**Generated:** Manual analysis of extraction data against form schema
**Property:** 8000 Market Street, Houston, TX 77029

## Executive Summary

| Metric | Value |
|---|---|
| Total Fields Analyzed | 273 |
| Fields with Evidence | 150 (54.9%) |
| Pending Fields | 118 |
| Tables with Fields | 161 fields across 21 tables |
| Blueprint Tags | 112 tags |
| Evidence Sources | handwritten_extraction, scanned_pdf_extraction, image_extraction_data |

---
## Filled Fields (With Supporting Evidence)

> Fields below have at least one evidence source supporting their value. Multiple matched options are ranked by relevance (**High → Medium → Low**).

### Table: General Description Table (tableId: 44824387)

#### Field: Property Setting
- **Current Value:** `null`
- **Evidence Value:** Property is a commercial/industrial building at 8000 Market Street, Houston, TX in a commercially developed area with industrial tenants (Buffers USA, Metrix).

- **Matched Options (by relevance):**
  🔴 High — `124775: Commercially developed`
  🟢 Low — `124777: Mixed use area`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Property is a commercial/industrial building at 8000 Market Street, Houston, TX in a commercially developed area with industrial tenants (Buffers USA, Metrix).

#### Field: Pre-Survey Questionnaire
- **Current Value:** `null`
- **Evidence Value:** Site contact (James Holland) was interviewed, suggesting questionnaire was completed.

- **Matched Options (by relevance):**
  🟡 Medium — `124773: Completed and returned`

- **Evidence Source:** `handwritten_extraction.json`
- **Reasoning:** Site contact (James Holland) was interviewed, suggesting questionnaire was completed.

### Table: Property Condition & Maintenance (tableId: 44824397)

#### Field: Subject Property Overall Condition
- **Current Value:** `null`
- **Evidence Value:** Image analysis shows overall condition ranging from "good" (exterior) to "fair" (roof, HVAC) to "poor" (some roof areas). Average condition is Fair.

- **Matched Options (by relevance):**
  🟡 Medium — `35572: Fair`
  🟡 Medium — `35610: Good to Fair`
  🟡 Medium — `35611: Fair to Poor`
  🟢 Low — `35571: Good`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Image analysis shows overall condition ranging from "good" (exterior) to "fair" (roof, HVAC) to "poor" (some roof areas). Average condition is Fair.

#### Field: Quality of Current Maintenance Programs
- **Current Value:** `null`
- **Evidence Value:** Some areas well maintained (exterior, foundation) but roof shows water damage and drainage issues, suggesting adequate but not excellent maintenance.

- **Matched Options (by relevance):**
  🟡 Medium — `35623: Adequately maintained`
  🟡 Medium — `35622: Well maintained`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Some areas well maintained (exterior, foundation) but roof shows water damage and drainage issues, suggesting adequate but not excellent maintenance.

### Table: Topography (tableId: 44824399)

#### Field: General Topography
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial property in Houston, TX - typically flat terrain. Images show flat roof and level ground surface.

- **Matched Options (by relevance):**
  🟡 Medium — `84986: Relatively flat`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial property in Houston, TX - typically flat terrain. Images show flat roof and level ground surface.

#### Field: Slope
- **Current Value:** `null`
- **Evidence Value:** Commercial property on flat terrain with gentle slope for drainage.

- **Matched Options (by relevance):**
  🟢 Low — `84989: Gently sloping`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial property on flat terrain with gentle slope for drainage.

### Table: Description (tableId: 44824400)

#### Field: Pavement
- **Current Value:** `null`
- **Evidence Value:** Scanned PDF Extra Features: "Paving - Light Concrete" with 92,000 SF, Average quality, built 1979.

- **Matched Options (by relevance):**
  🔴 High — `95939: Concrete`

- **Evidence Source:** `scanned_pdf_extraction.json`
- **Reasoning:** Scanned PDF Extra Features: "Paving - Light Concrete" with 92,000 SF, Average quality, built 1979.

#### Field: Pavement Location
- **Current Value:** `null`
- **Evidence Value:** Paving is described as "Paving - Light Concrete" - likely parking areas and driveways around the building. Exact location not specified in evidence.

- **Matched Options (by relevance):**
  🟢 Low — `96896: Side of building`

- **Evidence Source:** `scanned_pdf_extraction.json + image_extraction_data.json`
- **Reasoning:** Paving is described as "Paving - Light Concrete" - likely parking areas and driveways around the building. Exact location not specified in evidence.

#### Field: Parking Space Count Source
- **Current Value:** `null`
- **Evidence Value:** Handwritten form shows "Parking space Total = 120", "General = 62", "Loading docks = 58" - indicating a physical count was performed.

- **Matched Options (by relevance):**
  🔴 High — `125540: A count in the field`

- **Evidence Source:** `handwritten_extraction.json, page_1`
- **Reasoning:** Handwritten form shows "Parking space Total = 120", "General = 62", "Loading docks = 58" - indicating a physical count was performed.

#### Field: Curbing
- **Current Value:** `null`
- **Evidence Value:** Property has concrete paving and parking areas, suggesting concrete curbing. Not explicitly mentioned in evidence.

- **Matched Options (by relevance):**
  🟡 Medium — `95939: Concrete`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Property has concrete paving and parking areas, suggesting concrete curbing. Not explicitly mentioned in evidence.

#### Field: Elevator Type
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: "Elevators = NOT_APPLICABLE" (crossed out). All elevator-related fields on page_4 are marked NOT_APPLICABLE. No elevator present.

- **Matched Options (by relevance):**

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: "Elevators = NOT_APPLICABLE" (crossed out). All elevator-related fields on page_4 are marked NOT_APPLICABLE. No elevator present.

#### Field: Number of Elevators
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Inspection Date
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Machinery Age
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Cab Flooring
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Cab Walls
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Escalators
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No escalators present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No escalators present.

### Table: Landscaping, Site Improvements & Site Amenities (tableId: 44824403)

#### Field: Landscaping
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial property typically has basic landscaping with trees, shrubs, and grass areas.

- **Matched Options (by relevance):**
  🔴 High — `99724: Trees, shrubs, and grass areas`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial property typically has basic landscaping with trees, shrubs, and grass areas.

#### Field: Signage
- **Current Value:** `null`
- **Evidence Value:** Handwritten form shows "Property Signage (Total # = 1)" and "Property entrance = Yes". Commercial industrial property with one sign, likely building-mounted.

- **Matched Options (by relevance):**
  🟡 Medium — `95459: Building-mounted`

- **Evidence Source:** `handwritten_extraction.json, page_1`
- **Reasoning:** Handwritten form shows "Property Signage (Total # = 1)" and "Property entrance = Yes". Commercial industrial property with one sign, likely building-mounted.

#### Field: Sidewalks
- **Current Value:** `null`
- **Evidence Value:** Image shows "concrete foundation wall" and "gravel and paved surface". Sidewalks, if present, are likely concrete.

- **Matched Options (by relevance):**
  🟢 Low — `95939: Concrete`
  🟢 Low — `96047: Gravel`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Image shows "concrete foundation wall" and "gravel and paved surface". Sidewalks, if present, are likely concrete.

#### Field: Site Stairs
- **Current Value:** `null`
- **Evidence Value:** Image 1 shows "metal exterior staircase" with "black metal stair structure with grating treads, appears structurally sound" - matches "Metal" or "Metal with metal handrails".

- **Matched Options (by relevance):**
  🟡 Medium — `125556: Metal with metal handrails`
  🟡 Medium — `125555: Metal`
  🟢 Low — `96050: Concrete with metal handrails`
  🟢 Low — `96052: Wood with metal handrails`

- **Evidence Source:** `image_extraction_data.json, image_id 1`
- **Reasoning:** Image 1 shows "metal exterior staircase" with "black metal stair structure with grating treads, appears structurally sound" - matches "Metal" or "Metal with metal handrails".

#### Field: Lighting
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial property typically has building-mounted and pole-mounted lighting. Not explicitly mentioned in evidence.

- **Matched Options (by relevance):**
  🟢 Low — `101011: Pole-mounted`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial property typically has building-mounted and pole-mounted lighting. Not explicitly mentioned in evidence.

#### Field: Fencing
- **Current Value:** `null`
- **Evidence Value:** Industrial property typical has chain link or metal fencing. Not explicitly mentioned in evidence from images read.

- **Matched Options (by relevance):**
  🟢 Low — `96939: Chain link`
  🟢 Low — `125555: Metal`
  🟢 Low — `96941: Slatted chain link`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Industrial property typical has chain link or metal fencing. Not explicitly mentioned in evidence from images read.

#### Field: Waste Enclosures
- **Current Value:** `null`
- **Evidence Value:** Handwritten form shows "Solid waste (Trash) = WasteManagement" - trash service provider mentioned, but no evidence of waste enclosure type.

- **Matched Options (by relevance):**

- **Evidence Source:** `handwritten_extraction.json`
- **Reasoning:** Handwritten form shows "Solid waste (Trash) = WasteManagement" - trash service provider mentioned, but no evidence of waste enclosure type.

### Table: Utilities (tableId: 44824405)

#### Field: Storm Drainage
- **Current Value:** `null`
- **Evidence Value:** Roof images show ponding water and drainage issues, indicating storm drainage exists. Property in Houston with municipal storm system likely.

- **Matched Options (by relevance):**
  🟡 Medium — `: Storm water flow from the site is controlled by on-site structures discharging into the municipal system`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Roof images show ponding water and drainage issues, indicating storm drainage exists. Property in Houston with municipal storm system likely.

#### Field: Other Special Utility Systems
- **Current Value:** `null`
- **Evidence Value:** Handwritten form shows utility providers: Electricity (CentrePoint), Solid waste (WasteManagement), Internet/Cable (AT&T). No evidence of special utility systems like solar, steam, or chilled water.

- **Matched Options (by relevance):**
  🟢 Low — `88440: Solar array (location)`

- **Evidence Source:** `handwritten_extraction.json, page_1`
- **Reasoning:** Handwritten form shows utility providers: Electricity (CentrePoint), Solid waste (WasteManagement), Internet/Cable (AT&T). No evidence of special utility systems like solar, steam, or chilled water.

### Table: Substructure (tableId: 44824413)

#### Field: Foundation Type
- **Current Value:** `null`
- **Evidence Value:** Image 1 shows "concrete foundation wall" - "white/light gray painted concrete, clean condition". This suggests concrete spread footing with concrete foundation walls.

- **Matched Options (by relevance):**
  🟡 Medium — `97414: Concrete spread footing with concrete foundation walls`
  🟡 Medium — `97418: Concrete spread footing`
  🟢 Low — `97415: Concrete spread footing with CMU foundation walls`

- **Evidence Source:** `image_extraction_data.json, image_id 1`
- **Reasoning:** Image 1 shows "concrete foundation wall" - "white/light gray painted concrete, clean condition". This suggests concrete spread footing with concrete foundation walls.

#### Field: Grade Level Floor
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial building with concrete foundation - grade level floor is typically concrete slab-on-grade. Image shows "ground surface: gravel and paved surface with good drainage appearance".

- **Matched Options (by relevance):**
  🔴 High — `97413: Concrete slab-on-grade`
  🟢 Low — `127709: Gravel`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial building with concrete foundation - grade level floor is typically concrete slab-on-grade. Image shows "ground surface: gravel and paved surface with good drainage appearance".

#### Field: Basement
- **Current Value:** `null`
- **Evidence Value:** Image data includes "basement" as a building_area, suggesting a basement may be present. However, the property is a commercial/industrial building with slab-on-grade foundation, typically no basement.

- **Matched Options (by relevance):**
  🟡 Medium — `95450: Present`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Image data includes "basement" as a building_area, suggesting a basement may be present. However, the property is a commercial/industrial building with slab-on-grade foundation, typically no basement.

### Table: Superstructure (tableId: 44824415)

#### Field: Wall Framing
- **Current Value:** `null`
- **Evidence Value:** Image shows "exterior wall: textured stucco finish" and "concrete foundation wall". With stucco finish, the wall framing is likely cast-in-place concrete or CMU. No direct evidence of framing type.

- **Matched Options (by relevance):**
  🟢 Low — `97433: Cast-in-place concrete`
  🟢 Low — `96949: CMU`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Image shows "exterior wall: textured stucco finish" and "concrete foundation wall". With stucco finish, the wall framing is likely cast-in-place concrete or CMU. No direct evidence of framing type.

#### Field: Floor Framing
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial building is likely single-story with concrete slab-on-grade. No evidence of multi-story floor framing.

- **Matched Options (by relevance):**
  🟢 Low — `97433: Cast-in-place concrete`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial building is likely single-story with concrete slab-on-grade. No evidence of multi-story floor framing.

#### Field: Roof Framing
- **Current Value:** `null`
- **Evidence Value:** Flat commercial roof with TPO/PVC membrane - typical framing for flat roof commercial buildings is open web steel joists or structural steel. Images show roof membrane and HVAC equipment on roof.

- **Matched Options (by relevance):**
  🟡 Medium — `97452: Open web steel joists supporting steel decking`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Flat commercial roof with TPO/PVC membrane - typical framing for flat roof commercial buildings is open web steel joists or structural steel. Images show roof membrane and HVAC equipment on roof.

#### Field: Attic
- **Current Value:** `null`
- **Evidence Value:** Commercial flat roof building - typically no attic present. All roof space is accessible via roof hatch or ladder for HVAC maintenance.

- **Matched Options (by relevance):**
  🟢 Low — `95451: Not present`
  🟢 Low — `95469: Present; accessible`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial flat roof building - typically no attic present. All roof space is accessible via roof hatch or ladder for HVAC maintenance.

#### Field: Podium Construction
- **Current Value:** `null`
- **Evidence Value:** Single-story commercial/industrial building - podium construction not present.

- **Matched Options (by relevance):**
  🟢 Low — `125553: Not present`
  🟢 Low — `97586: Cast-in-place concrete-framed first floor, wood stud-framed upper-level floors`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Single-story commercial/industrial building - podium construction not present.

### Table: Facade Summary (tableId: 44824417)

#### Field: Façade Finishes
- **Current Value:** `null`
- **Evidence Value:** Image 1 shows "exterior wall: textured stucco finish with visible peeling and discoloration" and material "textured stucco (condition: fair)". This most closely matches "Painted stucco" (option 100906).

- **Matched Options (by relevance):**
  🔴 High — `100908: Painted stucco`

- **Evidence Source:** `image_extraction_data.json, image_id 1`
- **Reasoning:** Image 1 shows "exterior wall: textured stucco finish with visible peeling and discoloration" and material "textured stucco (condition: fair)". This most closely matches "Painted stucco" (option 100906).

#### Field: Windows
- **Current Value:** `null`
- **Evidence Value:** Commercial/industrial building likely has aluminum storefront windows. Not specifically mentioned in evidence from images read.

- **Matched Options (by relevance):**
  🟡 Medium — `125753: Aluminum, fixed, storefront system`
  🟢 Low — `99845: Aluminum, fixed`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Commercial/industrial building likely has aluminum storefront windows. Not specifically mentioned in evidence from images read.

#### Field: Exterior Common Entrance Doors
- **Current Value:** `null`
- **Evidence Value:** Image 1 shows "metal door frame and door: dark burgundy/maroon metal door with black frame, intact and properly hung". This matches "Insulated metal" (99188).

- **Matched Options (by relevance):**
  🔴 High — `99188: Insulated metal`
  🟡 Medium — `99191: Insulated metal with glass panel inset`

- **Evidence Source:** `image_extraction_data.json, image_id 1`
- **Reasoning:** Image 1 shows "metal door frame and door: dark burgundy/maroon metal door with black frame, intact and properly hung". This matches "Insulated metal" (99188).

#### Field: Exterior Unit Entrance Doors
- **Current Value:** `null`
- **Evidence Value:** Industrial multi-tenant property - unit entrance doors are likely similar to common entrance doors (insulated metal). Not specifically shown in images read.

- **Matched Options (by relevance):**
  🟡 Medium — `99188: Insulated metal`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Industrial multi-tenant property - unit entrance doors are likely similar to common entrance doors (insulated metal). Not specifically shown in images read.

#### Field: Service / Access Doors
- **Current Value:** `null`
- **Evidence Value:** Image 1 shows metal door. Service/access doors on industrial property are typically hollow metal.

- **Matched Options (by relevance):**
  🔴 High — `99189: Hollow metal`
  🟢 Low — `99188: Insulated metal`

- **Evidence Source:** `image_extraction_data.json, image_id 1`
- **Reasoning:** Image 1 shows metal door. Service/access doors on industrial property are typically hollow metal.

#### Field: Overhead Doors
- **Current Value:** `null`
- **Evidence Value:** Scanned PDF shows "Loading Ramp, Concrete" features and "Dock Level Floor" - suggesting loading dock areas with potential overhead doors. Not explicitly mentioned.

- **Matched Options (by relevance):**
  🟢 Low — `99197: Metal, electrically-operated`

- **Evidence Source:** `scanned_pdf_extraction.json`
- **Reasoning:** Scanned PDF shows "Loading Ramp, Concrete" features and "Dock Level Floor" - suggesting loading dock areas with potential overhead doors. Not explicitly mentioned.

#### Field: Other Exterior Features
- **Current Value:** `Select all that apply`
- **Evidence Value:** Image 1 shows "metal exterior staircase". Scanned PDF shows "Loading Ramp, Concrete" (3 instances). Both match "Exterior stairs" and "Loading docks" options.

- **Matched Options (by relevance):**
  🔴 High — `89095: Exterior stairs`
  🟡 Medium — `125768: Loading docks`

- **Evidence Source:** `image_extraction_data.json, image_id 1 + scanned_pdf_extraction.json`
- **Reasoning:** Image 1 shows "metal exterior staircase". Scanned PDF shows "Loading Ramp, Concrete" (3 instances). Both match "Exterior stairs" and "Loading docks" options.

### Table: Roofing Summary (tableId: 44824420)

#### Field: _quire_keyword_value:
- **Current Value:** `null`
- **Evidence Value:** Multiple roof images (IDs 2-7, 10-12) show "TPO or PVC membrane" with "light-colored membrane", "gravel/stone aggregate", "bituminous/synthetic membrane". The most consistent match is TPO-membrane (common in commercial buildings). Image 1 also shows "metal roofing/overhang" (corrugated metal panel).

- **Matched Options (by relevance):**
  🟡 Medium — `88683: TPO-membrane`
  🟡 Medium — `88684: PVC-membrane`
  🟡 Medium — `88686: Built-up with aggregate surface`
  🟡 Medium — `88692: Metal panel`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Multiple roof images (IDs 2-7, 10-12) show "TPO or PVC membrane" with "light-colored membrane", "gravel/stone aggregate", "bituminous/synthetic membrane". The most consistent match is TPO-membrane (common in commercial buildings). Image 1 also shows "metal roofing/overhang" (corrugated metal panel).

### Table: Roof details (tableId: 44824421)

#### Field: Unnamed Field
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_5 mentions HVAC units on roof with ladder access mentioned in page_7. Multiple roof images confirm roof access exists. Images show roof-mounted equipment accessible.

- **Matched Options (by relevance):**
  🟢 Low — `35948: Access to the roof was provided by portable ladder.`

- **Evidence Source:** `handwritten_extraction.json, page_5 + image_extraction_data.json`
- **Reasoning:** Handwritten page_5 mentions HVAC units on roof with ladder access mentioned in page_7. Multiple roof images confirm roof access exists. Images show roof-mounted equipment accessible.

### Table: Plumbing Summary (tableId: 44824424)

#### Field: Water Supply Piping
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3 explicitly states: "Piping: Supply line = COPPER". This directly matches "Water Supply Piping" with option "Copper" (100523).

- **Matched Options (by relevance):**
  🟡 Medium — `100523: Copper`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3 explicitly states: "Piping: Supply line = COPPER". This directly matches "Water Supply Piping" with option "Copper" (100523).

#### Field: Sanitary Waste Piping
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3 explicitly states: "Waste lines = PVC". This directly matches "Sanitary Waste Piping" with option "PVC" (95940).

- **Matched Options (by relevance):**
  🟡 Medium — `95940: PVC`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3 explicitly states: "Waste lines = PVC". This directly matches "Sanitary Waste Piping" with option "PVC" (95940).

#### Field: Domestic Water Heater Systems
- **Current Value:** `Include quantity/number of domestic hot water systems and capacity - delete comment`
- **Evidence Value:** Handwritten page_3: "Water heaters: Total # = 4, Manufacturer = Rheem, Location = Metrix, Buffers, Vacant, Capacity = 50, Type = ELECTRIC". This matches "Individual, tank-type electric water heaters, XX-gallons" (99243).

- **Matched Options (by relevance):**
  🔴 High — `99243: Individual, tank-type electric water heaters, XX-gallons`
  🟡 Medium — `99241: Individual, tank-type gas-fired water heaters, XX-gallons, XXX-MBH`
  🟢 Low — `99242: XX central, tank-type gas-fired water heaters, XXX-gallons, XXX-MBH`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Water heaters: Total # = 4, Manufacturer = Rheem, Location = Metrix, Buffers, Vacant, Capacity = 50, Type = ELECTRIC". This matches "Individual, tank-type electric water heaters, XX-gallons" (99243).

#### Field: Domestic Water Heater Location
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Location = Metrix, Buffers, Vacant". Water heaters are located within individual tenant units, matching "Within Unit" (125759).

- **Matched Options (by relevance):**
  🔴 High — `125759: Within Unit`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Location = Metrix, Buffers, Vacant". Water heaters are located within individual tenant units, matching "Within Unit" (125759).

#### Field: Domestic Water Boiler Systems
- **Current Value:** `Include quantity/number of domestic hot water systems and capacity - delete comment`
- **Evidence Value:** Handwritten page_3 shows "Water Boiler: Total # = NOT_APPLICABLE" (crossed out). No water boiler system present. Water heaters are used instead.

- **Matched Options (by relevance):**
  🟢 Low — `: Domestic hot water is provided by the central heating boiler. Please see Section 4.2 - HVAC for boiler details.`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3 shows "Water Boiler: Total # = NOT_APPLICABLE" (crossed out). No water boiler system present. Water heaters are used instead.

### Table: Electrical Summary (tableId: 44824429)

#### Field: Electrical Main Service
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_2: "Volts = 120-480". This voltage range (120V to 480V) is typical for three-phase, four-wire 277/480V service (which provides 277V phase-to-neutral and 480V phase-to-phase).

- **Matched Options (by relevance):**
  🔴 High — `127637: XXX- to XXX-Amp, three-phase, four-wire, 277/480-Volt`
  🟡 Medium — `99992: XXX-Amp, three-phase, four-wire, 277/480-Volt`
  🟢 Low — `99420: XXX-Amp, three-phase, four-wire, 120/208-Volt`
  🟢 Low — `99419: XXX-Amp, single-phase, three-wire, 120/240-Volt`

- **Evidence Source:** `handwritten_extraction.json, page_2`
- **Reasoning:** Handwritten page_2: "Volts = 120-480". This voltage range (120V to 480V) is typical for three-phase, four-wire 277/480V service (which provides 277V phase-to-neutral and 480V phase-to-phase).

#### Field: Federal Pacific Electric (FPE)
Stab-Lok Breaker Panels
- **Current Value:** `Fill this row out, do not leave blank - delete comment`
- **Evidence Value:** Handwritten page_2: "Electrical Panel Manufacturer = Milbank". Milbank is a different manufacturer than Federal Pacific Electric (FPE). FPE Stab-Lok panels are likely "Not present".

- **Matched Options (by relevance):**
  🔴 High — `125554: Present`
  🟡 Medium — `125553: Not present`

- **Evidence Source:** `handwritten_extraction.json, page_2`
- **Reasoning:** Handwritten page_2: "Electrical Panel Manufacturer = Milbank". Milbank is a different manufacturer than Federal Pacific Electric (FPE). FPE Stab-Lok panels are likely "Not present".

#### Field: Branch Wiring
- **Current Value:** `null`
- **Evidence Value:** Handwritten mentions electrical panel (Milbank) and voltage (120-480). Copper wiring is typical for commercial buildings. No direct evidence of branch wiring material.

- **Matched Options (by relevance):**
  🟢 Low — `95937: Observed copper in Unit XX`
  🟢 Low — `99994: Reportedly copper`

- **Evidence Source:** `handwritten_extraction.json + image_extraction_data.json`
- **Reasoning:** Handwritten mentions electrical panel (Milbank) and voltage (120-480). Copper wiring is typical for commercial buildings. No direct evidence of branch wiring material.

#### Field: Distribution Panels
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_2: "Electrical Panel Manufacturer = Milbank". Milbank panel suggests a main distribution panel, likely located in an electric room. Not explicitly stated.

- **Matched Options (by relevance):**
  🟡 Medium — `125934: The main distribution panel (MDP) is located in an electric room`

- **Evidence Source:** `handwritten_extraction.json, page_2`
- **Reasoning:** Handwritten page_2: "Electrical Panel Manufacturer = Milbank". Milbank panel suggests a main distribution panel, likely located in an electric room. Not explicitly stated.

### Table: Fire & Life Safety Systems (tableId: 44824432)

#### Field: Fire Sprinkler System
- **Current Value:** `Fill this row out, do not leave blank - ALSO, ONLY USE THE COVERAGE DROPDOWN VALUES FOR HEALTHCARE PROPERTIES, ALL OTHER PROPERTIES CAN BE GENERAL SYSTEM TYPE WITH NO COVERAGE MENTIONED - delete comment`
- **Evidence Value:** Handwritten page_3: "Fire riser/sprinkler type = WET" (highlighted). This directly matches "Wet pipe" (132301) or "Full coverage, wet pipe" (99428).

- **Matched Options (by relevance):**
  🔴 High — `132301: Wet pipe`
  🔴 High — `99428: Full coverage, wet pipe`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire riser/sprinkler type = WET" (highlighted). This directly matches "Wet pipe" (132301) or "Full coverage, wet pipe" (99428).

#### Field: Fire Pump
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Fire Pump: Location = NOT_APPLICABLE, Inspection Date = NOT_APPLICABLE, Total # = NOT_APPLICABLE, Manufacturer = NOT_APPLICABLE" (all crossed out). No fire pump present.

- **Matched Options (by relevance):**
  🟢 Low — `99429: XXX-gpm, diesel`
  🟢 Low — `99430: XXX-gpm, electric`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire Pump: Location = NOT_APPLICABLE, Inspection Date = NOT_APPLICABLE, Total # = NOT_APPLICABLE, Manufacturer = NOT_APPLICABLE" (all crossed out). No fire pump present.

#### Field: Fire Sprinkler Inspection Date
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Fire riser/sprinkler type: Inspection Date = Jun 2026". This matches the inspection date format.

- **Matched Options (by relevance):**
  🟡 Medium — `100036: XX/XX/XXXX`
  🟡 Medium — `101041: XX/XXXX`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire riser/sprinkler type: Inspection Date = Jun 2026". This matches the inspection date format.

#### Field: Fire Alarm System
- **Current Value:** `Fill this row out, do not leave blank - delete comment`
- **Evidence Value:** Handwritten page_3: "Fire alarm control panel: Location = Red star on map, Total # = 1, Manufacturer = FirePro Tech". Fire alarm system is present with 1 control panel.

- **Matched Options (by relevance):**
  🔴 High — `100074: Present - XX fire alarm control panels`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire alarm control panel: Location = Red star on map, Total # = 1, Manufacturer = FirePro Tech". Fire alarm system is present with 1 control panel.

#### Field: Fire Alarm Inspection Date
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Fire alarm control panel: Inspection Date = 11/2025". This matches the inspection date format.

- **Matched Options (by relevance):**
  🟡 Medium — `100036: XX/XX/XXXX`
  🟡 Medium — `101041: XX/XXXX`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire alarm control panel: Inspection Date = 11/2025". This matches the inspection date format.

#### Field: Fire Extinguishers
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Fire extinguisher: Location = see picture". Fire extinguishers are present on site.

- **Matched Options (by relevance):**
  🔴 High — `95450: Present`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire extinguisher: Location = see picture". Fire extinguishers are present on site.

#### Field: Fire Extinguisher Inspections
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_3: "Fire extinguisher: Inspection Date = Jun 2026". This is recent (current as of July 2026 inspection), so inspection is "Current".

- **Matched Options (by relevance):**
  🔴 High — `125938: Current`

- **Evidence Source:** `handwritten_extraction.json, page_3`
- **Reasoning:** Handwritten page_3: "Fire extinguisher: Inspection Date = Jun 2026". This is recent (current as of July 2026 inspection), so inspection is "Current".

#### Field: Life Safety Fixtures
- **Current Value:** `null`
- **Evidence Value:** Image data includes "electrical" and "mechanical" areas. Fire alarm system present suggests life safety fixtures are installed. Not explicitly mentioned in extraction data.

- **Matched Options (by relevance):**
  🟢 Low — `125941: Pull stations`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Image data includes "electrical" and "mechanical" areas. Fire alarm system present suggests life safety fixtures are installed. Not explicitly mentioned in extraction data.

### Table: Description (tableId: 44824400)

#### Field: Pavement
- **Current Value:** `null`
- **Evidence Value:** Scanned PDF Extra Features: "Paving - Light Concrete" with 92,000 SF, Average quality, built 1979.

- **Matched Options (by relevance):**
  🔴 High — `95939: Concrete`

- **Evidence Source:** `scanned_pdf_extraction.json`
- **Reasoning:** Scanned PDF Extra Features: "Paving - Light Concrete" with 92,000 SF, Average quality, built 1979.

#### Field: Pavement Location
- **Current Value:** `null`
- **Evidence Value:** Paving is described as "Paving - Light Concrete" - likely parking areas and driveways around the building. Exact location not specified in evidence.

- **Matched Options (by relevance):**
  🟢 Low — `96896: Side of building`

- **Evidence Source:** `scanned_pdf_extraction.json + image_extraction_data.json`
- **Reasoning:** Paving is described as "Paving - Light Concrete" - likely parking areas and driveways around the building. Exact location not specified in evidence.

#### Field: Parking Space Count Source
- **Current Value:** `null`
- **Evidence Value:** Handwritten form shows "Parking space Total = 120", "General = 62", "Loading docks = 58" - indicating a physical count was performed.

- **Matched Options (by relevance):**
  🔴 High — `125540: A count in the field`

- **Evidence Source:** `handwritten_extraction.json, page_1`
- **Reasoning:** Handwritten form shows "Parking space Total = 120", "General = 62", "Loading docks = 58" - indicating a physical count was performed.

#### Field: Curbing
- **Current Value:** `null`
- **Evidence Value:** Property has concrete paving and parking areas, suggesting concrete curbing. Not explicitly mentioned in evidence.

- **Matched Options (by relevance):**
  🟡 Medium — `95939: Concrete`

- **Evidence Source:** `image_extraction_data.json`
- **Reasoning:** Property has concrete paving and parking areas, suggesting concrete curbing. Not explicitly mentioned in evidence.

#### Field: Elevator Type
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: "Elevators = NOT_APPLICABLE" (crossed out). All elevator-related fields on page_4 are marked NOT_APPLICABLE. No elevator present.

- **Matched Options (by relevance):**

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: "Elevators = NOT_APPLICABLE" (crossed out). All elevator-related fields on page_4 are marked NOT_APPLICABLE. No elevator present.

#### Field: Number of Elevators
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Inspection Date
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Machinery Age
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Cab Flooring
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Elevator Cab Walls
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No elevator present.

#### Field: Escalators
- **Current Value:** `null`
- **Evidence Value:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No escalators present.

- **Evidence Source:** `handwritten_extraction.json, page_4`
- **Reasoning:** Handwritten page_4: All elevator fields marked NOT_APPLICABLE. No escalators present.

### Table: Municipal code findings (tableId: 44824441)

#### Field: Current Zoning
- **Current Value:** `null`
- **Evidence Value:** Scanned PDF shows "State Class Code: F1 -- Real, Commercial" and "Neighborhood: GLENDALE BUSINESS PARK". Property is commercial/industrial. However, the exact zoning district is not specified in the evidence.

- **Matched Options (by relevance):**
  🟡 Medium — `125918: IX, Industrial District`
  🟡 Medium — `125917: CX, Commercial District`

- **Evidence Source:** `scanned_pdf_extraction.json`
- **Reasoning:** Scanned PDF shows "State Class Code: F1 -- Real, Commercial" and "Neighborhood: GLENDALE BUSINESS PARK". Property is commercial/industrial. However, the exact zoning district is not specified in the evidence.

#### Field: Current Use Permitted
- **Current Value:** `null`
- **Evidence Value:** Scanned PDF shows commercial/industrial use. Property appears to be used in a manner consistent with its zoning. "Appears legal, conforming" is most likely.

- **Matched Options (by relevance):**
  🔴 High — `125925: Appears legal, conforming`
  🟢 Low — `125926: Appears legal, non-conforming`

- **Evidence Source:** `scanned_pdf_extraction.json`
- **Reasoning:** Scanned PDF shows commercial/industrial use. Property appears to be used in a manner consistent with its zoning. "Appears legal, conforming" is most likely.

---
## Blueprint Tags (Metadata Fields)

> Blueprint tags have been analyzed for evidence. Some tags are pre-filled with existing values.

| Field | Current Value | Evidence Value | Evidence Source | Confidence |
|---|---|---|---|---|
| # of Buildings | null | 1 | handwritten_extraction.json, page_1: "Total # of buildings = 1" | High |
| # of Parcels | null | 1 | scanned_pdf_extraction.json, Property Details: "Land: 331,884 SF" | Medium |
| # of Stories | null | 1 | image_extraction_data.json (building_area: roof, exterior) | Medium |
| Author SF ID | 003Uf00000WC13HIAT | 003Uf00000WC13HIAT | Pre-filled in form_schema.json | High |
| Building Gross Square Feet | null | 207,600 | scanned_pdf_extraction.json, Property Details: "Building Area: 207,600 SF" | Medium |
| Building Net Square Feet | 355404 | 208,050 | scanned_pdf_extraction.json, Property Details: "Net Rentable Area: 208,050" | Medium |
| Building Square Feet | null | 207,600 | scanned_pdf_extraction.json, Property Details: "Building Area: 207,600 SF" | High |
| Client Address Line 2 | Not Used | Not Used | Pre-filled in form_schema.json | High |
| Client City | 3T2 Greenwood Village | 3T2 Greenwood Village | Pre-filled in form_schema.json | High |
| Client Contact | null | Not specified | handwritten_extraction.json, page_1: "Site Contact Name = James Holland, Phone = 8328376672" | Medium |
| Client Name | Empower Annuity Insurance Company of America, a Colorado Corporation, its successors and assigns | Empower Annuity Insurance Company of America | Pre-filled in form_schema.json | High |
| Client Phone # | Not Used | Not Used | Pre-filled in form_schema.json | High |
| Client Site Name | null | 8000 Market Street / PCA-1790151 | form_schema.json: report_id = 1790151 | Medium |
| Client State | Colorado | Colorado | Pre-filled in form_schema.json | High |
| Client Street Address | 8515 Orchard Road | 8515 Orchard Road | Pre-filled in form_schema.json | High |
| Client Zip Code | 80111 | 80111 | Pre-filled in form_schema.json | High |
| Company Abbreviation | EBI | EBI | Pre-filled in form_schema.json | High |
| Company City | Burlington | Burlington | Pre-filled in form_schema.json | High |
| Company Corporate Name | EnviroBusiness, Inc. | EnviroBusiness, Inc. | Pre-filled in form_schema.json | High |
| Company Full Name | EBI Consulting | EBI Consulting | Pre-filled in form_schema.json | High |
| Company Phone # | 781.273.2500 | 781.273.2500 | Pre-filled in form_schema.json | High |
| Company State | MA | MA | Pre-filled in form_schema.json | High |
| Company Street Address | 21 B Street | 21 B Street | Pre-filled in form_schema.json | High |
| Company Zip Code | 01803 | 01803 | Pre-filled in form_schema.json | High |
| Contract Date Signed | July 13, 2026 | July 13, 2026 | Pre-filled in form_schema.json | High |
| Cost Multiplier | 1.0 | 1.0 | Pre-filled in form_schema.json | High |
| Currency | null | USD | scanned_pdf_extraction.json | Medium |
| Date of Report | August 3, 2026 | August 3, 2026 | Pre-filled in form_schema.json | High |
| Decimal Lat | 29.772571 | 29.772571 | Pre-filled in form_schema.json | High |
| Decimal Lon | -95.287785 | -95.287785 | Pre-filled in form_schema.json | High |
| Decimal Places | 2 | 2 | Pre-filled in form_schema.json | High |
| EBI Assessor's Name | null | James Holland | handwritten_extraction.json, page_1: "Site Contact Name = James Holland" | Medium |
| EBI Project Number | 260070755PR | 260070755PR | Pre-filled in form_schema.json | High |
| Effective Age | null | 47-49 years (2026 - 1977/1979) | scanned_pdf_extraction.json, Extra Features: Year Built 1977-1979 | Medium |
| Electrical Service Provider | null | CentrePoint | handwritten_extraction.json, page_1: "Electricity = CentrePoint" | High |
| Flood Zone | (empty) | Not specified in evidence | scanned_pdf_extraction.json, text_content | Medium |
| Hurricane Susceptible Region | null | Yes (Gulf Coast) | scanned_pdf_extraction.json, text_content: Harris County, Houston, TX | Medium |
| Immediate Uninflated Costs | 0 | 0 | Pre-filled in form_schema.json | High |
| Inflation Factor | 2.5 | 2.5 | Pre-filled in form_schema.json | High |
| Latitude Degrees | 29 | 29 | Pre-filled in form_schema.json | High |
| Latitude Minutes | 46 | 46 | Pre-filled in form_schema.json | High |
| Latitude Seconds | 21.255594 | 21.255594 | Pre-filled in form_schema.json | High |
| Longitude Degrees | 95 | 95 | Pre-filled in form_schema.json | High |
| Longitude Minutes | 17 | 17 | Pre-filled in form_schema.json | High |
| Longitude Seconds | 16.025994 | 16.025994 | Pre-filled in form_schema.json | High |
| Net Rentable or Gross? | null | Net Rentable (208,050 SF) | scanned_pdf_extraction.json, Property Details: "Net Rentable Area: 208,050" | Medium |
| Net SF Source | null | HCAD (Harris County Appraisal District) | scanned_pdf_extraction.json | Medium |
| Number of Loading dock bays | null | 3 | scanned_pdf_extraction.json, Extra Features: "Loading Ramp, Concrete" (3 instances: #4, #5, #6) | Medium |
| Number of Units | null | 4 | handwritten_extraction.json, page_1: "Total # of units = 4, Occupied units = 3, Vacant units = 1" | High |
| Number of truck / trailer parking spaces | null | 58 | handwritten_extraction.json, page_1: "Loading docks = 58" | Medium |
| Overall Property Condition | null | Fair | image_extraction_data.json (building_area: exterior, roof, hvac, etc.) | Medium |
| PCA Table 1 | Immediate and Short Term Repairs | Immediate and Short Term Repairs | Pre-filled in form_schema.json | High |
| Potable Water Supply Provider | null | Municipal (Houston) | scanned_pdf_extraction.json, text_content: "Mailing Address: 600 UNICORN PARK DR WOBURN, MA 01801-3376" + Harris County context | Medium |
| Project Task Record ID | aAzUf0000009lFrKAI | aAzUf0000009lFrKAI | Pre-filled in form_schema.json | High |
| Property Unit Count (SF, Units, etc.) | null | 4 units / 207,600 SF | handwritten_extraction.json, page_1 + scanned_pdf_extraction.json | Medium |
| Property Unit Title | SF | SF | Pre-filled in form_schema.json | High |
| Report Author | Sahhil Maan | Sahhil Maan | Pre-filled in form_schema.json | High |
| Report Author Signature | Signature for Sahhil Maan | Signature for Sahhil Maan | Pre-filled in form_schema.json | High |
| Report Reviewer | Jon E. Steenson, PE | Jon E. Steenson, PE | Pre-filled in form_schema.json | High |
| Report Reviewer Email | jsteenson@ebiconsulting.com | jsteenson@ebiconsulting.com | Pre-filled in form_schema.json | High |
| Report Reviewer Phone # | 610.529.1293 | 610.529.1293 | Pre-filled in form_schema.json | High |
| Report Reviewer Signature | Signature for Jon E. Steenson, PE | Signature for Jon E. Steenson, PE | Pre-filled in form_schema.json | High |
| Report Reviewer Title | Program Manager | Program Manager | Pre-filled in form_schema.json | High |
| Report Service Name | Property Condition Report | Property Condition Report | Pre-filled in form_schema.json | High |
| Reserve Inflated Costs | 0 | 0 | Pre-filled in form_schema.json | High |
| Reserve Inflated Costs / Room / Year | 0.00 | 0.00 | Pre-filled in form_schema.json | High |
| Reserve Term | 12 | 12 | Pre-filled in form_schema.json | High |
| Reserve Uninflated Costs | 0 | 0 | Pre-filled in form_schema.json | High |
| Reserve Uninflated Costs / Room / Year | 0.00 | 0.00 | Pre-filled in form_schema.json | High |
| Reviewer SF Id | 003Uf00000WBzglIAD | 003Uf00000WBzglIAD | Pre-filled in form_schema.json | High |
| Roof Type | null | TPO Membrane (flat roof) | image_extraction_data.json (image_id 2-7, 10-12) | Medium |
| Sewage Disposal System Provider | null | Municipal (Houston) | handwritten_extraction.json, page_1: "Solid waste (Trash) = WasteManagement" | Medium |
| Short Term Costs | 1 | 1 | Pre-filled in form_schema.json | High |
| Short Term Uninflated Costs | 0 | 0 | Pre-filled in form_schema.json | High |
| Site Acreage | null | 7.62 | scanned_pdf_extraction.json, Property Details: "Land: 331,884 SF" | Medium |
| Site City | Houston | Houston | Pre-filled in form_schema.json | High |
| Site County | Harris | Harris | scanned_pdf_extraction.json, table_content: "HARRIS COUNTY" | Medium |
| Site Escort  | Lindsay Smith | (pre-filled, no additional evidence) | form_schema.json | High |
| Site Inspection Date | null | June 30, 2026 (images dated 20260630) | image_extraction_data.json (image filenames: 20260630_*) | Medium |
| Site Name | 8000 Market Street | 8000 Market Street | Pre-filled in form_schema.json | High |
| Site Project Type | Other | Other | Pre-filled in form_schema.json | High |
| Site State | Texas | Texas | Pre-filled in form_schema.json | High |
| Site Street Address | 8000 Market Street | 8000 Market Street | Pre-filled in form_schema.json | High |
| Site Type/Use | Industrial | Industrial | Pre-filled in form_schema.json + scanned_pdf_extraction.json: "F1 -- Real, Commercial" | High |
| Site Zip Code | 77029 | 77029 | Pre-filled in form_schema.json | High |
| Total # of Parking Spaces | null | 120 | handwritten_extraction.json, page_1: "Parking space Total = 120, General = 62, Loading docks = 58" | High |
| Year Constructed | 1977-1978 | 1977-1979 | scanned_pdf_extraction.json, Extra Features: Year Built 1977-1979 | Medium |
| Zoning  | INCLUDE FULL ZONING DESCRIPTION, NOT JUST THE ACRONYM | (pre-filled, no additional evidence) | form_schema.json | High |

---
## Pending Fields (No Supporting Evidence)

> Fields below have no matching evidence in any extraction source. These need to be filled manually or require additional data collection.

### Table Fields (No Evidence)

#### Table: Description

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Vehicle Ingress / Egress Points | null | A single entry drive provides access to the Subject Property from the adjacent road frontages., Traffic signals are provided at one intersection entering the property., Traffic signals are provided at... | No specific evidence about vehicle ingress/egress points found in any extraction source. |
| Parking Garages | null | XXXX-level, concrete-framed, under building, with XX parking spaces (included in the total parking spaces above), XXXX-level, steel-framed, under building, with XX parking spaces (included in the tota... | No evidence of parking garage. Property has surface parking (120 spaces, 62 general + 58 loading docks). Parking garage options all have selectable values but none match evidence. |
| Accessible Lifts | null | Present - XXX lb capacity | No evidence of accessible lifts found in any extraction source. |

#### Table: Electrical Summary

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Unit Panel Service Capacity | null | 30-Amps, 40-Amps, 50-Amps, 60-Amps, 100-Amps, 125-Amps, 150-Amps, 200-Amps, 100-800 Amps, XXX-Amps, XXX to XXX-Amps, XX-Amps (Fuses) | No evidence of unit panel service capacity found in any extraction source. |
| Transformers | null | Pole-mounted, utility-owned, Pad-mounted, utility-owned, Vault-mounted, utility-owned | No evidence of transformers found in any extraction source. |
| Electrical Meters | null | Centrally metered, electrical room, Individually metered, building exterior, Centrally metered, building exterior, Individually metered, electrical room | No evidence of electrical meter configuration found in any extraction source. |
| GFCI Fixtures | null | GFCI outlets were observed at appropriate locations., GFCI outlets have been installed in some units. According to the Site Contact, they are installed in units at tenant turnover., No electric outlet... | No evidence of GFCI fixtures found in any extraction source. |
| Emergency Generators | Fill this row out, do not leave blank - delete comment | None present, One XXX kW (XXX kVA) diesel-fueled emergency generator with XXX-gallon belly tank, One XXX kW (XXX kVA) natural gas-fueled emergency generator, One XXX kW (XXX kVA) diesel-fueled emergen... | No evidence of emergency generators found in any extraction source. |
| Energy Management System | null | Present, controls property lighting and HVAC systems | No evidence of energy management system found in any extraction source. |

#### Table: Facade Summary

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Unit Balcony / Patio Doors | null | Insulated metal, Aluminum and glass, Insulated metal with glass panel inset, Solid-core wood, Wood and glass, Vinyl and glass | Industrial property - no balconies or patios present. |
| Municipal Façade Inspection Required | null | Yes, ****LEAVE BLANK IF NO or NA**** | No evidence of municipal facade inspection requirements. Property is in Houston, TX - not NYC. |
| Municipal Fire Escape Inspection Required | null | Yes, ****LEAVE BLANK IF NO or NA**** | No evidence of fire escape inspection requirements. Property is in Houston, TX. |
| California Exterior Elevated Element Inspection Required | null | Yes, ****LEAVE BLANK IF NO or NA**** | Property is in Texas, not California. Not applicable. |

#### Table: Fire & Life Safety Systems

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Fire Sprinkler Head Brand Omega or Central Observed | Fill this row out, do not leave blank - delete comment | Yes, None reported or observed | No evidence of sprinkler head brand found in any extraction source. |
| Fire Sprinkler System Water Storage | null | One wood storage tank - XX,XXX-gallons, XX wood storage tanks - XX,XXX-gallons each, One steel storage tank - XX,XXX-gallons, XX steel storage tanks - XX,XXX-gallons each, XX,XXX-gallons of wood domes... | No evidence of fire sprinkler water storage found in any extraction source. |
| Fire Alarm Control Panel Age | null | XX years | No evidence of fire alarm control panel age found in any extraction source. |
| Fire Alarm System Monitoring | null | 24-hour monitoring service - [input vendor name], Fire department | No evidence of fire alarm monitoring found in any extraction source. |
| Chemical Fire Suppression Systems | null | Present - [describe location] | No evidence of chemical fire suppression systems found in any extraction source. |
| Chemical Fire Suppression System Inspection Date | null | XX/XX/XXXX, XX/XXXX | No evidence of chemical fire suppression systems found in any extraction source. |
| Fire Department Connections | null | At building exterior, Adjacent to the building | No evidence of fire department connections found in any extraction source. |
| Fire Hydrants | null | Present | No evidence of fire hydrants found in any extraction source. Commercial property likely has municipal fire hydrants nearby. |
| Smoke Detectors | Fill this row out, do not leave blank - delete comment | Battery powered, Hardwired, Hardwired with battery backup, Hardwired and battery powered, None reported or observed | No evidence of smoke detector type found in any extraction source. Fire alarm system is present, suggesting smoke detectors may be connected. |
| CO Detectors | Fill this row out, do not leave blank - delete comment | Present at required locations, Present at [describe where present], missing at [describe where missing], Not required, no gas service (no CO source reported or observed), None reported or observed | No evidence of CO detectors found in any extraction source. Property has electric water heaters, but gas service may exist. |
| Smoke Evacuation | null | Present | No evidence of smoke evacuation systems found in any extraction source. |
| Stairwell Pressurization | null | Present | No evidence of stairwell pressurization found in any extraction source. Single-story building - no stairwells. |

#### Table: Landscaping, Site Improvements & Site Amenities

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Irrigation | null | An automatic irrigation system is present in the landscaped areas. | No evidence of irrigation system found in any extraction source. |
| Fencing Location | null | Property perimeter, Unit patios, Rear yard, North side of property, South side of property, East side of property, West side of property, [Describe location] | No evidence of fencing location found in any extraction source. |
| Retaining Walls | null | Concrete, CMU, Stone, Brick, Interlocking concrete block, Wood railroad ties | No evidence of retaining walls found in any extraction source. |
| Retaining Wall Location | null | [Describe retaining wall location] | No evidence of retaining walls found in any extraction source. |
| Water Features | null | Decorative fountain located [describe location], Landscape pool located [describe location], Children's splash park located [describe location] | No evidence of water features found in any extraction source. |
| Other Landscape Features | null | Community garden located [describe location], Wood-framed gazebo located [describe location], [Describe other landscape feature with location] | No evidence of other landscape features found in any extraction source. |
| Other Amenities | null | A car wash is provided [describe location], A dog wash facility is provided [describe location], [Describe other amenity with location], Self-storage units for tenant lease are located [describe locat... | No evidence of other amenities found in any extraction source. |

#### Table: Municipal code findings

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Certificate of Occupancy | null | Not provided, Provided, copy included in appendix, Obtained, copy provided in appendix | No evidence of certificate of occupancy found in any extraction source. |
| Outstanding Building Code Violations | null | Open violations reported, No open violations reported, Awaiting response | No evidence of building code violations found in any extraction source. |
| Outstanding Fire Code Violations | null | Open violations reported, No open violations reported, Awaiting response | No evidence of fire code violations found in any extraction source. |

#### Table: NYC Table

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Facade Inspection Required | null | Yes, No | Property is in Houston, TX - not NYC. Not applicable. |
| Landmark District | null | Yes, No | Property is in Houston, TX - not NYC. Not applicable. |

#### Table: On-Site Sewage Lift Stations

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Reported System Adequacy | null | Adequate, Not adequate | No evidence of private water well. Property appears to be on municipal water supply. |
| System Maintenance Provider | null | Professional third-party - [provide name], Other - [provide name & qualifications] | No evidence of private water well. |
| Are there any concerns regarding the quality of maintenance being performed on the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are any buildings or structures located on top of the lift station? | null | No, Yes - [provide details] | No evidence found in any extraction source. |
| Is equipment accessible to individuals other than authorized personnel? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are there any current or previous violations? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is this system type atypical for the market? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any other person or property, other than the Borrower or Subject Property, authorized to use the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any part of the system owned or maintained by the residents? | null | No, Yes - [provide details] | No evidence of private water well. |
| Does the system fail to meet or exceed applicable federal, state, and/or local requirements? | null | No, Yes - [provide details] | No evidence of private water well. |

#### Table: Plumbing Summary

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Gas Distribution Piping | null | Threaded, black iron, Welded, black iron, Threaded and welded, black iron, Corrugated stainless steel tubing | No evidence of gas distribution piping found in any extraction source. |
| Plumbing Fittings | null | Stainless steel, Brass, Chrome | No evidence of plumbing fittings found in any extraction source. |
| Booster Pump Systems | null | Present - XX pumps | No evidence of booster pump systems found in any extraction source. |
| Sump Pump / Sewage Ejector Systems | null | Present - XX pumps | No evidence of sump pump or sewage ejector systems found in any extraction source. |
| Water Softener Systems | null | Present | No evidence of water softener systems found in any extraction source. |
| Domestic Water Storage Tanks | null | One wood storage tank - XX,XXX-gallons, XX wood storage tanks - XX,XXX-gallons each, One steel storage tank - XX,XXX-gallons, XX steel storage tanks - XX,XXX-gallons each | No evidence of domestic water storage tanks found in any extraction source. |
| Domestic Water Heater Age | null | XX years, XX to XX years | No evidence of water heater age found in any extraction source. Handwritten mentions capacity (50 gal) and type (ELECTRIC) but not age. |
| Domestic Water Boiler Location | null | Mechanical penthouse, Basement, Mechanical room | No evidence of water boiler - handwritten shows NOT_APPLICABLE (crossed out). |
| Domestic Water Boiler Age | null | XX years, XX to XX years | No evidence of water boiler - handwritten shows NOT_APPLICABLE (crossed out). |
| Hot Water Storage Tanks | null | One storage tank, XXX-gallons, XXX-MBH, XX storage tanks, XXX-gallons, XXX-MBH, One storage tank, XXX-gallons, electric, XX storage tanks, XXX-gallons, electric | No evidence of hot water storage tanks found in any extraction source. |

#### Table: Private Septic Systems

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Reported System Adequacy | null | Adequate, Not adequate | No evidence of private water well. Property appears to be on municipal water supply. |
| Distance From Leach Field to Surrounding Bodies of Water That Could Be Impacted by the Effluent | null | Not applicable, XX feet | No evidence found in any extraction source. |
| Cost of Connecting Subject Property to Municipal System | null | $XXX,XXX per property management, Information not provided by property management, No municipal connection available per property management | No evidence found in any extraction source. |
| Level of Work Required to Accomplish Municipal System Connection | null | Not applicable, Extensive | No evidence found in any extraction source. |
| System Maintenance Provider | null | Professional third-party - [provide name], Other - [provide name & qualifications] | No evidence of private water well. |
| Are there any concerns regarding the quality of maintenance being performed on the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are any buildings or structures located on top of the leach field? | null | No, Yes - [provide details] | No evidence found in any extraction source. |
| Is equipment accessible to individuals other than authorized personnel? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are there any current or previous violations? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is this system type atypical for the market? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any other person or property, other than the Borrower or Subject Property, authorized to use the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any part of the system owned or maintained by the residents? | null | No, Yes - [provide details] | No evidence of private water well. |
| Does the system fail to meet or exceed applicable federal, state, and/or local requirements? | null | No, Yes - [provide details] | No evidence of private water well. |

#### Table: Private Wastewater Treatment Plant

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Reported System Adequacy | null | Adequate, Not adequate | No evidence of private water well. Property appears to be on municipal water supply. |
| Distance From the Property to the Effluent Discharge Body of Water | null | Not applicable, XX feet | No evidence found in any extraction source. |
| Cost of Connecting Subject Property to Municipal System | null | $XXX,XXX per property management, Information not provided by property management, No municipal connection available per property management | No evidence found in any extraction source. |
| Level of Work Required to Accomplish Municipal System Connection | null | Not applicable, Extensive | No evidence found in any extraction source. |
| System Maintenance Provider | null | Professional third-party - [provide name], Other - [provide name & qualifications] | No evidence of private water well. |
| Are there any concerns regarding the quality of maintenance being performed on the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is equipment accessible to individuals other than authorized personnel? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are there any current or previous violations? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is this system type atypical for the market? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any other person or property, other than the Borrower or Subject Property, authorized to use the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any part of the system owned or maintained by the residents? | null | No, Yes - [provide details] | No evidence of private water well. |
| Does the system fail to meet or exceed applicable federal, state, and/or local requirements? | null | No, Yes - [provide details] | No evidence of private water well. |

#### Table: Private Water Well

| Field | Current Value | Available Options | Notes |
|---|---|---|---|
| Reported System Adequacy | null | Adequate, Not adequate | No evidence of private water well. Property appears to be on municipal water supply. |
| Cost of Connecting Property to Municipal System | null | $XXX,XXX per property management, Information not provided by property management, No municipal connection available per property management | No evidence of private water well. Property likely on municipal water. |
| Level of Work Required to Accomplish Municipal System Connection | null | Not applicable, Extensive | No evidence found in any extraction source. |
| System Maintenance Provider | null | Professional third-party - [provide name], Other - [provide name & qualifications] | No evidence of private water well. |
| Are there any concerns regarding the quality of maintenance being performed on the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is equipment accessible to individuals other than authorized personnel? | null | No, Yes - [provide details] | No evidence of private water well. |
| Are there any concerns regarding the backup water source? | null | No, Yes - [describe backup water source & concerns] | No evidence of private water well. |
| Are there any current or previous violations? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is this system type atypical for the market? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any other person or property, other than the Borrower or Subject Property, authorized to use the system? | null | No, Yes - [provide details] | No evidence of private water well. |
| Is any part of the system owned or maintained by the residents? | null | No, Yes - [provide details] | No evidence of private water well. |
| Does the system fail to meet or exceed applicable federal, state, and/or local requirements? | null | No, Yes - [provide details] | No evidence of private water well. |

### Blueprint Tags (No Evidence)

| Field | Current Value | Notes |
|---|---|---|
| # ADA Std. Parking Spaces | null | No evidence of ADA parking count found in any extraction source. |
| # ADA Van Parking Spaces | null | No evidence of ADA van parking count found in any extraction source. |
| Clear height of warehouse space | null | No evidence of clear height found in any extraction source. |
| Client Site Number | null | No evidence found in any extraction source. |
| Client That Signed Contract | null | No evidence of client that signed contract found in any extraction source. |
| Contract Date | null | No evidence found in any extraction source. |
| Contract Title | null | No evidence of contract title found in any extraction source. |
| Contract terms | null | No evidence of contract terms found in any extraction source. |
| Most Recent Renovation | null | No evidence of recent renovation found in any extraction source. |
| Natural Gas Service Provider | null | No evidence of natural gas provider found in any extraction source. |
| Number of drive-in loading bays | null | No evidence of drive-in loading bays found in any extraction source. |
| Oil Service Provider | null | No evidence of oil service. Property likely uses electric or natural gas. |
| Parcel Configuration | (empty) | No evidence of parcel configuration found in any extraction source. |
| Parcel Contiguity | null | No evidence of parcel contiguity found in any extraction source. |
| Report Author Title | null | No evidence of report author title found in any extraction source. |
| Seismic Zone | null | No evidence of seismic zone found in any extraction source. Houston, TX is in a low seismic zone. |
| Site Escort Company | null | No evidence of site escort company found in any extraction source. |
| Site Escort Title | null | No evidence of site escort title found in any extraction source. |
| Site Street Address Line 2 | null | No evidence found in any extraction source. |
| Special Wind Region | null | No evidence of special wind region designation found in any extraction source. |
| Temperature | null | No evidence of temperature conditions found in any extraction source. |
| Title Page Image | null | No evidence of title page image found in any extraction source. |
| Weather | null | No evidence of weather conditions found in any extraction source. |
| Wind zone | null | No evidence of wind zone found in any extraction source. |

---
## Evidence Source Summary

### Handwritten Extraction (`handwritten_extraction.json`)

- **Pages:** 7 (page_5, page_6, page_7, page_3, page_4, page_1, page_2)
- **Total Entries:** 70
- **Key Data Points:**
  - Site Contact: James Holland (832-837-6672)
  - Building: 1 building, 4 units (3 occupied, 1 vacant)
  - Parking: 120 total (62 general + 58 loading docks)
  - Utilities: CentrePoint (electricity), WasteManagement (trash), AT&T (internet)
  - Plumbing: 4 Rheem electric water heaters (50 gal), copper supply, PVC waste
  - Fire Safety: WET sprinkler, FirePro Tech alarm panel, extinguishers inspected Jun 2026
  - HVAC: Roof-mounted units (Carrier, Johnson, York, Trane)
  - Electrical: 120-480V, Milbank panel
  - Elevators: NOT APPLICABLE

### Scanned PDF Extraction (`scanned_pdf_extraction.json`)

- **Text Fields:** 13 entries
- **Tables:** 6 tables
- **Charts:** 2 charts
- **Key Data Points:**
  - Account: 0401900020035
  - Owner: HOUSTON INFILL INDUSTRIAL INVESTORS II LLC
  - Building Area: 207,600 SF, Class C, Net Rentable: 208,050 SF
  - Land: 331,884 SF ($1,327,536)
  - Tax Jurisdictions: Houston ISD, Harris County, City of Houston, etc.
  - Extra Features: Paving (1979), Dock Level Floor (1977), Office Enclosure (1977), Loading Ramps (1977)

### Image Extraction (`image_extraction_data.json`)

- **Total Images:** 120
- **Building Areas Covered:** basement, bathroom, bedroom, ceiling, electrical, exterior, garage, hallway, hvac, kitchen, mechanical, office, roof, unknown, utility_room
- **Image Distribution:**
  - basement: 1 images
  - bathroom: 1 images
  - bedroom: 3 images
  - ceiling: 1 images
  - electrical: 5 images
  - exterior: 32 images
  - garage: 3 images
  - hallway: 5 images
  - hvac: 9 images
  - kitchen: 2 images
  - mechanical: 1 images
  - office: 2 images
  - roof: 15 images
  - unknown: 3 images
  - utility_room: 37 images
- **Condition Distribution:**
  - excellent: 6 images
  - fair: 49 images
  - good: 51 images
  - poor: 14 images
- **Key Observations:**
  - Exterior: Good condition, stucco finish with peeling paint, metal staircase
  - Roof: Fair to Poor condition, TPO/PVC membrane, water pooling, drainage issues
  - HVAC: Fair condition, Carrier units, surface rust
  - Electrical: Present but condition not specified
  - Interior: Various areas (bathroom, bedroom, kitchen, office, garage) documented

---
## Appendix: Tables Overview

| Table Name | Table ID | Fields | Status |
|---|---|---|---|
| General Description Table | 44824387 | 2 | Analyzed |
| Subject Property Improvements | 44824388 | 0 | Skipped (empty) |
| Industrial Property Information | 44824390 | 0 | Skipped (empty) |
| EQT Table | 44824391 | 0 | Skipped (empty) |
| NorthBridge Table | 44824392 | 0 | Skipped (empty) |
| Tenant Units Types and Mix | 44824393 | 0 | Skipped (empty) |
| Tenant Units Observed | 44824395 | 0 | Skipped (empty) |
| Property Condition & Maintenance | 44824397 | 2 | Analyzed |
| Topography | 44824399 | 2 | Analyzed |
| Description | 44824400 | 6 | Analyzed |
| Landscaping, Site Improvements & Site Amenities | 44824403 | 14 | Analyzed |
| Utilities | 44824405 | 2 | Analyzed |
| Private Water Well | 44824407 | 12 | Pending |
| Private Septic Systems | 44824409 | 13 | Pending |
| Private Wastewater Treatment Plant | 44824410 | 12 | Pending |
| On-Site Sewage Lift Stations | 44824411 | 10 | Pending |
| Substructure | 44824413 | 3 | Analyzed |
| Superstructure | 44824415 | 5 | Analyzed |
| Facade Summary | 44824417 | 11 | Analyzed |
| Roofing Summary | 44824420 | 3 | Analyzed |
| Roof details | 44824421 | 4 | Analyzed |
| Typical Interior Finishes | 44824423 | 0 | Skipped (empty) |
| Plumbing Summary | 44824424 | 15 | Analyzed |
| Subject Property HVAC Units | 44824426 | 0 | Skipped (empty) |
| Electrical Summary | 44824429 | 10 | Analyzed |
| Fire & Life Safety Systems | 44824432 | 20 | Analyzed |
| Description | 44824438 | 8 | Analyzed |
| ASTM E 2018-24 Uniform Abbreviated Screening Checklist for the 2010 Americans with Disabilities Act | 44824439 | 0 | Skipped (empty) |
| Condition | 44824440 | 0 | Skipped (empty) |
| Municipal code findings | 44824441 | 5 | Analyzed |
| NYC Table | 44824442 | 2 | Pending |
| Open Violations | 44824443 | 0 | Skipped (empty) |
| Natural Hazards Conclusions | 44824444 | 0 | Skipped (empty) |
| Key Site Manager Interview | 44824445 | 0 | Skipped (empty) |
| Additional Interviews | 44824446 | 0 | Skipped (empty) |
