"""ChromaDB vector store service."""

from pathlib import Path
from typing import Any

from langchain_chroma import Chroma
from langchain_core.documents import Document

from backend.app.core.config import settings
from backend.app.services.chunking import DocumentChunk
from backend.app.services.embedding import EmbeddingService


class GeminiEmbeddingAdapter:
    """Adapt the existing EmbeddingService to LangChain's embedding interface."""

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self.embedding_service = embedding_service

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedding_service.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embedding_service.embed_query(text)


class VectorStoreService:
    """Store and search document chunks using ChromaDB."""

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection_name: str = "mclaren_documents",
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.persist_directory = Path(
            persist_directory or settings.DATA_DIR / "chroma"
        )

        self.persist_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.collection_name = collection_name

        self.embedding_service = embedding_service or EmbeddingService()

        self.embedding_adapter = GeminiEmbeddingAdapter(
            self.embedding_service
        )

        self.vector_store = Chroma(
            collection_name=self.collection_name,
            embedding_function=self.embedding_adapter,
            persist_directory=str(self.persist_directory),
        )

    def add_chunks(
        self,
        chunks: list[DocumentChunk],
    ) -> int:
        """Add document chunks and metadata to ChromaDB."""

        if not chunks:
            return 0

        documents = [
            Document(
                page_content=chunk.text,
                metadata=chunk.metadata,
            )
            for chunk in chunks
        ]

        ids = [chunk.chunk_id for chunk in chunks]

        self.vector_store.add_documents(
            documents=documents,
            ids=ids,
        )

        return len(documents)

    def similarity_search(
        self,
        query: str,
        k: int = 5,
    ) -> list[Document]:
        """Retrieve the most relevant chunks for a query."""

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if k <= 0:
            raise ValueError("k must be greater than zero.")

        return self.vector_store.similarity_search(
            query=query,
            k=k,
        )

    def count(self) -> int:
        """Return the number of stored chunks."""

        collection = self.vector_store._collection
        return collection.count()

    def delete_by_filename(self, filename: str) -> None:
        """Remove any existing chunks for a document filename."""

        if not filename or not filename.strip():
            return

        try:
            self.vector_store._collection.delete(where={"filename": filename})
        except Exception:
            pass