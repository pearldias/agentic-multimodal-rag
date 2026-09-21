"""Text chunking service for parsed RAG documents."""

from dataclasses import dataclass
from typing import Any

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.models.document import ParsedDocument


@dataclass
class DocumentChunk:
    """A text chunk with metadata used for retrieval and citations."""

    chunk_id: str
    text: str
    metadata: dict[str, Any]


class ChunkingService:
    """Split parsed documents into smaller overlapping text chunks."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 150,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero.")

        if chunk_overlap < 0:
            raise ValueError("chunk_overlap cannot be negative.")

        if chunk_overlap >= chunk_size:
            raise ValueError(
                "chunk_overlap must be smaller than chunk_size."
            )

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                " ",
                "",
            ],
        )

    def chunk_document(
        self,
        document: ParsedDocument,
    ) -> list[DocumentChunk]:
        """Split a parsed document into chunks with source metadata."""

        chunks: list[DocumentChunk] = []

        for page_index, page in enumerate(document.pages):
            if not page.text or not page.text.strip():
                continue

            page_chunks = self._splitter.split_text(page.text)

            for chunk_index, text in enumerate(page_chunks):
                chunk_id = (
                    f"{document.filename}"
                    f"__page_{page.page_number or page_index + 1}"
                    f"__chunk_{chunk_index + 1}"
                )

                metadata = {
                    "filename": document.filename,
                    "file_type": document.file_type,
                    "title": document.metadata.title,
                    "page_number": page.page_number,
                    "sheet_name": page.sheet_name,
                    "chunk_index": chunk_index,
                }

                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        text=text,
                        metadata=metadata,
                    )
                )

        return chunks