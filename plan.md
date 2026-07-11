# AI Inspection Report Automation - MVP Architecture

## Objective

Build an AI-powered inspection report automation system that:

- Uploads **2 PDFs**
  - Handwritten questionnaire
  - Scanned inspection report
- Uploads **200+ building images**
- Extracts structured information using **Qwen2.5-VL-3B-Instruct**
- Stores extracted data in JSON
- Allows manual review and correction
- Maps extracted values to Quire fields
- Automatically fills the Quire form using Playwright

---

# Technology Stack

| Component        | Technology                 |
| ---------------- | -------------------------- |
| Frontend         | Streamlit                  |
| Vision Model     | Qwen2.5-VL-3B-Instruct     |
| Storage          | JSON (Project Based)       |
| Automation       | Playwright                 |
| Language         | Python                     |
| PDF Processing   | pdf2image / PyMuPDF        |
| Image Processing | PIL / OpenCV (if required) |

---

# Project Structure

```
inspection_ai/

│
├── app.py
├── config.py
│
├── storage/
│   └── projects/
│       └── project_id/
│           ├── project.json
│           ├── handwritten.pdf
│           ├── scanned.pdf
│           ├── images/
│           ├── document_output.json
│           ├── image_output.json
│           ├── mapping.json
│           └── processing.log.json
│
├── services/
│   ├── project_manager.py
│   ├── pdf_processor.py
│   ├── image_processor.py
│   ├── mapping_service.py
│   ├── review_service.py
│   └── playwright_service.py
│
├── models/
│   └── qwen_vl.py
│
├── prompts/
│   ├── pdf_extraction.txt
│   ├── image_analysis.txt
│   └── field_mapping.txt
│
├── utils/
│
└── logs/
```

---

# Core Modules

## 1. Project Manager

Responsible for:

- Create Project
- Save Project
- Load Project
- Update Project JSON
- Manage Project Files

This is the only module responsible for reading/writing project data.

---

## 2. PDF Processor

Responsibilities

- Convert PDF pages into images
- Send pages to Qwen
- Extract handwritten answers
- Extract scanned report information
- Return structured JSON

Output updates:

```
project.document_data
```

---

## 3. Image Processor

Responsibilities

For every uploaded image:

- Caption generation
- Building condition
- Roof type
- Damage detection
- Tool identification
- Area identification
- Select predefined dropdown values
- Confidence score

Output updates:

```
project.image_analysis
```

---

## 4. Review Service

Responsibilities

- Show extracted values
- Allow manual correction
- Save edited values
- Update project JSON

---

## 5. Mapping Service

Responsibilities

- Read extracted JSON
- Read Quire webpage fields
- Match extracted values
- Prepare final mapped data

Output

```
project.field_mapping
```

---

## 6. Playwright Service

Responsibilities

- Launch browser
- Login (if required)
- Extract webpage fields
- Fill textboxes
- Select dropdowns
- Click checkboxes
- Submit form

---

# Project Lifecycle

```
Create Project

↓

Upload PDFs

↓

Upload Images

↓

Store Raw Files

↓

Process PDFs

↓

Process Images

↓

Merge Results

↓

Save JSON

↓

Review & Edit

↓

Extract Quire Fields

↓

Map Values

↓

Preview

↓

Auto Fill

↓

Complete
```

---

# Project JSON Structure

```json
{
  "metadata": {
    "project_id": "",
    "project_name": "",
    "status": "",
    "created_at": ""
  },

  "files": {
    "handwritten_pdf": "",
    "scanned_pdf": "",
    "images": []
  },

  "document_data": {},

  "image_analysis": [],

  "field_mapping": {},

  "automation": {},

  "logs": []
}
```

This JSON acts as the single source of truth.

---

# Streamlit Screens

## Dashboard

- Create Project
- Open Existing Project
- Delete Project

---

## Upload

- Handwritten PDF
- Scanned PDF
- Images
- Start Processing

---

## Review

Editable extracted fields

- Owner Name
- Address
- Roof
- Wall
- etc.

---

## Image Analysis

For each image

- Preview
- Caption
- Building Condition
- Damage
- Confidence

---

## Automation

- Connect to Quire
- Extract Fields
- Preview Mapping
- Auto Fill

---

# Processing Order

1. Create Project
2. Upload Files
3. Save Files
4. PDF Extraction
5. Image Analysis
6. Merge Results
7. Save JSON
8. Review
9. Extract Website Fields
10. Mapping
11. Auto Fill
12. Complete

---

# Development Phases

## Phase 1

- Project Manager
- Streamlit UI
- Upload Module
- JSON Storage

---

## Phase 2

- Qwen Wrapper
- PDF Processing
- JSON Extraction

---

## Phase 3

- Image Processing
- Parallel Image Execution
- Image JSON Generation

---

## Phase 4

- Review Screen
- Editing Support
- Save Corrections

---

## Phase 5

- Playwright
- Website Field Extraction
- Field Mapping
- Form Filling

---

# Design Principles

- One Project = One Folder
- One Project = One JSON
- One Service = One Responsibility
- Every processing step updates `project.json`
- No service directly depends on another service
- All modules communicate through the Project Manager
- Keep Qwen isolated inside the model wrapper for easy replacement
- Save intermediate outputs for debugging and future reprocessing

---

# Confidence Scoring & Evidence

Each extraction (PDF, image, mapping) returns:

- `confidence_score` (0.0 - 1.0)
- `evidence` (text snippet, image region, or field reference)

Example output structure:

```json
{
  "field_name": "roof_type",
  "value": "Metal",
  "confidence_score": 0.92,
  "evidence": "Detected in image_001.jpg, region: [120, 45, 200, 100]"
}
```

---

# Processing Logs & Status

Each project maintains `processing.log.json`:

```json
{
  "steps": [
    {
      "step": "pdf_extraction",
      "status": "success",
      "timestamp": "2024-01-15T10:30:00Z",
      "duration_ms": 1500,
      "error": null
    }
  ]
}
```

Status values: `pending`, `running`, `success`, `failed`, `skipped`

---

# Parallel Processing

- PDF and image processing run concurrently
- Image processing uses ThreadPoolExecutor for parallel execution
- Retry mechanism: max 3 attempts with exponential backoff
- Each worker is isolated and returns structured results

---

# DTO & Field Aliases

Standard DTO for consistent field mapping:

```python
class FieldDTO:
    canonical_name: str
    aliases: list[str]
    value: any
    confidence_score: float
    evidence: str
```

Field aliases allow mapping varying field names across projects to a canonical name.

---

# Human Approval Workflow

1.  After mapping, system generates `mapping.json`
2.  UI displays mapped values with confidence scores
3.  User can review, edit, or approve
4.  Only approved mappings proceed to auto-fill
5.  Approval status stored in `project.json`

---

# Future Improvements (After MVP)

- SQLite/PostgreSQL instead of JSON
- Background processing (Celery/RQ)
- Multiple AI model support
- Browser Extension
- Multi-user authentication
- Project versioning
- Human approval workflow
- Export to Excel/PDF
