"""Text document parser for plain text and markdown legal files."""

from datetime import datetime, timezone
from pathlib import Path
from backend.app.core.exceptions import CorruptedDocumentError, EmptyDocumentError
from backend.app.models.document import DocumentMetadata, DocumentType, ParsedDocument, ParsedPage
from backend.app.services.document_parser.base import BaseDocumentParser
from backend.app.services.document_parser.normalizer import normalize_legal_text


class TxtParser(BaseDocumentParser):
    """Parser for plain text (.txt, .md) documents."""

    @property
    def supported_extensions(self) -> set[str]:
        return {"txt", "md"}

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

        raw_content = None
        # Try UTF-8 first, fallback to common legacy encodings
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=encoding) as f:
                    raw_content = f.read()
                break
            except (UnicodeDecodeError, OSError):
                continue

        if raw_content is None:
            raise CorruptedDocumentError(path.name, details="Unable to decode file with supported encodings")

        normalized = normalize_legal_text(raw_content)
        if not normalized or not normalized.strip():
            raise EmptyDocumentError(path.name, reason="File contains only whitespace or empty content")

        timestamp = datetime.now(timezone.utc).isoformat()
        resolved_title = title or path.stem.replace("_", " ").title()

        metadata = DocumentMetadata(
            filename=path.name,
            file_type=DocumentType.TXT.value,
            title=resolved_title,
            source_url=source_url,
            ingestion_timestamp=timestamp,
            file_size_bytes=file_size,
            total_pages=1,
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
