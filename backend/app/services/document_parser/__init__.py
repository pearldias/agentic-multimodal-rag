"""Document parser package exports."""

from backend.app.services.document_parser.base import BaseDocumentParser
from backend.app.services.document_parser.docx_parser import DocxParser
from backend.app.services.document_parser.normalizer import (
    format_table_as_markdown,
    normalize_legal_text,
    normalize_unicode,
    repair_hyphenation,
)
from backend.app.services.document_parser.pdf_parser import PdfParser
from backend.app.services.document_parser.service import DocumentParserService
from backend.app.services.document_parser.txt_parser import TxtParser
from backend.app.services.document_parser.xlsx_parser import XlsxParser

__all__ = [
    "BaseDocumentParser",
    "TxtParser",
    "PdfParser",
    "DocxParser",
    "XlsxParser",
    "DocumentParserService",
    "normalize_legal_text",
    "normalize_unicode",
    "repair_hyphenation",
    "format_table_as_markdown",
]
