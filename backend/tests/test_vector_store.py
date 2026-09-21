from pathlib import Path

from backend.app.services.chunking import DocumentChunk
from backend.app.services.vector_store import VectorStoreService


class FakeEmbeddingService:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        embeddings = []

        for text in texts:
            if "software engineering" in text.lower():
                embeddings.append([1.0, 0.0, 0.0])
            else:
                embeddings.append([0.0, 1.0, 0.0])

        return embeddings

    def embed_query(self, text: str) -> list[float]:
        if "software engineering" in text.lower():
            return [1.0, 0.0, 0.0]

        return [0.0, 1.0, 0.0]

def test_vector_store_can_be_created(tmp_path: Path) -> None:
    service = VectorStoreService(
        persist_directory=tmp_path / "chroma",
        collection_name="test_collection",
    )

    assert service.vector_store is not None
    assert service.count() == 0


def test_vector_store_can_add_chunks(tmp_path: Path) -> None:
    service = VectorStoreService(
        persist_directory=tmp_path / "chroma",
        collection_name="test_add_collection",
        embedding_service=FakeEmbeddingService(),
    )

    chunks = [
        DocumentChunk(
            chunk_id="test_chunk_1",
            text="McLaren provides software engineering services.",
            metadata={
                "document_id": "DOC_001",
                "document_name": "test.pdf",
                "page_number": 1,
                "chunk_index": 0,
            },
        )
    ]

    added_count = service.add_chunks(chunks)

    assert added_count == 1
    assert service.count() == 1

def test_vector_store_can_search_chunks(tmp_path: Path) -> None:
    service = VectorStoreService(
        persist_directory=tmp_path / "chroma",
        collection_name="test_search_collection",
        embedding_service=FakeEmbeddingService(),
    )

    chunks = [
        DocumentChunk(
            chunk_id="test_chunk_1",
            text="McLaren provides software engineering services.",
            metadata={
                "document_id": "DOC_001",
                "document_name": "test.pdf",
                "page_number": 1,
                "chunk_index": 0,
            },
        ),
        DocumentChunk(
            chunk_id="test_chunk_2",
            text="Employees can request work from home.",
            metadata={
                "document_id": "DOC_002",
                "document_name": "policy.pdf",
                "page_number": 2,
                "chunk_index": 0,
            },
        ),
    ]

    service.add_chunks(chunks)

    results = service.similarity_search(
        query="software engineering",
        k=1,
    )

    assert len(results) == 1
    assert results[0].page_content == (
        "McLaren provides software engineering services."
    )