# AI Report Automation - Task Tracker

## Project Setup

- [x] Create project directory structure (`inspection_ai/`)
- [x] Set up configuration module (`config.py`)
- [x] Create DTO/schema definitions

## Core Services

- [x] Implement `project_manager.py` - single source of truth for project data
- [x] Implement `pdf_processor.py` - PDF to image conversion and extraction
- [x] Implement `image_processor.py` - parallel image processing with retry
- [x] Implement `mapping_service.py` - field mapping with aliases
- [x] Implement `playwright_service.py` - form filling automation
- [x] Implement `review_service.py` - manual review and correction

## Features

- [x] Add confidence scoring to all extractions
- [x] Add evidence snippets to extractions
- [x] Add structured processing logs (`processing.log.json`)
- [x] Add processing status tracking
- [x] Implement parallel PDF and image processing
- [x] Add retry mechanism (max 3 attempts, exponential backoff)
- [x] Create separate JSON outputs per project:
  - [x] `document_output.json`
  - [x] `image_output.json`
  - [x] `mapping.json`
  - [x] `processing.log.json`

## UI Layer

- [x] Create Streamlit UI (`app.py`)
- [x] Dashboard screen
- [x] Upload screen
- [x] Review screen
- [x] Automation screen

## Testing

- [ ] Add unit tests for all services
- [ ] Add integration tests for end-to-end flow

## Documentation

- [x] Add top-level documentation to all modules

## Future Improvements

- [ ] SQLite/PostgreSQL storage
- [ ] Background processing (Celery/RQ)
- [ ] Multi-user authentication
