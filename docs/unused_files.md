# Unused Files and Folders Reference

This document lists files and folders that are **no longer used** after the refactoring of `processing/` into `inspection_ai/services/`.

**Important**: Do NOT delete these files yet. They are kept for verification and rollback purposes.

---

## Migrated from processing/ to inspection_ai/services/

These files have been migrated and their code now lives in `inspection_ai/services/`. The originals are no longer imported or used by the main application.

| Original File                       | New Location                                             | Status             |
| ----------------------------------- | -------------------------------------------------------- | ------------------ |
| `processing/ocr_process.py`         | `inspection_ai/services/ocr_pdf_processor.py`            | ❗ Ready to remove |
| `processing/handwritten_process.py` | `inspection_ai/services/handwritten_pdf_processor.py`    | ❗ Ready to remove |
| `processing/image_process.py`       | `inspection_ai/services/image_processor.py`              | ❗ Ready to remove |
| `processing/pdf_aggregator.py`      | `inspection_ai/services/aggregators/pdf_aggregator.py`   | ❗ Ready to remove |
| `processing/image_aggregator.py`    | `inspection_ai/services/aggregators/image_aggregator.py` | ❗ Ready to remove |
| `processing/pca_aggregator.py`      | `inspection_ai/services/aggregators/pca_aggregator.py`   | ❗ Ready to remove |
| `processing/vector_store.py`        | `inspection_ai/services/vector_store.py`                 | ❗ Ready to remove |
| `processing/retriever.py`           | `inspection_ai/services/retriever.py`                    | ❗ Ready to remove |
| `processing/embeddings.py`          | `inspection_ai/services/embeddings.py`                   | ❗ Ready to remove |

---

## Potentially Unused (Reference Only)

These files exist in `processing/` but were NOT part of the main API flow and have no direct migration target.

| File                            | Reason                                                                                   |
| ------------------------------- | ---------------------------------------------------------------------------------------- |
| `processing/debugging.ipynb`    | Debug notebook, not part of application                                                  |
| `processing/api_form_mapper.py` | Legacy form mapping script, used only by `/map/form-fields` endpoint which is deprecated |
| `processing/form_mapper.py`     | Old form mapping logic, superseded by `mapping_service.py`                               |
| `processing/llm_client.py`      | Legacy client, superseded by `inspection_ai/services/llm_client.py`                      |
| `processing/pdf_models.py`      | Pydantic models for old PDF processing                                                   |
| `processing/models/`            | Model artifacts folder                                                                   |
| `inspection_ai/app.py`          | Legacy Streamlit UI using old PDFProcessor/ImageProcessor constructor signatures         |

---

## Not to be Removed (Explicitly Preserved)

| Path                                          | Reason                                                         |
| --------------------------------------------- | -------------------------------------------------------------- |
| `json_extraction/`                            | All JSON output files must be preserved                        |
| `data/`                                       | Configuration and data files (chunks, indices, mapping config) |
| `inspection_ai/services/pdf_processor.py`     | Updated to delegate to new processors (interface kept)         |
| `inspection_ai/services/docling_processor.py` | Updated with EasyOCR options + raw text extraction             |

---

## Verified Removals After Testing

Run the following before permanently deleting migrated files:

```bash
# Verify imports resolve correctly
python -c "from inspection_ai.services.ocr_pdf_processor import OCRPDFProcessor"
python -c "from inspection_ai.services.handwritten_pdf_processor import HandwrittenPDFProcessor"
python -c "from inspection_ai.services.image_processor import ImageProcessor"
python -c "from inspection_ai.services.vector_store import VectorStore"
python -c "from inspection_ai.services.retriever import retrieve_for_field"
```

Then safely remove:

```bash
rm processing/ocr_process.py
rm processing/handwritten_process.py
rm processing/image_process.py
rm processing/pdf_aggregator.py
rm processing/image_aggregator.py
rm processing/pca_aggregator.py
rm processing/vector_store.py
rm processing/retriever.py
rm processing/embeddings.py
```

---

## Notes

- The `processing/__init__.py` file can also be removed once all files above are deleted.
- The `processing/__pycache__/` directory will be cleaned automatically.
- After verification, the `processing/` folder can be entirely deleted or preserved as archive.
