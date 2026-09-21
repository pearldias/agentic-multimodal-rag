from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from google.genai import errors

from backend.app.services.llm_service import (
    LLMService,
    LLMUnavailableError,
    LLMRateLimitError,
)


def test_chat_endpoint_empty_question_returns_400(client: TestClient) -> None:
    """Verify POST /api/chat with empty question returns 400."""
    response = client.post("/api/chat", json={"question": "   "})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_chat_endpoint_success_returns_expected_structure(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify POST /api/chat returns answer, sources, and retrieved_documents."""
    from backend.app.api.routes import chat

    mock_result = {
        "question": "What is the policy?",
        "answer": "The employee leave policy includes 20 days paid leave [Source 1].",
        "sources": [
            {
                "source_id": 1,
                "filename": "HR_Policy.pdf",
                "page": 5,
                "page_number": 5,
                "title": "HR Policy",
            }
        ],
        "retrieved_documents": 1,
    }

    monkeypatch.setattr(chat.rag_service, "ask", lambda question, k: mock_result)

    response = client.post("/api/chat", json={"question": "What is the policy?"})
    assert response.status_code == 200

    data = response.json()
    assert data["question"] == "What is the policy?"
    assert data["answer"] == mock_result["answer"]
    assert len(data["sources"]) == 1
    assert data["sources"][0]["filename"] == "HR_Policy.pdf"
    assert data["retrieved_documents"] == 1


def test_chat_endpoint_gemini_503_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify POST /api/chat returns 503 with informative detail on Gemini unavailability."""
    from backend.app.api.routes import chat

    def raise_503(question: str, k: int):
        raise LLMUnavailableError(
            "The Gemini AI service is temporarily experiencing high demand (503 Service Unavailable). Please try again in a moment."
        )

    monkeypatch.setattr(chat.rag_service, "ask", raise_503)

    response = client.post("/api/chat", json={"question": "What is the policy?"})
    assert response.status_code == 503
    assert "503 Service Unavailable" in response.json()["detail"]


def test_chat_endpoint_gemini_rate_limit_returns_429(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify POST /api/chat returns 429 when rate limit is exceeded."""
    from backend.app.api.routes import chat

    def raise_429(question: str, k: int):
        raise LLMRateLimitError(
            "Gemini API rate limit exceeded. Please wait a moment and try again."
        )

    monkeypatch.setattr(chat.rag_service, "ask", raise_429)

    response = client.post("/api/chat", json={"question": "What is the policy?"})
    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()


def test_llm_service_retries_on_503_and_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMService retries on 503 and returns the answer when a subsequent attempt succeeds."""
    llm = LLMService(max_retries=3, retry_delay=0.01)

    calls = 0

    def mock_generate_content(model: str, contents: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise errors.ServerError(503, {"error": {"code": 503, "message": "High demand"}})
        mock_resp = MagicMock()
        mock_resp.text = "Grounded response after retry."
        return mock_resp

    monkeypatch.setattr(llm.client.models, "generate_content", mock_generate_content)

    answer = llm.generate_answer("What is X?", "Context about X")
    assert calls == 2
    assert answer == "Grounded response after retry."


def test_llm_service_exhausted_retries_raises_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify LLMService raises LLMUnavailableError when all 503 retries are exhausted."""
    llm = LLMService(max_retries=2, retry_delay=0.01)

    def mock_generate_content_fail(model: str, contents: str):
        raise errors.ServerError(503, {"error": {"code": 503, "message": "High demand"}})

    monkeypatch.setattr(llm.client.models, "generate_content", mock_generate_content_fail)

    with pytest.raises(LLMUnavailableError) as exc_info:
        llm.generate_answer("What is X?", "Context about X")

    assert exc_info.value.status_code == 503
    assert "503 Service Unavailable" in exc_info.value.message
