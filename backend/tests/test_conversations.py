"""Tests for SQLite conversation persistence, context management, and endpoints."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient

from backend.app.db.database import get_db_connection, init_db
from backend.app.models.conversation import MessageResponse
from backend.app.services.context_manager import ContextManager
from backend.app.services.conversation_service import ConversationService
from backend.app.services.llm_service import LLMService


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database for testing."""
    db_file = tmp_path / "test_conversations.db"
    init_db(db_file)
    return db_file


@pytest.fixture
def conv_service(test_db: Path) -> ConversationService:
    """Provide a ConversationService bound to the temporary database."""
    return ConversationService(db_path=test_db)


def test_conversation_creation_listing_loading_deletion(conv_service: ConversationService) -> None:
    """Verify conversation lifecycle: create, list, load, and delete."""
    # Create
    created = conv_service.create_conversation("Leave Policy Discussion")
    assert created.title == "Leave Policy Discussion"
    assert created.id is not None

    # List
    convs = conv_service.list_conversations()
    assert len(convs) == 1
    assert convs[0].id == created.id

    # Load detail
    detail = conv_service.get_conversation(created.id)
    assert detail is not None
    assert detail.id == created.id
    assert detail.title == "Leave Policy Discussion"
    assert len(detail.messages) == 0

    # Delete
    deleted = conv_service.delete_conversation(created.id)
    assert deleted is True
    assert conv_service.get_conversation(created.id) is None
    assert len(conv_service.list_conversations()) == 0


def test_message_persistence_and_citations(conv_service: ConversationService) -> None:
    """Verify storing user and assistant messages with source citations."""
    conv = conv_service.create_conversation("Citation Test")

    # User message
    conv_service.add_message(
        conversation_id=conv.id,
        role="user",
        content="What is the bereavement policy?",
    )

    # Assistant message with sources
    sources = [
        {
            "source_id": 1,
            "filename": "Leave_Policy.pdf",
            "page": 4,
            "page_number": 4,
            "title": "McLaren Leave Policy",
        }
    ]
    conv_service.add_message(
        conversation_id=conv.id,
        role="assistant",
        content="Bereavement leave allows up to 5 days [Source 1].",
        sources=sources,
    )

    detail = conv_service.get_conversation(conv.id)
    assert detail is not None
    assert len(detail.messages) == 2

    assert detail.messages[0].role == "user"
    assert detail.messages[0].content == "What is the bereavement policy?"
    assert detail.messages[0].sources == []

    assert detail.messages[1].role == "assistant"
    assert detail.messages[1].content == "Bereavement leave allows up to 5 days [Source 1]."
    assert len(detail.messages[1].sources) == 1
    assert detail.messages[1].sources[0]["filename"] == "Leave_Policy.pdf"
    assert detail.messages[1].sources[0]["page"] == 4


def test_cascade_deletion(conv_service: ConversationService, test_db: Path) -> None:
    """Verify deleting a conversation cascades and deletes all its messages."""
    conv = conv_service.create_conversation("Cascade Test")
    conv_service.add_message(conv.id, "user", "Hello")
    conv_service.add_message(conv.id, "assistant", "Hi there")

    # Verify messages exist in raw SQLite
    with get_db_connection(test_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?;",
            (conv.id,),
        ).fetchone()["cnt"]
        assert count == 2

    # Delete conversation
    conv_service.delete_conversation(conv.id)

    # Verify messages are gone
    with get_db_connection(test_db) as conn:
        count = conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?;",
            (conv.id,),
        ).fetchone()["cnt"]
        assert count == 0


def test_bounded_memory_window(conv_service: ConversationService) -> None:
    """Verify only the last 6 messages are returned in chronological order."""
    conv = conv_service.create_conversation("Memory Window Test")

    for i in range(1, 11):
        role = "user" if i % 2 != 0 else "assistant"
        conv_service.add_message(conv.id, role, f"Message {i}")

    # Fetch last 6 messages
    recent = conv_service.get_recent_messages(conv.id, limit=6)
    assert len(recent) == 6

    # Chronological check: Message 5 to 10
    contents = [m.content for m in recent]
    assert contents == [
        "Message 5",
        "Message 6",
        "Message 7",
        "Message 8",
        "Message 9",
        "Message 10",
    ]


def test_conversation_isolation(conv_service: ConversationService) -> None:
    """Verify conversations do not leak messages between sessions."""
    conv_a = conv_service.create_conversation("Session A")
    conv_b = conv_service.create_conversation("Session B")

    conv_service.add_message(conv_a.id, "user", "Question for A")
    conv_service.add_message(conv_b.id, "user", "Question for B")

    detail_a = conv_service.get_conversation(conv_a.id)
    detail_b = conv_service.get_conversation(conv_b.id)

    assert detail_a is not None and detail_b is not None
    assert len(detail_a.messages) == 1
    assert detail_a.messages[0].content == "Question for A"

    assert len(detail_b.messages) == 1
    assert detail_b.messages[0].content == "Question for B"


