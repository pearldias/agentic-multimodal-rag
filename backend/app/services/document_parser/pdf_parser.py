"""PDF document parser using PyMuPDF (fitz) for legal document ingestion."""

from datetime import datetime, timezone
from pathlib import Path
import fitz  # PyMuPDF
from backend.app.core.exceptions import CorruptedDocumentError, EmptyDocumentError
from backend.app.models.document import DocumentMetadata, DocumentType, ParsedDocument, ParsedPage
from backend.app.services.document_parser.base import BaseDocumentParser
from backend.app.services.document_parser.normalizer import normalize_legal_text


class PdfParser(BaseDocumentParser):
    """Parser for PDF files using PyMuPDF with page-level text extraction."""

    @property
    def supported_extensions(self) -> set[str]:
        return {"pdf"}

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
            doc = fitz.open(str(path))
        except Exception as exc:
            raise CorruptedDocumentError(path.name, details=str(exc)) from exc

        try:
            if doc.page_count == 0:
                raise EmptyDocumentError(path.name, reason="PDF contains 0 pages")

            pdf_meta = doc.metadata or {}
            extracted_title = title or pdf_meta.get("title")
            if not extracted_title or not extracted_title.strip():
                extracted_title = path.stem.replace("_", " ").title()

            pages: list[ParsedPage] = []
            consolidated_texts: list[str] = []

            for page_idx in range(doc.page_count):
                page_num = page_idx + 1
                page = doc.load_page(page_idx)
                raw_page_text = page.get_text("text") or ""
                normalized_page_text = normalize_legal_text(raw_page_text)

                if normalized_page_text:
                    pages.append(
                        ParsedPage(
                            text=normalized_page_text,
                            page_number=page_num,
                            metadata={
                                "filename": path.name,
                                "page_number": page_num,
                                "total_pages": doc.page_count,
                            },
                        )
                    )
                    consolidated_texts.append(normalized_page_text)

            if not pages or not consolidated_texts:
                raise EmptyDocumentError(
                    path.name,
                    reason="PDF contains no extractable text (file may be scanned or empty)",
                )

            timestamp = datetime.now(timezone.utc).isoformat()
            metadata = DocumentMetadata(
                filename=path.name,
                file_type=DocumentType.PDF.value,
                title=extracted_title.strip(),
                source_url=source_url,
                ingestion_timestamp=timestamp,
                file_size_bytes=file_size,
                total_pages=doc.page_count,
                extra={
                    "author": pdf_meta.get("author"),
                    "subject": pdf_meta.get("subject"),
                    "creation_date": pdf_meta.get("creationDate"),
                },
            )

            raw_text = "\n\n".join(consolidated_texts)

            return ParsedDocument(
                metadata=metadata,
                pages=pages,
                raw_text=raw_text,
            )
        finally:
            doc.close()
