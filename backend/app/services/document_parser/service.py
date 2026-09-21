"""Document parser service orchestrating file parsing, validation, normalization, and persistence."""

import json
import logging
from pathlib import Path

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

    def __init__(
        self,
        parsers: list[BaseDocumentParser] | None = None,
    ) -> None:
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
        for extension in parser.supported_extensions:
            self._parsers[extension.lower()] = parser

    @property
    def supported_extensions(self) -> set[str]:
        """Return the set of all registered file extensions."""
        return set(self._parsers.keys())

    @staticmethod
    def ensure_data_directories() -> None:
        """Create the required data storage directories."""
        settings.RAW_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        settings.PROCESSED_DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        settings.METADATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            "Ensured data directories exist at %s",
            settings.DATA_DIR,
        )

    def parse_file(
        self,
        file_path: str | Path,
        source_url: str | None = None,
        title: str | None = None,
        save: bool = False,
    ) -> ParsedDocument:
        """Validate, route, and parse a document.

        Args:
            file_path: Path to the target document.
            source_url: Optional origin URL for legal citation tracking.
            title: Optional document title override.
            save: If True, persist the processed document and metadata.

        Returns:
            ParsedDocument: The validated and normalized document.

        Raises:
            FileNotFoundError: If the document does not exist.
            UnsupportedFileTypeError: If the extension is unsupported.
            EmptyDocumentError: If the document contains no readable text.
            CorruptedDocumentError: If the document is malformed.
        """
        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"File not found: {path}"
            )

        suffix = path.suffix.lstrip(".").lower()

        if not suffix or suffix not in self._parsers:
            raise UnsupportedFileTypeError(
                suffix or "none",
                self.supported_extensions,
            )

        parser = self._parsers[suffix]

        logger.info(
            "Parsing '%s' using %s",
            path.name,
            parser.__class__.__name__,
        )

        parsed_document = parser.parse(
            path,
            source_url=source_url,
            title=title,
        )

        if save:
            self.save_parsed_document(parsed_document)

        return parsed_document

    def save_parsed_document(
        self,
        parsed_doc: ParsedDocument,
        doc_id: str | None = None,
    ) -> tuple[Path, Path]:
        """Persist a parsed document and its metadata.

        A stable filename based on the source document is used by default.
        This prevents duplicate files from being created when ingestion is
        executed multiple times.

        Args:
            parsed_doc: The ParsedDocument instance to persist.
            doc_id: Optional custom identifier for file naming.

        Returns:
            A tuple containing:
                - processed document path
                - metadata document path
        """
        self.ensure_data_directories()

        if doc_id:
            identifier = doc_id
        else:
            identifier = Path(parsed_doc.filename).stem

        processed_path = (
            settings.PROCESSED_DATA_DIR
            / f"{identifier}.json"
        )

        metadata_path = (
            settings.METADATA_DIR
            / f"{identifier}_meta.json"
        )

        with processed_path.open(
            "w",
            encoding="utf-8",
        ) as processed_file:
            json.dump(
                parsed_doc.model_dump(),
                processed_file,
                indent=2,
                ensure_ascii=False,
            )

        with metadata_path.open(
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(
                parsed_doc.metadata.model_dump(),
                metadata_file,
                indent=2,
                ensure_ascii=False,
            )

        logger.info(
            "Saved processed document to %s and metadata to %s",
            processed_path,
            metadata_path,
        )

        return processed_path, metadata_path