def test_contextualize_query_with_history(conv_service: ConversationService) -> None:
    """Verify ContextManager contextualizes follow-up questions when history exists."""
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.contextualize_query.return_value = "What is the employee leave policy for probation employees?"

    context_mgr = ContextManager(
        conversation_service=conv_service,
        llm_service=mock_llm,
    )

    history = [
        MessageResponse(id="1", role="user", content="What is the employee leave policy?", sources=[], created_at=""),
        MessageResponse(id="2", role="assistant", content="Employees receive 20 days paid leave.", sources=[], created_at=""),
    ]

    reformulated = context_mgr.contextualize_query("What about probation?", history)
    assert reformulated == "What is the employee leave policy for probation employees?"
    mock_llm.contextualize_query.assert_called_once()


def test_contextualize_query_graceful_fallback(conv_service: ConversationService) -> None:
    """Verify ContextManager falls back to raw question if contextualizer fails."""
    mock_llm = MagicMock(spec=LLMService)
    mock_llm.contextualize_query.side_effect = RuntimeError("API unavailable")

    context_mgr = ContextManager(
        conversation_service=conv_service,
        llm_service=mock_llm,
    )

    history = [
        MessageResponse(id="1", role="user", content="What is the leave policy?", sources=[], created_at=""),
    ]

    result = context_mgr.contextualize_query("What about probation?", history)
    # Should fall back cleanly without raising
    assert result == "What about probation?"


def test_contextualize_query_skipped_when_no_history(conv_service: ConversationService) -> None:
    """Verify ContextManager skips LLM call completely if history is empty."""
    mock_llm = MagicMock(spec=LLMService)

    context_mgr = ContextManager(
        conversation_service=conv_service,
        llm_service=mock_llm,
    )

    result = context_mgr.contextualize_query("What is the leave policy?", [])
    assert result == "What is the leave policy?"
    mock_llm.contextualize_query.assert_not_called()


def test_chat_endpoint_creates_and_persists_conversation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify POST /api/chat auto-creates conversation and returns conversation_id."""
    from backend.app.api.routes import chat

    test_db_file = tmp_path / "api_test.db"
    init_db(test_db_file)
    test_conv_svc = ConversationService(db_path=test_db_file)
    monkeypatch.setattr(chat, "conversation_service", test_conv_svc)

    mock_result = {
        "question": "What is leave policy?",
        "answer": "Leave policy is 20 days [Source 1].",
        "sources": [{"source_id": 1, "filename": "leave.pdf", "page": 1, "title": "Leave"}],
        "retrieved_documents": 1,
    }
    monkeypatch.setattr(chat.rag_service, "ask", lambda question, k, conversation_id: mock_result)

    response = client.post("/api/chat", json={"question": "What is leave policy?"})
    assert response.status_code == 200
    data = response.json()

    assert "conversation_id" in data
    conv_id = data["conversation_id"]
    assert conv_id is not None

    # Check persistence
    saved = test_conv_svc.get_conversation(conv_id)
    assert saved is not None
    assert len(saved.messages) == 2
    assert saved.messages[0].role == "user"
    assert saved.messages[0].content == "What is leave policy?"
    assert saved.messages[1].role == "assistant"
    assert len(saved.messages[1].sources) == 1


def test_chat_endpoint_with_existing_conversation_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify POST /api/chat with conversation_id appends to the same session."""
    from backend.app.api.routes import chat

    test_db_file = tmp_path / "api_test2.db"
    init_db(test_db_file)
    test_conv_svc = ConversationService(db_path=test_db_file)
    monkeypatch.setattr(chat, "conversation_service", test_conv_svc)

    conv = test_conv_svc.create_conversation("My Existing Session")

    mock_result = {
        "question": "What about probation?",
        "answer": "Probation employees get 1 day per month [Source 1].",
        "sources": [{"source_id": 1, "filename": "leave.pdf", "page": 2, "title": "Leave"}],
        "retrieved_documents": 1,
    }
    monkeypatch.setattr(chat.rag_service, "ask", lambda question, k, conversation_id: mock_result)

    response = client.post(
        "/api/chat",
        json={"question": "What about probation?", "conversation_id": conv.id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conv.id

    saved = test_conv_svc.get_conversation(conv.id)
    assert saved is not None
    assert len(saved.messages) == 2
    assert saved.messages[0].content == "What about probation?"


def test_conversation_api_routes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify GET and DELETE /api/conversations routes."""
    from backend.app.api.routes import conversations

    test_db_file = tmp_path / "routes_test.db"
    init_db(test_db_file)
    test_conv_svc = ConversationService(db_path=test_db_file)
    monkeypatch.setattr(conversations, "conversation_service", test_conv_svc)

    conv = test_conv_svc.create_conversation("Route Test Session")
    test_conv_svc.add_message(conv.id, "user", "Hello API")

    # GET /api/conversations
    res = client.get("/api/conversations")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    assert items[0]["id"] == conv.id
    assert items[0]["message_count"] == 1

    # GET /api/conversations/{id}
    res_detail = client.get(f"/api/conversations/{conv.id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert detail["title"] == "Route Test Session"
    assert len(detail["messages"]) == 1

    # DELETE /api/conversations/{id}
    res_del = client.delete(f"/api/conversations/{conv.id}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "deleted"

    # GET again -> 404
    res_not_found = client.get(f"/api/conversations/{conv.id}")
    assert res_not_found.status_code == 404
