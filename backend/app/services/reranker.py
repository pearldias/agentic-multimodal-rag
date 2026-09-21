"""Cohere Reranker service for second-stage precision ranking."""

import logging
from typing import Sequence
import cohere
from langchain_core.documents import Document

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

PLACEHOLDER_KEYS = {
    "your-cohere-api-key-here",
    "your_cohere_api_key_here",
    "placeholder",
    "<your-cohere-api-key-here>",
    "your_api_key",
    "changeme",
    "none",
}


def is_valid_cohere_key(key: str | None) -> bool:
    """Validate that the Cohere API key is present and not a known placeholder."""
    if not key or not key.strip():
        return False
    cleaned = key.strip().lower()
    if cleaned in PLACEHOLDER_KEYS or "your-cohere" in cleaned or "your_cohere" in cleaned:
        return False
    return True


class CohereRerankerService:
    """Reranks candidate document chunks using Cohere Rerank model."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else settings.COHERE_API_KEY
        self._is_enabled = is_valid_cohere_key(resolved_key)
        self.model = model or settings.COHERE_RERANK_MODEL
        self.client: cohere.ClientV2 | None = None

        if self._is_enabled and resolved_key:
            try:
                self.client = cohere.ClientV2(api_key=resolved_key.strip())
                logger.info("Initialized CohereRerankerService with model '%s'", self.model)
            except Exception as error:
                logger.warning(
                    "Failed to initialize Cohere client: %s. Reranking will be bypassed.",
                    error,
                )
                self.client = None
                self._is_enabled = False
        else:
            logger.info("COHERE_API_KEY is not configured or is a placeholder; reranking will be bypassed.")

    @property
    def is_available(self) -> bool:
        """Return True if Cohere client is successfully initialized and enabled."""
        return self._is_enabled and self.client is not None

    def rerank(
        self,
        query: str,
        documents: Sequence[Document],
        top_n: int | None = None,
    ) -> list[Document]:
        """Rerank candidate document chunks against the user query.

        Args:
            query: Search query string.
            documents: Candidate document chunks from vector store.
            top_n: Number of top reranked chunks to return. Defaults to settings.RERANK_TOP_K.

        Returns:
            list[Document]: Reranked top_n document chunks with all metadata preserved.
        """
        if not documents:
            return []

        effective_top_n = top_n if top_n is not None else settings.RERANK_TOP_K

        if not query or not query.strip():
            return list(documents[:effective_top_n])

        target_top_n = min(effective_top_n, len(documents))

        if not self.is_available:
            logger.debug(
                "Cohere reranker is not available; returning top %d chunks from vector search.",
                target_top_n,
            )
            return list(documents[:target_top_n])

        doc_texts = [doc.page_content for doc in documents]

        try:
            response = self.client.rerank(
                model=self.model,
                query=query.strip(),
                documents=doc_texts,
                top_n=target_top_n,
            )

            reranked_docs: list[Document] = []
            for item in response.results:
                original_doc = documents[item.index]
                updated_metadata = dict(original_doc.metadata or {})
                if hasattr(item, "relevance_score") and item.relevance_score is not None:
                    updated_metadata["rerank_score"] = float(item.relevance_score)

                reranked_docs.append(
                    Document(
                        page_content=original_doc.page_content,
                        metadata=updated_metadata,
                    )
                )

            return reranked_docs

        except Exception as error:
            logger.warning(
                "Cohere rerank failed (%s); falling back to top %d vector search results.",
                error,
                target_top_n,
            )
            return list(documents[:target_top_n])
