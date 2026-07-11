"""
Docling Processor - Converts PDF documents to text using docling.
"""

from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import ThreadedPdfPipelineOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions


class DoclingProcessor:
    def __init__(self):
        pipeline_options = ThreadedPdfPipelineOptions(
            do_ocr=True,
            accelerator_options=AcceleratorOptions(AcceleratorDevice.CPU),
            do_table_structure=True,
        )
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                )
            }
        )

    def export_to_text(self, pdf_path: str) -> str:
        result_doc = self.converter.convert(pdf_path)
        return result_doc.document.export_to_text()

    def convert_pdf_to_text(self, pdf_path: str) -> str:
        return self.export_to_text(pdf_path)
