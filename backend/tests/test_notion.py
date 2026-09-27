"""Unit and integration tests for Notion MCP client and FastAPI endpoints."""

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from backend.app.main import app
from mcp_server.notion_client import JsonFileTokenStorage, NotionMCPClient, get_notion_client


@pytest.fixture
def temp_token_file(tmp_path: Path) -> Path:
    return tmp_path / "test_notion_tokens.json"


@pytest.fixture
def storage(temp_token_file: Path) -> JsonFileTokenStorage:
    return JsonFileTokenStorage(temp_token_file)


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# TokenStorage Tests
# ---------------------------------------------------------------------------

def test_token_storage_empty(storage: JsonFileTokenStorage):
    """Test reading from empty token storage."""
    async def _test():
        assert await storage.get_tokens() is None
        assert await storage.get_client_info() is None
        assert storage.is_authenticated() is False
    asyncio.run(_test())


def test_token_storage_save_and_retrieve(storage: JsonFileTokenStorage):
    """Test saving and loading OAuth tokens and client info."""
    async def _test():
        token = OAuthToken(
            access_token="test_access_token_123",
            token_type="Bearer",
            expires_in=3600,
            refresh_token="test_refresh_token_456",
            scope="default",
        )
        await storage.set_tokens(token)

        loaded_token = await storage.get_tokens()
        assert loaded_token is not None
        assert loaded_token.access_token == "test_access_token_123"
        assert loaded_token.refresh_token == "test_refresh_token_456"
        assert storage.is_authenticated() is True

        # Test client info
        client_info = OAuthClientInformationFull(
            client_id="test_client_id",
            client_secret="test_secret",
        )
        await storage.set_client_info(client_info)

        loaded_client = await storage.get_client_info()
        assert loaded_client is not None
        assert loaded_client.client_id == "test_client_id"
        assert loaded_client.client_secret == "test_secret"
    asyncio.run(_test())


def test_token_storage_clear(storage: JsonFileTokenStorage):
    """Test clearing token storage."""
    async def _test():
        token = OAuthToken(access_token="abc", token_type="Bearer")
        await storage.set_tokens(token)
        assert storage.is_authenticated() is True

        storage.clear()
        assert storage.is_authenticated() is False
        assert await storage.get_tokens() is None
    asyncio.run(_test())


# ---------------------------------------------------------------------------
# NotionMCPClient Logic Tests
# ---------------------------------------------------------------------------

def test_client_initialization(temp_token_file: Path):
    """Test NotionMCPClient configuration and initialization."""
    client = NotionMCPClient(
        server_url="https://mcp.notion.com/mcp",
        redirect_uri="http://localhost:8000/api/notion/callback",
        token_path=temp_token_file,
    )
    status = client.get_status()
    assert status["server_url"] == "https://mcp.notion.com/mcp"
    assert status["redirect_uri"] == "http://localhost:8000/api/notion/callback"
    assert status["authenticated"] is False


def test_tool_name_resolution(temp_token_file: Path):
    """Test tool name normalization and resolution against server tool names."""
    client = NotionMCPClient(token_path=temp_token_file)
    available_tools = ["notion-create-pages", "query_data_sources", "fetch"]

    assert client._resolve_tool_name("fetch", available_tools) == "fetch"
    assert client._resolve_tool_name("create_pages", available_tools) == "notion-create-pages"
    assert client._resolve_tool_name("query-data-sources", available_tools) == "query_data_sources"
    assert client._resolve_tool_name("unknown_tool", available_tools) == "unknown_tool"


# ---------------------------------------------------------------------------
# FastAPI Route Tests
# ---------------------------------------------------------------------------

def test_api_notion_status(test_client: TestClient):
    """Test GET /api/notion/status returns valid diagnostic payload."""
    response = test_client.get("/api/notion/status")
    assert response.status_code == 200
    data = response.json()
    assert "authenticated" in data
    assert "server_url" in data
    assert "redirect_uri" in data
    assert "token_path" in data


def test_api_notion_callback_missing_params(test_client: TestClient):
    """Test GET /api/notion/callback returns 400 when code or state is missing."""
    response = test_client.get("/api/notion/callback")
    assert response.status_code == 400
    assert "Missing required" in response.text


