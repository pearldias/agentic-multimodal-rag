"""Pydantic schemas for normalized parsed documents, pages, and metadata."""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported document formats for LexiRAG ingestion."""

    TXT = "txt"
    PDF = "pdf"
    DOCX = "docx"
    XLSX = "xlsx"


class DocumentMetadata(BaseModel):
    """Metadata describing an ingested document."""

    filename: str
    file_type: str
    title: str | None = None
    source_url: str | None = None
    ingestion_timestamp: str
    file_size_bytes: int | None = None
    total_pages: int = 1
    extra: dict[str, Any] = Field(default_factory=dict)


class ParsedPage(BaseModel):
    """A single page, sheet, or text unit of an ingested document."""

    text: str
    page_number: int | None = None
    sheet_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """Container representing a fully parsed, validated, and normalized document."""

    metadata: DocumentMetadata
    pages: list[ParsedPage] = Field(default_factory=list)
    raw_text: str = ""

    @property
    def filename(self) -> str:
        return self.metadata.filename

    @property
    def file_type(self) -> str:
        return self.metadata.file_type

    @property
    def total_pages(self) -> int:
        return len(self.pages)
