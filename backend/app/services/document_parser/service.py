"""Document parser service orchestrating file parsing, validation, normalization, and persistence."""

import json
import logging
from pathlib import Path
from uuid import uuid4
from backend.app.core.config import settings
from backend.app.core.exceptions import UnsupportedFileTypeError
from backend.app.models.document import ParsedDocument
from backend.app.services.document_parser.base import BaseDocumentParser
from backend.app.services.document_parser.docx_parser import DocxParser
from backend.app.services.document_parser.pdf_parser import PdfParser
from backend.app.services.document_parser.txt_parser import TxtParser
from backend.app.services.document_parser.xlsx_parser import XlsxParser

logger = logging.getLogger(__name__)


class DocumentParserService:
    """Central service for parsing, validating, and managing legal documents."""

    def __init__(self, parsers: list[BaseDocumentParser] | None = None) -> None:
        """Initialize parser registry with supported document formats."""
        self._parsers: dict[str, BaseDocumentParser] = {}

        default_parsers = parsers or [
            TxtParser(),
            PdfParser(),
            DocxParser(),
            XlsxParser(),
        ]
        for parser in default_parsers:
            self.register_parser(parser)

    def register_parser(self, parser: BaseDocumentParser) -> None:
        """Register a parser for its supported extensions."""
        for ext in parser.supported_extensions:
            self._parsers[ext.lower()] = parser

    @property
    def supported_extensions(self) -> set[str]:
        """Return the set of all registered file extensions."""
        return set(self._parsers.keys())

    @staticmethod
    def ensure_data_directories() -> None:
        """Explicitly create data/raw, data/processed, and data/metadata storage folders.

        Adheres to clean startup semantics: directories are only created when this method
        is explicitly called by an ingestion or setup workflow.
        """
        settings.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        settings.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        settings.METADATA_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("Ensured data directories exist at %s", settings.DATA_DIR)

    def parse_file(
        self,
        file_path: str | Path,
        source_url: str | None = None,
        title: str | None = None,
        save: bool = False,
    ) -> ParsedDocument:
        """Validate, route, and parse a legal document into a normalized ParsedDocument.

        Args:
            file_path: Path to the target document.
            source_url: Optional origin URL for legal citation tracking.
            title: Optional document title override.
            save: If True, persists processed document and metadata JSON to disk.

        Returns:
            ParsedDocument: The validated and normalized document.

        Raises:
            FileNotFoundError: If the file does not exist on disk.
            UnsupportedFileTypeError: If the file extension is not supported.
            EmptyDocumentError: If document contains no readable text.
            CorruptedDocumentError: If document is malformed or unreadable.
        """
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        # Extract lower-case extension without leading dot
        suffix = path.suffix.lstrip(".").lower()
        if not suffix or suffix not in self._parsers:
            raise UnsupportedFileTypeError(suffix or "none", self.supported_extensions)

        parser = self._parsers[suffix]
        logger.info("Parsing '%s' using %s", path.name, parser.__class__.__name__)

        parsed_doc = parser.parse(path, source_url=source_url, title=title)

        if save:
            self.save_parsed_document(parsed_doc)

        return parsed_doc

    def save_parsed_document(
        self,
        parsed_doc: ParsedDocument,
        doc_id: str | None = None,
    ) -> tuple[Path, Path]:
        """Persist parsed document and its metadata to data/processed and data/metadata.

        Args:
            parsed_doc: The ParsedDocument instance to persist.
            doc_id: Unique identifier for file naming (defaults to UUID4).

        Returns:
            tuple[Path, Path]: (processed_file_path, metadata_file_path)
        """
        self.ensure_data_directories()
        identifier = doc_id or f"{Path(parsed_doc.filename).stem}_{uuid4().hex[:8]}"

        processed_path = settings.PROCESSED_DATA_DIR / f"{identifier}.json"
        metadata_path = settings.METADATA_DIR / f"{identifier}_meta.json"

        with open(processed_path, "w", encoding="utf-8") as f:
            json.dump(parsed_doc.model_dump(), f, indent=2, ensure_ascii=False)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(parsed_doc.metadata.model_dump(), f, indent=2, ensure_ascii=False)

        logger.info("Saved processed document to %s and metadata to %s", processed_path, metadata_path)
        return processed_path, metadata_path
