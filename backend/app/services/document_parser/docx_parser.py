"""Word (.docx) document parser for legal document ingestion."""

from datetime import datetime, timezone
from pathlib import Path
import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
from backend.app.core.exceptions import CorruptedDocumentError, EmptyDocumentError
from backend.app.models.document import DocumentMetadata, DocumentType, ParsedDocument, ParsedPage
from backend.app.services.document_parser.base import BaseDocumentParser
from backend.app.services.document_parser.normalizer import (
    format_table_as_markdown,
    normalize_legal_text,
)


class DocxParser(BaseDocumentParser):
    """Parser for DOCX documents preserving paragraph structure and embedded tables."""

    @property
    def supported_extensions(self) -> set[str]:
        return {"docx"}

    def parse(
        self,
        file_path: Path,
        source_url: str | None = None,
        title: str | None = None,
        **kwargs,
    ) -> ParsedDocument:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        file_size = path.stat().st_size
        if file_size == 0:
            raise EmptyDocumentError(path.name, reason="File is 0 bytes")

        try:
            doc = docx.Document(str(path))
        except Exception as exc:
            raise CorruptedDocumentError(path.name, details=str(exc)) from exc

        # Extract title from core properties if available
        doc_title = title
        if not doc_title and doc.core_properties:
            doc_title = doc.core_properties.title
        if not doc_title or not doc_title.strip():
            doc_title = path.stem.replace("_", " ").title()

        content_blocks: list[str] = []

        # Iterate over XML body elements to preserve sequential reading order of paragraphs and tables
        for child in doc.element.body:
            if child.tag.endswith("p"):
                para = Paragraph(child, doc)
                text = para.text.strip()
                if text:
                    content_blocks.append(text)
            elif child.tag.endswith("tbl"):
                tbl = Table(child, doc)
                rows_data = []
                for row in tbl.rows:
                    row_cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                    rows_data.append(row_cells)
                if rows_data:
                    headers = rows_data[0]
                    body_rows = rows_data[1:] if len(rows_data) > 1 else []
                    md_table = format_table_as_markdown(headers, body_rows)
                    if md_table:
                        content_blocks.append(md_table)

        combined_raw = "\n\n".join(content_blocks)
        normalized = normalize_legal_text(combined_raw)

        if not normalized or not normalized.strip():
            raise EmptyDocumentError(path.name, reason="DOCX contains no extractable text or tables")

        timestamp = datetime.now(timezone.utc).isoformat()
        metadata = DocumentMetadata(
            filename=path.name,
            file_type=DocumentType.DOCX.value,
            title=doc_title.strip(),
            source_url=source_url,
            ingestion_timestamp=timestamp,
            file_size_bytes=file_size,
            total_pages=1,
            extra={
                "author": doc.core_properties.author if doc.core_properties else None,
                "created": (
                    doc.core_properties.created.isoformat()
                    if doc.core_properties and doc.core_properties.created
                    else None
                ),
            },
        )

        page = ParsedPage(
            text=normalized,
            page_number=1,
            metadata={"filename": path.name, "page_number": 1},
        )

        return ParsedDocument(
            metadata=metadata,
            pages=[page],
            raw_text=normalized,
        )
