import os
import pytest
from backend.app.core.config import settings
from backend.app.services.embedding import (
    EmbeddingService,
    is_valid_api_key,
)

# Detect if a valid API key exists in environment or settings
_HAS_VALID_KEY = is_valid_api_key(settings.GOOGLE_API_KEY or os.getenv("GOOGLE_API_KEY"))


@pytest.mark.integration
@pytest.mark.skipif(
    not _HAS_VALID_KEY,
    reason="GOOGLE_API_KEY is not configured or is a placeholder; skipping live Gemini API test.",
)
def test_live_gemini_embedding_query_and_documents() -> None:
    """Live integration test against Google Gemini API.

    Verifies embedding 1 query and 2 documents, ensuring every returned
    vector has exactly 768 dimensions and contains valid float values.
    """
    service = EmbeddingService()

    # 1. Embed one query
    query_text = "What is retrieval-augmented generation in artificial intelligence?"
    query_vector = service.embed_query(query_text)

    assert isinstance(query_vector, list)
    assert len(query_vector) == 768
    assert all(isinstance(val, float) for val in query_vector)

    # 2. Embed two documents
    documents = [
        "Retrieval-Augmented Generation grounds large language models with dynamic knowledge retrieval.",
        "Vector embeddings represent semantic meanings of textual chunks in a continuous vector space.",
    ]
    doc_vectors = service.embed_documents(documents)

    assert isinstance(doc_vectors, list)
    assert len(doc_vectors) == 2

    # Verify each document embedding vector
    for idx, vec in enumerate(doc_vectors):
        assert isinstance(vec, list), f"Document {idx} embedding is not a list"
        assert len(vec) == 768, f"Document {idx} embedding dimension is {len(vec)}, expected 768"
        assert all(isinstance(val, float) for val in vec), f"Document {idx} vector elements must be floats"
