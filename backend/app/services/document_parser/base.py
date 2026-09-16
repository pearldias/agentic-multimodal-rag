"""Abstract base class for document parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from backend.app.models.document import ParsedDocument


class BaseDocumentParser(ABC):
    """Abstract strategy for parsing specific file types into normalized ParsedDocument structures."""

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Return the set of lower-case file extensions (without leading dot) supported by this parser."""
        pass

    @abstractmethod
    def parse(
        self,
        file_path: Path,
        source_url: str | None = None,
        title: str | None = None,
        **kwargs,
    ) -> ParsedDocument:
        """Parse the given file into a validated, normalized ParsedDocument instance.

        Args:
            file_path: Absolute or relative Path to the file.
            source_url: Optional source URL for legal citation tracking.
            title: Optional document title override.

        Returns:
            ParsedDocument: The fully parsed document containing page units and metadata.

        Raises:
            EmptyDocumentError: If document contains no extractable text.
            CorruptedDocumentError: If file is malformed or cannot be opened.
        """
        pass