def test_api_notion_callback_error(test_client: TestClient):
    """Test GET /api/notion/callback with error returns 400 HTML page."""
    response = test_client.get("/api/notion/callback?error=access_denied&error_description=User+declined")
    assert response.status_code == 400
    assert "Authorization Failed" in response.text
    assert "access_denied" in response.text


def test_api_notion_callback_success(test_client: TestClient):
    """Test GET /api/notion/callback with valid code and state."""
    response = test_client.get("/api/notion/callback?code=mock_code_123&state=mock_state_456")
    assert response.status_code == 200
    assert "Notion Connected Successfully" in response.text


def test_api_notion_meeting_notes_validation(test_client: TestClient):
    """Test POST /api/notion/meeting-notes validates request body."""
    response = test_client.post("/api/notion/meeting-notes", json={})
    assert response.status_code == 422


def test_prepare_token_auth_rfc6749_single_method():
    """Verify that prepare_token_auth removes client_id from body when Basic auth is used (RFC 6749 §2.3.1)."""
    from mcp.client.auth.oauth2 import OAuthContext
    from mcp.shared.auth import OAuthClientInformationFull

    ctx = OAuthContext(
        server_url="https://mcp.notion.com/mcp",
        client_metadata=MagicMock(redirect_uris=["http://localhost:8000/api/notion/callback"]),
        storage=MagicMock(),
        redirect_handler=None,
        callback_handler=None,
    )
    ctx.client_info = OAuthClientInformationFull(
        client_id="test_client_id",
        client_secret="test_secret",
        token_endpoint_auth_method="client_secret_basic",
    )

    token_data = {
        "grant_type": "authorization_code",
        "code": "test_code",
        "redirect_uri": "http://localhost:8000/api/notion/callback",
        "client_id": "test_client_id",
        "code_verifier": "test_verifier",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    data, updated_headers = ctx.prepare_token_auth(token_data, headers)

    assert "Authorization" in updated_headers
    assert updated_headers["Authorization"].startswith("Basic ")
    assert "client_secret" not in data
    assert "client_id" not in data  # MUST NOT be included in body alongside Basic auth
    assert data["grant_type"] == "authorization_code"
    assert data["code"] == "test_code"
    assert data["code_verifier"] == "test_verifier"


def test_api_notion_tools_success(test_client: TestClient):
    """Test GET /api/notion/tools returns tools list and dynamic count."""
    mock_tools = [
        {"name": "notion-search", "description": "Search workspace", "inputSchema": {}},
        {"name": "notion-create-pages", "description": "Create pages", "inputSchema": {}},
    ]
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_tools = AsyncMock(return_value=mock_tools)
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tools")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["tools"]) == 2
        assert data["tools"][0]["name"] == "notion-search"


def test_api_notion_tools_error(test_client: TestClient):
    """Test GET /api/notion/tools returns 502 on MCP server error."""
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.list_tools = AsyncMock(side_effect=RuntimeError("MCP connection failed"))
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tools")
        assert response.status_code == 502
        assert "Failed to communicate with Notion MCP server" in response.json()["detail"]


def test_api_notion_tasks_success(test_client: TestClient):
    """Test GET /api/notion/tasks queries tasks dynamically via NotionMCPClient."""
    mock_tasks = [
        {
            "id": "task-1",
            "name": "Complete RAG Kubernetes setup",
            "status": "In progress",
            "priority": "High",
            "due_date": "2026-09-24",
            "url": "https://app.notion.com/task-1",
        },
        {
            "id": "task-2",
            "name": "Review React website",
            "status": "Done",
            "priority": "Medium",
            "due_date": "2026-09-25",
            "url": "https://app.notion.com/task-2",
        },
    ]
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.query_daily_tasks = AsyncMock(return_value=mock_tasks)
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tasks")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["name"] == "Complete RAG Kubernetes setup"
        assert data["tasks"][0]["priority"] == "High"
        mock_instance.query_daily_tasks.assert_called_once()


def test_api_notion_tasks_error(test_client: TestClient):
    """Test GET /api/notion/tasks returns 502 when MCP client fails."""
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.query_daily_tasks = AsyncMock(side_effect=Exception("Database query failed"))
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tasks")
        assert response.status_code == 502
        assert "Failed to query Notion tasks" in response.json()["detail"]


def test_api_notion_meeting_notes_success(test_client: TestClient):
    """Test POST /api/notion/meeting-notes creates a page via MCP tool."""
    mock_result = {
        "tool": "notion-create-pages",
        "is_error": False,
        "content": [
            {
                "pages": [
                    {
                        "id": "page-123",
                        "url": "https://app.notion.com/p/page-123",
                        "properties": {"title": "Architecture Sync"},
                    }
                ]
            }
        ],
    }
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.create_meeting_notes_page = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_instance

        payload = {
            "title": "Architecture Sync",
            "content": "## Agenda\n- MCP Integration",
            "icon": "📝",
        }
        response = test_client.post("/api/notion/meeting-notes", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["page_id"] == "page-123"
        assert data["page_url"] == "https://app.notion.com/p/page-123"
        mock_instance.create_meeting_notes_page.assert_called_once_with(
            title="Architecture Sync",
            content="## Agenda\n- MCP Integration",
            parent_page_id=None,
            parent_database_id=None,
            icon="📝",
        )


def test_api_notion_meeting_notes_tool_error(test_client: TestClient):
    """Test POST /api/notion/meeting-notes handles Notion MCP tool execution error."""
    mock_result = {
        "tool": "notion-create-pages",
        "is_error": True,
        "error": "Notion API permission denied",
    }
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.create_meeting_notes_page = AsyncMock(return_value=mock_result)
        mock_get_client.return_value = mock_instance

        payload = {"title": "Denied Notes"}
        response = test_client.post("/api/notion/meeting-notes", json=payload)
        assert response.status_code == 400
        assert "Notion page creation failed" in response.json()["detail"]


# ---------------------------------------------------------------------------
# Task Details Endpoint & Client Tests
# ---------------------------------------------------------------------------

def test_api_notion_task_details_success(test_client: TestClient):
    """Test GET /api/notion/tasks/{page_id} returns structured task details."""
    mock_task_details = {
        "id": "3e58c53d-f08d-8043-9315-e9678a600be8",
        "title": "Complete RAG Kubernetes setup",
        "name": "Complete RAG Kubernetes setup",
        "url": "https://app.notion.com/p/3e58c53df08d80439315e9678a600be8",
        "status": "In progress",
        "priority": "High",
        "due_date": "2026-09-24",
        "due_date_end": None,
        "last_edited_at": "2026-09-24T06:21:16.703Z",
        "path": "Daily Task",
        "cover": None,
        "icon": None,
        "properties": {
            "Name": "Complete RAG Kubernetes setup",
            "priority": "High",
            "status": "In progress",
        },
        "content": "Setup helm charts and ingress controller.",
        "is_error": False,
    }
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.get_task_details = AsyncMock(return_value=mock_task_details)
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tasks/3e58c53d-f08d-8043-9315-e9678a600be8")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "3e58c53d-f08d-8043-9315-e9678a600be8"
        assert data["title"] == "Complete RAG Kubernetes setup"
        assert data["status"] == "In progress"
        assert data["priority"] == "High"
        assert data["content"] == "Setup helm charts and ingress controller."
        mock_instance.get_task_details.assert_called_once_with("3e58c53d-f08d-8043-9315-e9678a600be8")


def test_api_notion_task_details_empty_id(test_client: TestClient):
    """Test GET /api/notion/tasks/{page_id} returns 400 when page_id is only whitespace."""
    response = test_client.get("/api/notion/tasks/%20")
    assert response.status_code == 400
    assert "must not be empty" in response.json()["detail"]


def test_api_notion_task_details_not_found(test_client: TestClient):
    """Test GET /api/notion/tasks/{page_id} returns 404 when Notion page is not found."""
    mock_not_found = {
        "id": "non-existent-id",
        "is_error": True,
        "error": "Page non-existent-id not found in Notion workspace",
    }
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.get_task_details = AsyncMock(return_value=mock_not_found)
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tasks/non-existent-id")
        assert response.status_code == 404
        assert "Failed to fetch Notion task" in response.json()["detail"]


def test_api_notion_task_details_server_error(test_client: TestClient):
    """Test GET /api/notion/tasks/{page_id} returns 502 when MCP client fails."""
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.get_task_details = AsyncMock(side_effect=Exception("MCP connection error"))
        mock_get_client.return_value = mock_instance

        response = test_client.get("/api/notion/tasks/test-task-id")
        assert response.status_code == 502
        assert "Failed to communicate with Notion MCP" in response.json()["detail"]


def test_client_get_task_details_parsing(temp_token_file: Path):
    """Test NotionMCPClient.get_task_details properly parses XML and JSON properties."""
    client = NotionMCPClient(token_path=temp_token_file)

    sample_fetch_xml = (
        'Here is the result of "fetch" for the Page with URL https://app.notion.com/p/test123:\n'
        '<page url="https://app.notion.com/p/test123">\n'
        '<ancestor-path>\n'
        '<parent-data-source url="collection://abc" name="Daily Task"/>\n'
        '</ancestor-path>\n'
        '<properties>\n'
        '{"Name":"Test Task Title","priority":"High","status":"In progress","date:due date:start":"2026-09-25","url":"https://app.notion.com/p/test123"}\n'
        '</properties>\n'
        '<iconMetadata>null</iconMetadata>\n'
        'Detailed notes on this task body.\n'
        '</page>'
    )

    mock_tool_result = {
        "tool": "fetch",
        "is_error": False,
        "content": [{"text": sample_fetch_xml}],
    }

    client.call_tool = AsyncMock(return_value=mock_tool_result)

    async def _run():
        res = await client.get_task_details("test123")
        assert res["is_error"] is False
        assert res["title"] == "Test Task Title"
        assert res["status"] == "In progress"
        assert res["priority"] == "High"
        assert res["due_date"] == "2026-09-25"
        assert res["url"] == "https://app.notion.com/p/test123"
        assert "Detailed notes on this task body." in res["content"]
        assert client.call_tool.called

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Dedicated Notion Assistant Chat Tests
# ---------------------------------------------------------------------------

def test_api_notion_chat_success(test_client: TestClient):
    """Test POST /api/notion/chat answers Notion questions using MCP data and LLM."""
    mock_tasks = [
        {
            "id": "task-1",
            "name": "Read LanGraph Documentation",
            "status": "In progress",
            "priority": "Medium",
            "due_date": "2026-09-26",
            "url": "https://app.notion.com/p/task-1",
        }
    ]
    mock_details = {
        "id": "task-1",
        "title": "Read LanGraph Documentation",
        "status": "In progress",
        "priority": "Medium",
        "due_date": "2026-09-26",
        "content": "Next steps: 1. Read docs, 2. Build 2-node graph",
        "description": "LangGraph tutorial task",
        "url": "https://app.notion.com/p/task-1",
    }

    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client, \
         patch("backend.app.services.llm_service.LLMService") as mock_llm_cls:

        mock_instance = MagicMock()
        mock_instance.query_daily_tasks = AsyncMock(return_value=mock_tasks)
        mock_instance.get_task_details = AsyncMock(return_value=mock_details)
        mock_instance.call_tool = AsyncMock(return_value={"content": [{"results": []}]})
        mock_get_client.return_value = mock_instance

        mock_llm_inst = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "The Read LanGraph Documentation task is currently In progress with Medium priority."
        mock_llm_inst.client.models.generate_content.return_value = mock_response
        mock_llm_inst.model = "gemini-2.5-flash"
        mock_llm_cls.return_value = mock_llm_inst

        payload = {"question": "What tasks are currently in progress?"}
        response = test_client.post("/api/notion/chat", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["question"] == "What tasks are currently in progress?"
        assert "In progress" in data["answer"]
        assert len(data["referenced_tasks"]) == 1
        assert data["referenced_tasks"][0]["name"] == "Read LanGraph Documentation"


def test_api_notion_chat_empty_question(test_client: TestClient):
    """Test POST /api/notion/chat returns 400 on empty question."""
    response = test_client.post("/api/notion/chat", json={"question": "   "})
    assert response.status_code == 400
    assert "Question cannot be empty" in response.json()["detail"]


def test_api_notion_chat_mcp_failure(test_client: TestClient):
    """Test POST /api/notion/chat returns 502 when MCP client query fails."""
    with patch("backend.app.api.routes.notion.get_notion_client") as mock_get_client:
        mock_instance = MagicMock()
        mock_instance.query_daily_tasks = AsyncMock(side_effect=Exception("MCP connection timed out"))
        mock_get_client.return_value = mock_instance

        payload = {"question": "What tasks are in progress?"}
        response = test_client.post("/api/notion/chat", json=payload)
        assert response.status_code == 502
        assert "Notion Assistant encountered an error" in response.json()["detail"]


