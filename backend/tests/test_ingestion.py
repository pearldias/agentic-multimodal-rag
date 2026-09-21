from pathlib import Path

from backend.app.services.chunking import ChunkingService
from backend.app.services.ingestion import IngestionService
from backend.app.services.vector_store import VectorStoreService


class FakeEmbeddingService:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


def test_ingestion_service_can_be_created() -> None:
    service = IngestionService()

    assert service.parser_service is not None
    assert service.chunking_service is not None


def test_ingestion_directory_returns_summary(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(
        "This is a sample document for ingestion testing.",
        encoding="utf-8",
    )

    service = IngestionService()

    result = service.ingest_directory(
        directory=tmp_path,
        save=False,
    )

    assert result["total_files"] == 1
    assert result["successful_files"] == 1
    assert result["failed_files"] == 0
    assert result["results"][0]["filename"] == "sample.txt"


def test_ingestion_stores_chunks_in_vector_store(tmp_path: Path) -> None:
    sample_file = tmp_path / "sample.txt"
    sample_file.write_text(
        "This document contains information about software engineering.",
        encoding="utf-8",
    )

    vector_store = VectorStoreService(
        persist_directory=tmp_path / "chroma",
        collection_name="test_ingestion_collection",
        embedding_service=FakeEmbeddingService(),
    )

    service = IngestionService(
        vector_store_service=vector_store,
    )

    result = service.ingest_file(
        file_path=sample_file,
        save=False,
    )

    assert result["processed"] is True
    assert len(result["chunks"]) > 0
    assert result["stored_chunks"] == len(result["chunks"])
    assert vector_store.count() == len(result["chunks"])