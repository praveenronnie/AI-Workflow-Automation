# Quire Report Automation

## Overview

This project automates the extraction of data from PDFs and images and fills a Quire report form. The system is built around a **stand‑alone Windows executable** that bundles a local FastAPI server and an Electron UI.

## Key Components

1. **Extraction Engine** –
   - Hand‑written PDFs: Qwen‑VL‑3B OCR (text only).
   - Scanned PDFs (e.g., tax_details): Docling converts PDF to text, then OpenRouter LLM (`openai/gpt-oss-20b`) extracts all key-value pairs.
   - Images: Qwen‑VL‑3B object detection.
2. **Mapping** – Deterministic exact‑match mapping of extracted keys to Quire form fields.
3. **Form‑Filling** – Playwright script that sets form values based on the mapping.
4. **UI** – Streamlit app that shows the original document, extracted data, allows edits, and requires approval before submission.

## VLM Integration

The system now uses **Qwen2.5-VL-3B-Instruct** for both image and PDF processing:

- **Image Analysis**: Extracts room, category, view, materials, systems, objects, visible damage, overall condition, captions, and notes.
- **PDF Processing**: Converts PDF pages to PNG images (300 DPI) and extracts fields like owner name, property address, inspection date, and inspector name.

### Model Loading

The QwenVL model is loaded once via `QwenVLProvider` singleton and reused across all inference requests for efficiency.

### Redis Caching

Inference results are cached in Redis (localhost:6379) to avoid redundant processing. Cache keys are based on image path and prompt hash.

### PDF to Image Conversion

PDFs are converted to PNG images at 300 DPI using `pdf2image` and stored in the project's storage folder under `pdf_images/`.

## Workflow

1. Client uploads documents to a shared folder.
2. Async processing extracts data from PDFs and images.
3. Data is transformed into a flat dictionary via `field_transformer`.
4. User provides the Quire report URL.
5. Playwright extracts the form fields from the Quire page.
6. Mapping service maps extracted values to Quire fields.
7. On approval, the back‑end triggers Playwright to auto-fill the form.

## Installation (Windows)

```bash
# Install dependencies
pip install -r requirements.txt

# Additional system dependency for PDF conversion
# Install poppler for pdf2image
# Download from: http://blog.alivate.com.au/poppler-windows/

# Optional: Install Redis for caching
# Download from: https://github.com/tporadowski/redis-windows
```

## Usage

```bash
# Run the Streamlit UI
streamlit run inspection_ai/app.py

# Or build the executable (requires Python 3.12+ and PyInstaller)
pyinstaller --onefile --add-data "templates;templates" --add-data "static;static" main.py
```

The UI will open automatically. The client can then upload documents to the configured folder.

## Project Structure

```
inspection_ai/
├── app.py                    # Streamlit UI
├── config.py                 # Configuration settings
├── models/
│   ├── __init__.py
│   └── dto.py               # Data transfer objects
├── prompts/
│   ├── image_analysis.txt     # Prompt for image analysis
│   ├── pdf_extraction.txt     # Prompt for PDF field extraction
│   └── field_mapping.txt
├── services/
│   ├── __init__.py
│   ├── qwen_vl.py           # QwenVL wrapper class (legacy)
│   ├── qwen_vl_provider.py    # Singleton QwenVL with Redis caching
│   ├── image_processor.py     # Async parallel image processing
│   ├── image_scene_service.py # Scene understanding
│   ├── image_inspection_service.py # Inspection analysis
│   ├── pdf_processor.py       # Async PDF processing
│   ├── project_manager.py     # Project state management
│   ├── mapping_service.py     # Field mapping
│   ├── playwright_service.py    # Form filling
│   ├── review_service.py      # Review and approval
│   ├── async_extract.py       # Async Quire page extraction
│   └── field_transformer.py   # Transforms extracted data for mapping
└── storage/                  # Project data storage
```

## Extensibility

- New extraction skills can be added by implementing a module that follows the `extractor` interface.
- The mapping logic is deterministic; to support new fields, simply update the form extraction script.

## Security

- All processing occurs locally; no external network calls.
- Extraction logs are stored encrypted.

## License

MIT
