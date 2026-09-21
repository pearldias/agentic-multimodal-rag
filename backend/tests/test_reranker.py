from unittest.mock import MagicMock
import pytest
from langchain_core.documents import Document

from backend.app.services.reranker import (
    CohereRerankerService,
    is_valid_cohere_key,
)
from backend.app.services.rag_service import RAGService


def test_is_valid_cohere_key():
    """Verify placeholder and invalid keys are properly identified."""
    assert not is_valid_cohere_key(None)
    assert not is_valid_cohere_key("")
    assert not is_valid_cohere_key("   ")
    assert not is_valid_cohere_key("your-cohere-api-key-here")
    assert not is_valid_cohere_key("placeholder")
    assert not is_valid_cohere_key("changeme")
    assert is_valid_cohere_key("real_api_key_123456789")


def test_reranker_init_missing_or_placeholder_key(monkeypatch: pytest.MonkeyPatch):
    """Verify reranker handles missing or placeholder keys gracefully without throwing."""
    monkeypatch.setattr("backend.app.services.reranker.settings.COHERE_API_KEY", None)
    reranker_none = CohereRerankerService()
    assert not reranker_none.is_available
    assert reranker_none.client is None

    reranker_ph = CohereRerankerService(api_key="your-cohere-api-key-here")
    assert not reranker_ph.is_available
    assert reranker_ph.client is None

    reranker_empty = CohereRerankerService(api_key="")
    assert not reranker_empty.is_available
    assert reranker_empty.client is None


def test_rerank_returns_fallback_when_disabled():
    """Verify rerank falls back to top_n vector search results when reranker is not enabled."""
    reranker = CohereRerankerService(api_key="")
    assert not reranker.is_available

    docs = [
        Document(page_content="First doc", metadata={"id": 1}),
        Document(page_content="Second doc", metadata={"id": 2}),
        Document(page_content="Third doc", metadata={"id": 3}),
    ]

    result = reranker.rerank("any query", docs, top_n=2)
    assert len(result) == 2
    assert result[0].page_content == "First doc"
    assert result[1].page_content == "Second doc"


def test_rerank_empty_inputs():
    """Verify handling of empty documents or empty queries."""
    reranker = CohereRerankerService(api_key="")

    assert reranker.rerank("query", []) == []

    docs = [Document(page_content="Doc", metadata={})]
    assert len(reranker.rerank("", docs, top_n=1)) == 1


def test_rerank_successful_reordering(monkeypatch: pytest.MonkeyPatch):
    """Verify reranker reorders candidate chunks according to Cohere relevance scores."""
    mock_client_instance = MagicMock()
    mock_client_cls = MagicMock(return_value=mock_client_instance)
    monkeypatch.setattr("backend.app.services.reranker.cohere.ClientV2", mock_client_cls)

    reranker = CohereRerankerService(api_key="mock_valid_key", model="rerank-v4.0-fast")

    docs = [
        Document(
            page_content="General company introduction and services.",
            metadata={"filename": "doc1.pdf", "page": 1, "title": "Overview"},
        ),
        Document(
            page_content="Employees receive 20 days of planned annual leave.",
            metadata={"filename": "doc2.pdf", "page": 2, "title": "Leave Policy"},
        ),
        Document(
            page_content="Sick leave provides 10 days per calendar year.",
            metadata={"filename": "doc3.pdf", "page": 3, "title": "Sick Leave"},
        ),
    ]

    # Mock Cohere ClientV2 response
    mock_item_1 = MagicMock()
    mock_item_1.index = 1
    mock_item_1.relevance_score = 0.98

    mock_item_2 = MagicMock()
    mock_item_2.index = 2
    mock_item_2.relevance_score = 0.85

    mock_response = MagicMock()
    mock_response.results = [mock_item_1, mock_item_2]

    mock_client_instance.rerank.return_value = mock_response

    reranked = reranker.rerank(
        query="What is the employee leave policy?",
        documents=docs,
        top_n=2,
    )

    assert len(reranked) == 2
    # doc2 should be ranked 1st
    assert reranked[0].page_content == "Employees receive 20 days of planned annual leave."
    assert reranked[0].metadata["filename"] == "doc2.pdf"
    assert reranked[0].metadata["page"] == 2
    assert reranked[0].metadata["title"] == "Leave Policy"
    assert reranked[0].metadata["rerank_score"] == 0.98

    # doc3 should be ranked 2nd
    assert reranked[1].page_content == "Sick leave provides 10 days per calendar year."
    assert reranked[1].metadata["filename"] == "doc3.pdf"
    assert reranked[1].metadata["page"] == 3
    assert reranked[1].metadata["rerank_score"] == 0.85

    mock_client_instance.rerank.assert_called_once_with(
        model="rerank-v4.0-fast",
        query="What is the employee leave policy?",
        documents=[doc.page_content for doc in docs],
        top_n=2,
    )


def test_rerank_handles_api_failure_with_fallback(monkeypatch: pytest.MonkeyPatch):
    """Verify reranker catches Cohere API exceptions and gracefully falls back to vector order."""
    mock_client_instance = MagicMock()
    mock_client_instance.rerank.side_effect = RuntimeError("Cohere API rate limit exceeded")
    mock_client_cls = MagicMock(return_value=mock_client_instance)
    monkeypatch.setattr("backend.app.services.reranker.cohere.ClientV2", mock_client_cls)

    reranker = CohereRerankerService(api_key="mock_valid_key")

    docs = [
        Document(page_content="Candidate 1", metadata={"id": 1}),
        Document(page_content="Candidate 2", metadata={"id": 2}),
        Document(page_content="Candidate 3", metadata={"id": 3}),
    ]

    # Should not raise; should return top_n unreranked
    fallback = reranker.rerank("leave policy", docs, top_n=2)
    assert len(fallback) == 2
    assert fallback[0].page_content == "Candidate 1"
    assert fallback[1].page_content == "Candidate 2"


def test_rag_service_integration_with_reranker():
    """Verify RAGService queries vector store with candidate pool and reranks to top k."""
    mock_vector_store = MagicMock()
    # Mock vector store returning 15 candidate docs
    candidates = [
        Document(page_content=f"Content {i}", metadata={"filename": f"file_{i}.pdf", "page_number": i, "title": f"Doc {i}"})
        for i in range(15)
    ]
    mock_vector_store.similarity_search.return_value = candidates

    mock_reranker = MagicMock()
    # Mock reranker selecting top 4
    mock_reranker.rerank.side_effect = lambda query, documents, top_n: documents[:top_n]

    mock_llm = MagicMock()
    mock_llm.generate_answer.return_value = "Mocked answer based on context."

    rag = RAGService(
        vector_store=mock_vector_store,
        llm_service=mock_llm,
        reranker=mock_reranker,
    )

    result = rag.answer_question("What is leave policy?", k=4)

    # Verify vector store was called with initial candidate pool (>= 12)
    mock_vector_store.similarity_search.assert_called_once()
    call_args = mock_vector_store.similarity_search.call_args
    assert call_args[1]["k"] >= 12

    # Verify reranker was called with candidates and top_n = 4
    mock_reranker.rerank.assert_called_once_with(
        query="What is leave policy?",
        documents=candidates,
        top_n=4,
    )

    assert result["retrieved_documents"] == 4
    assert len(result["sources"]) == 4
    assert result["sources"][0]["filename"] == "file_0.pdf"
    assert result["sources"][0]["page"] == 0
    assert result["sources"][0]["page_number"] == 0
