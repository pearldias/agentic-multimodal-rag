"""Custom domain exceptions for document ingestion, parsing, and validation."""


class DocumentIngestionError(Exception):
    """Base exception for all document ingestion and parsing errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedFileTypeError(DocumentIngestionError):
    """Raised when an uploaded or ingested file format is not supported."""

    def __init__(self, file_extension: str, supported: list[str] | set[str]) -> None:
        message = (
            f"Unsupported file type '{file_extension}'. "
            f"Supported extensions: {sorted(list(supported))}"
        )
        super().__init__(message)
        self.file_extension = file_extension
        self.supported = supported


class EmptyDocumentError(DocumentIngestionError):
    """Raised when a document is zero bytes or contains only whitespace/blank content."""

    def __init__(self, filename: str, reason: str = "Document contains no extractable text") -> None:
        message = f"Empty document error for '{filename}': {reason}."
        super().__init__(message)
        self.filename = filename
        self.reason = reason


class CorruptedDocumentError(DocumentIngestionError):
    """Raised when a document is corrupted, malformed, or cannot be parsed."""

    def __init__(self, filename: str, details: str = "") -> None:
        message = f"Failed to parse corrupted document '{filename}'."
        if details:
            message += f" Details: {details}"
        super().__init__(message)
        self.filename = filename
        self.details = details
