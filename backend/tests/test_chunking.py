from backend.app.models.document import (
    DocumentMetadata,
    ParsedDocument,
    ParsedPage,
)
from backend.app.services.chunking import ChunkingService


def create_test_document() -> ParsedDocument:
    metadata = DocumentMetadata(
        filename="test_policy.pdf",
        file_type="pdf",
        title="Test Policy",
        ingestion_timestamp="2026-09-17T00:00:00Z",
    )

    return ParsedDocument(
        metadata=metadata,
        pages=[
            ParsedPage(
                text=(
                    "This is a sample policy document. "
                    "It contains information about company procedures. "
                    "Employees must follow the documented procedures. "
                )
                * 30,
                page_number=1,
            )
        ],
    )


def test_document_is_split_into_chunks() -> None:
    document = create_test_document()
    service = ChunkingService(
        chunk_size=200,
        chunk_overlap=30,
    )

    chunks = service.chunk_document(document)

    assert len(chunks) > 1
    assert all(chunk.text.strip() for chunk in chunks)


def test_chunks_contain_source_metadata() -> None:
    document = create_test_document()
    service = ChunkingService()

    chunks = service.chunk_document(document)

    assert chunks
    assert chunks[0].metadata["filename"] == "test_policy.pdf"
    assert chunks[0].metadata["file_type"] == "pdf"
    assert chunks[0].metadata["page_number"] == 1


def test_empty_pages_are_skipped() -> None:
    metadata = DocumentMetadata(
        filename="empty.pdf",
        file_type="pdf",
        ingestion_timestamp="2026-09-17T00:00:00Z",
    )

    document = ParsedDocument(
        metadata=metadata,
        pages=[
            ParsedPage(
                text="   ",
                page_number=1,
            )
        ],
    )

    service = ChunkingService()

    chunks = service.chunk_document(document)

    assert chunks == []