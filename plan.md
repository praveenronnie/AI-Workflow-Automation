# Refactoring Plan

## Issues Identified

1. **Duplicate code**: `qwen_vl.py` and `qwen_vl_provider.py` have nearly identical `_run_inference`, `_parse_response`, and `_normalize_response` methods
2. **Unnecessary abstraction**: `image_scene_service.py` and `image_inspection_service.py` are thin wrappers that just call the provider
3. **Over-engineered DTOs**: `dto.py` dataclasses with `to_dict()` are redundant - can use plain dicts
4. **Duplicate JS code**: `async_extract.py` and `playwright_service.py` have similar field extraction JavaScript
5. **Inline documentation**: Should be removed per user request
6. **Unused imports**: Some files have unused imports
7. **Hardcoded credentials**: Quire email and password were hardcoded in extract.py

## Completed Refactoring Steps

- [x] Remove `qwen_vl.py` (keep `qwen_vl_provider.py` as it's more feature-rich)
- [x] Simplify `image_scene_service.py` and `image_inspection_service.py` - merge into `image_processor.py`
- [x] Simplify `dto.py` - removed inline documentation
- [x] Remove duplicate code in `async_extract.py` and `playwright_service.py` - created shared `playwright_js.py`
- [x] Clean up imports and remove inline documentation
- [x] Update `__init__.py` files
- [x] Update `qwen_vl_test.py` to use `QwenVLProvider`
- [x] Update `extract.py` to use shared JavaScript and environment variables
- [x] Update `docling_processor.py` - removed inline documentation
- [x] Update `llm_extractor.py` - removed inline documentation
- [x] Update `review_service.py` - removed inline documentation
- [x] Update `field_transformer.py` - removed inline documentation
- [x] Update `mapping_service.py` - removed inline documentation
- [x] Update `pdf_processor.py` - removed inline documentation
- [x] Update `project_manager.py` - removed inline documentation
- [x] Update `app.py` - removed inline documentation, moved imports to top
- [x] Add Quire credentials to `.env` and `.env.example` files

## Summary of Changes

### Files Removed (3 files)

- `qwen_vl.py` - duplicate of `qwen_vl_provider.py`
- `image_scene_service.py` - merged into `image_processor.py`
- `image_inspection_service.py` - merged into `image_processor.py`

### Files Created (1 file)

- `playwright_js.py` - Shared JavaScript for field extraction (DRY principle)

### Files Modified (16 files)

- `qwen_vl_provider.py` - Removed inline documentation
- `image_processor.py` - Simplified to use single inference call instead of two
- `qwen_vl_test.py` - Updated to test `QwenVLProvider`
- `extract.py` - Uses shared JavaScript and environment variables for credentials
- `docling_processor.py` - Removed inline documentation
- `llm_extractor.py` - Removed inline documentation
- `review_service.py` - Removed inline documentation
- `field_transformer.py` - Removed inline documentation
- `mapping_service.py` - Removed inline documentation
- `pdf_processor.py` - Removed inline documentation
- `project_manager.py` - Removed inline documentation
- `async_extract.py` - Uses shared JavaScript
- `playwright_service.py` - Uses shared JavaScript
- `app.py` - Removed inline documentation, moved imports to top
- `.env` - Added Quire credentials
- `.env.example` - Added Quire credentials template

### Key Improvements

1. **Eliminated duplicate code** - Removed redundant `qwen_vl.py` and merged image services
2. **DRY principle** - Created shared `playwright_js.py` for JavaScript used in multiple places
3. **Single inference call** - `image_processor.py` now makes one call instead of two
4. **Cleaner code** - Removed inline documentation, kept only file-level docstrings
5. **All imports at top** - Reorganized imports to be at the top of each file
6. **Environment variables** - Quire credentials now use environment variables instead of hardcoded values
