"""
Docling Processor - Converts PDF documents to text using docling.
"""

import hashlib
import logging
import re
from datetime import datetime

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions, EasyOcrOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions

from docling.chunking import HybridChunker
from docling_core.transforms.chunker.hierarchical_chunker import (
    ChunkingDocSerializer,
    ChunkingSerializerProvider,
)
from docling_core.transforms.serializer.plain_text import PlainTextParams


from uuid import uuid4

logger = logging.getLogger(__name__)

# Pipeline options for local CPU processing
LOCAL_PIPELINE_OPTIONS = PdfPipelineOptions(
    do_ocr=True,
    ocr_options=EasyOcrOptions(
        lang=["en"],
        use_gpu=False,
    ),
    do_chart_extraction=True,
    do_table_structure=True,
    generate_page_images=True,
    generate_picture_images=True,
)


class DoclingProcessor:
    def __init__(self):

        pipeline_options = PdfPipelineOptions(
            do_ocr=True,
            ocr_options=EasyOcrOptions(
                lang=["en"],
                use_gpu=True,
            ),
            accelerator_options=AcceleratorOptions(AcceleratorDevice.CUDA),
            do_chart_extraction=True,
            do_table_structure=True,
            generate_page_images=True,
            generate_picture_images=True,
        )
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

        class TraversePicturesProvider(ChunkingSerializerProvider):
            def get_serializer(self, doc):
                params = PlainTextParams(traverse_pictures=True)
                return ChunkingDocSerializer(doc=doc, params=params)

        self.chunker = HybridChunker(serializer_provider=TraversePicturesProvider())

    def grid_to_rows(self, grid):
        if not grid:
            return [], []

        headers = [cell.text.strip() for cell in grid[0]]
        rows = [
            {header: cell.text.strip() for header, cell in zip(headers, row)}
            for row in grid[1:]
        ]
        return headers, rows

    def extract_single_table(self, grid):
        if not grid:
            return None
        is_key_value = (
            len(grid) > 1
            and len(grid[1]) == 2
            and (len(grid[0]) == 1 or any(cell.col_span > 1 for cell in grid[0]))
        )

        if is_key_value:
            title = grid[0][0].text.strip() if grid[0] else None

            data = {}

            for row in grid[1:]:
                if len(row) < 2:
                    continue
                key = row[0].text.strip()
                value = row[1].text.strip()

                if key:
                    data[key] = value
            return {"table_type": "key_value", "title": title, "data": data}

        headers, rows = self.grid_to_rows(grid)
        return {"table_type": "dataset", "headers": headers, "table_data": rows}

    def extract_table_data(self, docling_doc):
        table_data = []
        tables = docling_doc.tables
        if tables:
            for table in docling_doc.tables:
                extracted = self.extract_single_table(table.data.grid)

                if extracted:
                    table_data.append(extracted)
        return table_data

    def extract_chart_data(self, docling_doc):
        chart_data = []

        for idx, img in enumerate(docling_doc.pictures or []):
            try:
                # Picture itself
                if img is None:
                    logger.debug("Picture[%s]: None", idx)
                    continue

                # Metadata
                meta = getattr(img, "meta", None)
                if meta is None:
                    logger.debug("Picture[%s]: meta=None", idx)
                    continue

                # Classification
                classification = getattr(meta, "classification", None)
                if classification is None:
                    logger.debug("Picture[%s]: classification=None", idx)
                    continue

                # Predictions
                predictions = getattr(classification, "predictions", None)
                if not predictions:
                    logger.debug("Picture[%s]: predictions=None/empty", idx)
                    continue

                # First prediction
                prediction = predictions[0]
                if prediction is None:
                    logger.debug("Picture[%s]: prediction[0]=None", idx)
                    continue

                # Class name
                class_name = getattr(prediction, "class_name", None)
                if not class_name:
                    logger.debug("Picture[%s]: class_name=None", idx)
                    continue

                # Only process supported charts
                if class_name not in {
                    "line_chart",
                    "bar_chart",
                    "pie_chart",
                }:
                    logger.debug(
                        "Picture[%s]: Skipping non-chart type '%s'",
                        idx,
                        class_name,
                    )
                    continue

                # Tabular chart
                tabular_chart = getattr(meta, "tabular_chart", None)
                if tabular_chart is None:
                    logger.debug("Picture[%s]: tabular_chart=None", idx)
                    continue

                # Chart grid
                chart_grid = getattr(tabular_chart, "chart_data", None)
                if chart_grid is None:
                    logger.debug("Picture[%s]: chart_data=None", idx)
                    continue

                if not chart_grid.grid:
                    logger.debug("Picture[%s]: chart grid empty", idx)
                    continue

                headers, rows = self.grid_to_rows(chart_grid.grid)

                chart_data.append(
                    {
                        "chart_type": class_name,
                        "headers": headers,
                        "chart_data": rows,
                    }
                )

            except Exception as e:
                logger.exception(
                    "Failed to process picture[%s]: %s",
                    idx,
                    str(e),
                )
                continue

        logger.info("Extracted %d charts.", len(chart_data))

        return chart_data

    def clean_text(self, text):
        PUA_PATTERN = re.compile(r"[\uE000-\uF8FF]")
        text = PUA_PATTERN.sub("", text)
        text = " ".join(text.split())
        return text

    def extract_text(self, docling_doc):
        text_list = []
        for t in docling_doc.texts:
            text = self.clean_text(t.text)
            if text != "":
                text_list.append(text)
        text_doc = "\n".join(text_list)

        return text_doc

    def extract_scanned_pdf(self, pdf_path: str, report_id: str):
        logger.info("extract_scanned_pdf — path=%s, report_id=%s", pdf_path, report_id)

        result_doc = self.converter.convert(pdf_path)
        docling_doc = result_doc.document

        return self._extract(docling_doc)

    def extract_raw_texts(
        self,
        pdf_path: str,
        report_id: str = None,
        file_id: str = None,
        file_name: str = None,
        file_hash: str = None,
        user_id: str = None,
    ) -> dict:
        logger.info(
            "extract_raw_texts — path=%s, report_id=%s, file_id=%s",
            pdf_path,
            report_id,
            file_id,
        )

        result_doc = self.converter.convert(pdf_path)
        docling_doc = result_doc.document

        chunk_data = []
        chunks = self.chunker.chunk(docling_doc)

        for c in chunks:
            content = c.text
            chunk_content_hash = hashlib.sha256(content.encode()).hexdigest()
            page_no = list(set(p.page_no for p in c.meta.doc_items[0].prov))

            chunk_data.append(
                {
                    "chunk_id": str(uuid4()),
                    "report_id": report_id,
                    "file_id": file_id,
                    "file_name": file_name,
                    "section": c.meta.headings,
                    "page_no": page_no,
                    "content": content,
                    "chunk_content_hash": chunk_content_hash,
                }
            )

        return {
            "file_metadata": {
                "file_id": file_id,
                "file_name": file_name,
                "file_hash": file_hash,
                "report_id": report_id,
                "user_id": user_id,
                "total_pages": len(docling_doc.pages),
                "processed_at": datetime.utcnow().isoformat(),
            },
            "chunks": chunk_data,
        }
