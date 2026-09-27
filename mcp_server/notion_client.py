"""Notion MCP Client implementation using official MCP Python SDK v2.

This module provides a reusable Notion MCP client that:
- Connects to the Notion MCP server (https://mcp.notion.com/mcp) using Streamable HTTP.
- Handles OAuth 2.0 + PKCE authentication via official OAuthClientProvider.
- Manages secure local file-based token storage outside git.
- Supports browser-based authorization redirects and callback handling.
- Exposes tools discovery, execution, Daily Task database querying,
  and meeting notes page creation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import sys
import webbrowser
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx2
from mcp.client.auth.oauth2 import OAuthClientProvider, OAuthContext, TokenStorage

# RFC 6749 §2.3.1 compliance patch for MCP SDK 2.2.0:
# When using HTTP Basic authentication (client_secret_basic), the client transmits credentials
# via the 'Authorization' header. RFC 6749 §2.3.1 states that the client MUST NOT also include
# the 'client_id' parameter in the request body. MCP SDK 2.2.0 removes 'client_secret' from
# the body but leaves 'client_id', causing Notion's token endpoint to reject the request with
# 'Client must not use multiple authentication methods'. This patch strips 'client_id' from the body
# whenever Basic auth is present.
_orig_prepare_token_auth = OAuthContext.prepare_token_auth


def _rfc6749_safe_prepare_token_auth(
    self: OAuthContext,
    data: dict[str, str],
    headers: dict[str, str] | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    data, headers = _orig_prepare_token_auth(self, data, headers)
    if headers and "Authorization" in headers and headers["Authorization"].startswith("Basic "):
        data = {k: v for k, v in data.items() if k not in ("client_id", "client_secret")}
    return data, headers


OAuthContext.prepare_token_auth = _rfc6749_safe_prepare_token_auth

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client
from mcp.shared.auth import (
    AuthorizationCodeResult,
    OAuthClientInformationFull,
    OAuthClientMetadata,
    OAuthToken,
)
import mcp.types as mcp_types
from pydantic.networks import AnyUrl

try:
    from backend.app.core.config import settings
except ImportError:
    # Fallback if executed standalone outside backend context
    settings = None

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Token Storage Implementation
# ---------------------------------------------------------------------------

class JsonFileTokenStorage:
    """Persistent JSON file-based token storage implementing the MCP TokenStorage protocol.

    Stores client registration metadata and OAuth tokens in a local JSON file.
    Uses atomic writes to prevent file corruption.
    """

    def __init__(self, file_path: Path | str) -> None:
        self.file_path = Path(file_path).resolve()
        self._lock = asyncio.Lock()

    def _read_data(self) -> dict[str, Any]:
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Could not read token storage file %s: %s", self.file_path, exc)
            return {}

    def _write_data(self, data: dict[str, Any]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.file_path)
        except Exception as exc:
            logger.error("Failed to write token storage to %s: %s", self.file_path, exc)
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            raise

    async def get_tokens(self) -> OAuthToken | None:
        """Retrieve stored OAuth tokens."""
        async with self._lock:
            data = self._read_data()
            tokens_data = data.get("tokens")
            if not tokens_data:
                return None
            try:
                return OAuthToken.model_validate(tokens_data)
            except Exception as exc:
                logger.warning("Failed to validate stored tokens: %s", exc)
                return None

    async def set_tokens(self, tokens: OAuthToken) -> None:
        """Store OAuth tokens."""
        async with self._lock:
            data = self._read_data()
            data["tokens"] = tokens.model_dump(mode="json")
            self._write_data(data)
            logger.info("Notion OAuth tokens successfully saved to %s", self.file_path)

    async def get_client_info(self) -> OAuthClientInformationFull | None:
        """Retrieve stored dynamic client registration info."""
        async with self._lock:
            data = self._read_data()
            client_data = data.get("client_info")
            if not client_data:
                return None
            try:
                return OAuthClientInformationFull.model_validate(client_data)
            except Exception as exc:
                logger.warning("Failed to validate stored client info: %s", exc)
                return None

    async def set_client_info(self, client_info: OAuthClientInformationFull) -> None:
        """Store dynamic client registration info."""
        async with self._lock:
            data = self._read_data()
            data["client_info"] = client_info.model_dump(mode="json")
            self._write_data(data)
            logger.info("Notion OAuth client registration info saved to %s", self.file_path)

    def is_authenticated(self) -> bool:
        """Synchronously check if access token exists in storage."""
        data = self._read_data()
        tokens = data.get("tokens")
        return bool(tokens and tokens.get("access_token"))

    def clear(self) -> None:
        """Remove stored tokens and credentials."""
        if self.file_path.exists():
            try:
                self.file_path.unlink()
                logger.info("Cleared Notion token storage: %s", self.file_path)
            except Exception as exc:
                logger.warning("Failed to remove token file %s: %s", self.file_path, exc)


# ---------------------------------------------------------------------------
# Notion MCP Client Implementation
# ---------------------------------------------------------------------------

class NotionMCPClient:
    """Reusable Notion MCP Client for interacting with Notion through the Model Context Protocol.

    Handles:
    - MCP connection via Streamable HTTP (https://mcp.notion.com/mcp).
    - OAuth 2.0 PKCE flow with OAuthClientProvider.
    - Automatic token persistence and refresh.
    - Tool discovery and generic tool execution.
    - Querying Notion databases (e.g. Daily Tasks).
    - Page creation (e.g. meeting notes).
    """

    def __init__(
        self,
        server_url: str | None = None,
        redirect_uri: str | None = None,
        client_name: str | None = None,
        token_path: Path | str | None = None,
        daily_tasks_db_id: str | None = None,
        auto_open_browser: bool = True,
    ) -> None:
        # Resolve configuration from settings or sensible defaults
        base_dir = Path(settings.BASE_DIR) if settings else Path.cwd()

        self.server_url = server_url or (
            getattr(settings, "NOTION_MCP_URL", "https://mcp.notion.com/mcp")
            if settings
            else "https://mcp.notion.com/mcp"
        )
        self.redirect_uri = redirect_uri or (
            getattr(settings, "NOTION_REDIRECT_URI", "http://localhost:8000/api/notion/callback")
            if settings
            else "http://localhost:8000/api/notion/callback"
        )
        self.client_name = client_name or (
            getattr(settings, "NOTION_CLIENT_NAME", "Agentic RAG Notion Client")
            if settings
            else "Agentic RAG Notion Client"
        )

        if token_path:
            self.token_path = Path(token_path)
        elif settings and getattr(settings, "NOTION_TOKEN_PATH", None):
            self.token_path = base_dir / settings.NOTION_TOKEN_PATH
        else:
            self.token_path = base_dir / "data" / ".notion_auth.json"

        self.daily_tasks_db_id = daily_tasks_db_id or (
            getattr(settings, "NOTION_DAILY_TASKS_DATABASE_ID", "3e58c53d-f08d-800a-bb8e-cd75db304c97")
            if settings
            else "3e58c53d-f08d-800a-bb8e-cd75db304c97"
        )

        self.auto_open_browser = auto_open_browser
        self.code_signal_file = base_dir / "data" / ".notion_oauth_code.json"

        # Storage and OAuth Provider setup
        self.storage = JsonFileTokenStorage(self.token_path)
        self.metadata = OAuthClientMetadata(
            client_name=self.client_name,
            redirect_uris=[AnyUrl(self.redirect_uri)],
            grant_types=["authorization_code", "refresh_token"],
            response_types=["code"],
            scope="default",
        )

        self.oauth_provider = OAuthClientProvider(
            server_url=self.server_url,
            client_metadata=self.metadata,
            storage=self.storage,
            redirect_handler=self._redirect_handler,
            callback_handler=self._callback_handler,
        )

        # State tracking
        self.last_auth_url: str | None = None
        self._expected_state: str | None = None
        self._auth_future: asyncio.Future[AuthorizationCodeResult] | None = None
        self._discovered_tools: list[dict[str, Any]] | None = None
        self._connection_lock = asyncio.Lock()

    # -----------------------------------------------------------------------
    # OAuth Callbacks & Redirect Handling
    # -----------------------------------------------------------------------

    async def _redirect_handler(self, auth_url: str) -> None:
        """Called by OAuthClientProvider when browser authorization is required."""
        self.last_auth_url = auth_url
        try:
            parsed = urlparse(auth_url)
            from urllib.parse import parse_qs
            qs = parse_qs(parsed.query)
            self._expected_state = qs.get("state", [None])[0]
        except Exception:
            self._expected_state = None

        logger.info("\n" + "=" * 70)
        logger.info("[NOTION OAUTH] Authorization required!")
        logger.info("[NOTION OAUTH] Please open this URL in your browser to authorize:")
        logger.info("[NOTION OAUTH] %s", auth_url)
        logger.info("=" * 70 + "\n")

        if self.auto_open_browser:
            try:
                logger.info("[NOTION OAUTH] Launching default web browser...")
                webbrowser.open(auth_url)
            except Exception as exc:
                logger.warning("[NOTION OAUTH] Could not open browser automatically: %s", exc)

    async def _callback_handler(self) -> AuthorizationCodeResult:
        """Awaited by OAuthClientProvider to retrieve the authorization code.

        Supports:
        1. In-process resolution via notify_callback() (e.g. from FastAPI route).
        2. Inter-process signal file reading (data/.notion_oauth_code.json).
        3. Standalone local server listener if redirect port is not bound.
        """
        loop = asyncio.get_running_loop()
        self._auth_future = loop.create_future()

        logger.info(
            "[NOTION OAUTH] Waiting for authorization callback at %s (timeout: 300s)...",
            self.redirect_uri,
        )

        # Ensure signal file from past runs is cleaned up
        if self.code_signal_file.exists():
            try:
                self.code_signal_file.unlink()
            except OSError:
                pass

        # Also start a temporary local server listener if port is available
        temp_server_task = None
        parsed_uri = urlparse(self.redirect_uri)
        port = parsed_uri.port or 8000
        path = parsed_uri.path or "/api/notion/callback"

        try:
            # Check if port is available; if so, spin up a fallback mini-listener
            temp_server_task = asyncio.create_task(
                self._run_fallback_callback_listener(port=port, expected_path=path)
            )
        except Exception as exc:
            logger.debug("Fallback callback listener not started (port may already be in use): %s", exc)

        start_time = asyncio.get_event_loop().time()
        timeout_seconds = 600.0

        try:
            while not self._auth_future.done():
                # Check for signal file written by external process (FastAPI route)
                if self.code_signal_file.exists():
                    try:
                        with open(self.code_signal_file, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        code = data.get("code")
                        state = data.get("state")
                        iss = data.get("iss")
                        if code and state:
                            if self._expected_state and state != self._expected_state:
                                logger.warning(
                                    "[NOTION OAUTH] Stale callback received in signal file (state %s != expected %s). Ignoring.",
                                    state,
                                    self._expected_state,
                                )
                                try:
                                    self.code_signal_file.unlink()
                                except OSError:
                                    pass
                            else:
                                logger.info("[NOTION OAUTH] Received valid authorization code from signal file.")
                                self.code_signal_file.unlink()
                                return AuthorizationCodeResult(code=code, state=state, iss=iss)
                    except Exception as err:
                        logger.debug("Error checking signal file: %s", err)

                # Check if future was resolved directly
                if self._auth_future.done():
                    return self._auth_future.result()

                # Check timeout
                if asyncio.get_event_loop().time() - start_time > timeout_seconds:
                    raise TimeoutError(
                        f"Timed out waiting for Notion OAuth callback after {int(timeout_seconds)}s."
                    )

                await asyncio.sleep(0.5)

            return self._auth_future.result()

        finally:
            if temp_server_task and not temp_server_task.done():
                temp_server_task.cancel()
                try:
                    await temp_server_task
                except (asyncio.CancelledError, Exception):
                    pass
            self._auth_future = None

    async def _run_fallback_callback_listener(self, port: int, expected_path: str) -> None:
        """Lightweight HTTP server to catch OAuth callback if backend is not already running."""
        try:
            async def handle_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
                try:
                    line = await reader.readline()
                    request_line = line.decode("utf-8").strip()
                    if not request_line:
                        writer.close()
                        await writer.wait_closed()
                        return

                    parts = request_line.split()
                    if len(parts) >= 2:
                        url_path = parts[1]
                        parsed = urlparse(url_path)
                        if parsed.path == expected_path:
                            from urllib.parse import parse_qs
                            query = parse_qs(parsed.query)
                            code = query.get("code", [None])[0]
                            state = query.get("state", [None])[0]
                            iss = query.get("iss", [None])[0]

                            if code and state:
                                if self._expected_state and state != self._expected_state:
                                    logger.warning(
                                        "[NOTION OAUTH] Fallback listener received stale callback (state %s != expected %s).",
                                        state,
                                        self._expected_state,
                                    )
                                    response = (
                                        "HTTP/1.1 400 Bad Request\r\n"
                                        "Content-Type: text/html; charset=utf-8\r\n"
                                        "Connection: close\r\n\r\n"
                                        "<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                        "<h2>⚠️ Stale Authorization Session</h2>"
                                        "<p>This authorization was for an expired or earlier session. Please use the most recent browser tab or authorization link.</p>"
                                        "</body></html>"
                                    )
                                    writer.write(response.encode("utf-8"))
                                    await writer.drain()
                                    writer.close()
                                    await writer.wait_closed()
                                    return

                                self.notify_callback(code=code, state=state, iss=iss)
                                response = (
                                    "HTTP/1.1 200 OK\r\n"
                                    "Content-Type: text/html; charset=utf-8\r\n"
                                    "Connection: close\r\n\r\n"
                                    "<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                                    "<h2>✅ Notion Authorization Successful</h2>"
                                    "<p>You can close this tab and return to the terminal/app.</p>"
                                    "</body></html>"
                                )
                                writer.write(response.encode("utf-8"))
                                await writer.drain()
                                writer.close()
                                await writer.wait_closed()
                                return

                    writer.write(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\n\r\nNot Found")
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    try:
                        writer.close()
                        await writer.wait_closed()
                    except Exception:
                        pass

            server = await asyncio.start_server(handle_request, "127.0.0.1", port)
            async with server:
                await server.serve_forever()
        except OSError:
            # Port already in use (e.g. by uvicorn), which is completely fine
            pass

    def notify_callback(self, code: str, state: str, iss: str | None = None) -> None:
        """Notify the client of an incoming authorization callback."""
        logger.info("[NOTION OAUTH] Processing incoming callback (code length: %d)", len(code))

        if self._expected_state and state != self._expected_state:
            logger.warning(
                "[NOTION OAUTH] Received callback with state %s but active session expects %s. Ignoring stale callback.",
                state,
                self._expected_state,
            )
            return

        # Write to signal file for any external processes
        try:
            self.code_signal_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.code_signal_file, "w", encoding="utf-8") as f:
                json.dump({"code": code, "state": state, "iss": iss}, f)
        except Exception as exc:
            logger.warning("[NOTION OAUTH] Failed to write callback signal file: %s", exc)

        # Resolve internal in-process future if pending
        if self._auth_future and not self._auth_future.done():
            self._auth_future.set_result(
                AuthorizationCodeResult(code=code, state=state, iss=iss)
            )

    # -----------------------------------------------------------------------
    # Connection & Session Context Management
    # -----------------------------------------------------------------------

    @asynccontextmanager
    async def connect(self) -> AsyncGenerator[ClientSession, None]:
        """Establish an authenticated ClientSession to the Notion MCP server.

        Yields:
            ClientSession: Initialized MCP client session ready for tool execution.
        """
        http_client = create_mcp_http_client(auth=self.oauth_provider)
        try:
            async with http_client:
                async with streamable_http_client(
                    self.server_url,
                    http_client=http_client,
                    terminate_on_close=True,
                ) as (read_stream, write_stream):
                    async with ClientSession(read_stream, write_stream) as session:
                        logger.info("Initializing MCP session with %s...", self.server_url)
                        init_result = await session.initialize()
                        logger.info(
                            "MCP Session initialized successfully. Server: %s, Protocol: %s",
                            getattr(init_result.server_info, "name", "Notion"),
                            init_result.protocol_version,
                        )
                        yield session
        except Exception as exc:
            logger.error("Error in Notion MCP session: %s", exc)
            raise

    # -----------------------------------------------------------------------
    # Tool Discovery & Generic Tool Invocation
    # -----------------------------------------------------------------------

    async def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools provided by the Notion MCP server.

        Returns:
            list[dict[str, Any]]: List of tool schemas with name, description, and inputSchema.
        """
        async with self.connect() as session:
            tools_result = await session.list_tools()
            tools_list = []
            for tool in tools_result.tools:
                tools_list.append({
                    "name": tool.name,
                    "description": tool.description or "",
                    "inputSchema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                })
            self._discovered_tools = tools_list
            logger.info("Discovered %d tools from Notion MCP server.", len(tools_list))
            return tools_list

    def _resolve_tool_name(self, name: str, available_tools: list[str]) -> str:
        """Resolve a tool name against the server's registered tools.

        Handles variations like 'fetch' vs 'notion-fetch' or hyphens vs underscores.
        """
        if name in available_tools:
            return name

        # Try prefix matching or normalization
        clean_target = name.lower().replace("-", "_").replace("notion_", "")
        for t in available_tools:
            clean_t = t.lower().replace("-", "_").replace("notion_", "")
            if clean_t == clean_target:
                return t

        return name

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool on the Notion MCP server.

        Args:
            name: The tool name (e.g. 'fetch', 'query_data_sources', 'create_pages').
            arguments: Tool arguments dictionary.

        Returns:
            dict[str, Any]: Structured tool execution result.
        """
        arguments = arguments or {}
        async with self.connect() as session:
            # Refresh tool discovery if needed
            tools_result = await session.list_tools()
            available_names = [t.name for t in tools_result.tools]
            resolved_name = self._resolve_tool_name(name, available_names)

            logger.info(
                "Calling Notion MCP tool '%s' (resolved from '%s') with args: %s",
                resolved_name,
                name,
                list(arguments.keys()),
            )

            result = await session.call_tool(name=resolved_name, arguments=arguments)

            parsed_contents = []
            for item in getattr(result, "content", []):
                if hasattr(item, "text"):
                    text_str = item.text
                    # Check if text is JSON string
                    try:
                        parsed_json = json.loads(text_str)
                        parsed_contents.append(parsed_json)
                    except Exception:
                        parsed_contents.append(text_str)
                elif hasattr(item, "data"):
                    parsed_contents.append(f"<binary data: {getattr(item, 'mimeType', 'unknown')}>")
                else:
                    parsed_contents.append(str(item))

            is_error = bool(getattr(result, "is_error", False))
            if is_error:
                logger.warning("Notion tool '%s' returned an error result.", resolved_name)

            return {
                "tool": resolved_name,
                "is_error": is_error,
                "content": parsed_contents,
                "raw": [c.model_dump(mode="json") for c in getattr(result, "content", [])]
                if hasattr(result, "content")
                else [],
            }

    # -----------------------------------------------------------------------
    # High-Level Feature Implementations
    # -----------------------------------------------------------------------

    async def query_daily_tasks(
        self,
        database_id: str | None = None,
        due_date: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query tasks from the Notion Daily Task database.

        Args:
            database_id: The Notion database ID (defaults to configured Daily Task DB).
            due_date: Optional due date filter in 'YYYY-MM-DD' format.
            status: Optional status filter (e.g. 'In progress', 'Not started', 'Done').

        Returns:
            list[dict[str, Any]]: List of task items with name, status, priority, and due_date.
        """
        db_id = database_id or self.daily_tasks_db_id
        logger.info("Querying Daily Tasks from database ID: %s", db_id)

        # 1. Fetch database details to obtain data source collection URL
        fetch_res = await self.call_tool("fetch", {"id": db_id})
        fetch_text = ""
        for item in fetch_res.get("content", []):
            if isinstance(item, str):
                fetch_text += item
            elif isinstance(item, dict):
                fetch_text += json.dumps(item)

        # Extract collection URL: collection://<UUID>
        match = re.search(r"collection://[0-9a-fA-F-]+", fetch_text)
        if not match:
            logger.warning(
                "Could not extract collection URL from database fetch. Using database ID directly."
            )
            collection_url = f"collection://{db_id}"
        else:
            collection_url = match.group(0)

        logger.info("Found Notion data source collection: %s", collection_url)

        # 2. Build SQL query for query_data_sources
        sql_query = f'SELECT * FROM "{collection_url}"'
        params = []
        conditions = []

        if due_date:
            conditions.append('"date:due date:start" = ?')
            params.append(due_date)

        if status:
            conditions.append('"status" = ?')
            params.append(status)

        if conditions:
            sql_query += " WHERE " + " AND ".join(conditions)

        logger.info("Executing query on data source: %s (params: %s)", sql_query, params)

        query_payload: dict[str, Any] = {
            "data": {
                "mode": "sql",
                "data_source_urls": [collection_url],
                "query": sql_query,
            }
        }
        if params:
            query_payload["data"]["params"] = params

        query_res = await self.call_tool("query_data_sources", query_payload)

        # Parse task results
        tasks = []
        if not query_res.get("is_error"):
            for content in query_res.get("content", []):
                if isinstance(content, dict) and "results" in content:
                    for row in content.get("results", []):
                        tasks.append({
                            "id": row.get("id"),
                            "name": row.get("Name"),
                            "status": row.get("status"),
                            "priority": row.get("priority"),
                            "due_date": row.get("date:due date:start"),
                            "due_date_end": row.get("date:due date:end"),
                            "created_time": row.get("createdTime"),
                            "url": row.get("url"),
                        })
                elif isinstance(content, list):
                    for row in content:
                        if isinstance(row, dict):
                            tasks.append({
                                "id": row.get("id"),
                                "name": row.get("Name") or row.get("name"),
                                "status": row.get("status"),
                                "priority": row.get("priority"),
                                "due_date": row.get("date:due date:start") or row.get("due date"),
                                "created_time": row.get("createdTime"),
                                "url": row.get("url"),
                            })

        # If query_data_sources failed (e.g. usage limit reached), fall back to notion-search
        if not tasks:
            logger.info("Falling back to notion-search to discover Daily Tasks.")
            try:
                search_res = await self.call_tool("notion-search", {"query": "Task"})
                search_content = search_res.get("content", [])
                search_results = (
                    search_content[0].get("results", [])
                    if search_content and isinstance(search_content[0], dict)
                    else []
                )
                daily_items = [
                    item for item in search_results
                    if item.get("path") == "Daily Task" and item.get("type") == "page"
                ]

                async def _fill_task(item: dict[str, Any]) -> dict[str, Any]:
                    try:
                        d = await self.get_task_details(item.get("id"))
                        return {
                            "id": item.get("id"),
                            "name": d.get("title") or item.get("title") or "Untitled Task",
                            "status": d.get("status") or "In progress",
                            "priority": d.get("priority") or "Medium",
                            "due_date": d.get("due_date"),
                            "due_date_end": d.get("due_date_end"),
                            "created_time": item.get("timestamp"),
                            "url": item.get("url") or d.get("url"),
                        }
                    except Exception:
                        return {
                            "id": item.get("id"),
                            "name": item.get("title") or "Untitled Task",
                            "status": "In progress",
                            "priority": "Medium",
                            "due_date": None,
                            "created_time": item.get("timestamp"),
                            "url": item.get("url"),
                        }

                if daily_items:
                    tasks = await asyncio.gather(*[_fill_task(item) for item in daily_items])
            except Exception as search_err:
                logger.error("Search fallback also failed: %s", search_err)

        # Apply in-memory filters if needed
        if due_date:
            tasks = [t for t in tasks if t.get("due_date") == due_date]
        if status:
            tasks = [t for t in tasks if (t.get("status") or "").lower() == status.lower()]

        logger.info("Successfully retrieved %d task(s) from Notion.", len(tasks))
        return list(tasks)

    async def get_task_details(self, page_id: str) -> dict[str, Any]:
        """Fetch full details and content for a specific Notion task or page using notion-fetch tool.

        Args:
            page_id: Notion page ID or UUID.

        Returns:
            dict[str, Any]: Structured task details, properties, content, and metadata.
        """
        import re

        clean_id = page_id.strip()
        logger.info("Fetching Notion task details for page ID: %s", clean_id)

        result = await self.call_tool("fetch", {"id": clean_id})
        if result.get("is_error"):
            logger.error("Notion MCP fetch tool error for ID %s: %s", clean_id, result)
            return {
                "id": clean_id,
                "is_error": True,
                "error": result.get("error") or "Failed to fetch task from Notion MCP",
                "raw": result,
            }

        content_items = result.get("content", [])
        page_info = content_items[0] if content_items and isinstance(content_items, list) else {}

        # Parse properties block if present in XML/text
        properties = {}
        raw_text = page_info.get("text", "")
        props_match = re.search(r"<properties>\s*(\{.*?\})\s*</properties>", raw_text, re.DOTALL)
        if props_match:
            try:
                properties = json.loads(props_match.group(1))
            except Exception:
                pass

        # Extract page body/content (excluding system tags)
        content_body = raw_text
        if "<properties>" in content_body and "</properties>" in content_body:
            content_body = re.sub(r"<properties>.*?</properties>", "", content_body, flags=re.DOTALL)
        if "<ancestor-path>" in content_body and "</ancestor-path>" in content_body:
            content_body = re.sub(r"<ancestor-path>.*?</ancestor-path>", "", content_body, flags=re.DOTALL)
        content_body = re.sub(r"<iconMetadata>.*?</iconMetadata>", "", content_body, flags=re.DOTALL)
        content_body = re.sub(r"<blank-page[^>]*>.*?</blank-page>", "", content_body, flags=re.DOTALL)
        content_body = re.sub(r"</?blank-page[^>]*>", "", content_body)
        content_body = re.sub(r"</?page[^>]*>", "", content_body)
        content_body = re.sub(r"</?content[^>]*>", "", content_body)
        content_body = re.sub(r"<empty-block[^>]*/>", "", content_body)
        content_body = re.sub(r"</?empty-block[^>]*>", "", content_body)
        content_body = re.sub(r'^Here is the result of "fetch"[^\n]*:\s*', "", content_body, flags=re.IGNORECASE)
        content_body = content_body.strip()
        if content_body.lower() == "null" or "this page is blank and has no content" in content_body.lower():
            content_body = ""

        # Extract Description property if available from Notion database schema
        raw_description = properties.get("Description") or properties.get("description") or ""
        clean_description = ""
        if isinstance(raw_description, str) and raw_description.strip():
            clean_description = (
                raw_description.replace("<br>", "\n")
                .replace("<br/>", "\n")
                .replace("<br />", "\n")
                .strip()
            )

        if not content_body and clean_description:
            content_body = clean_description
        elif clean_description and clean_description not in content_body:
            content_body = f"{clean_description}\n\n{content_body}".strip()

        title = (
            page_info.get("title")
            or properties.get("Name")
            or properties.get("name")
            or properties.get("title")
            or "Untitled Task"
        )
        url = page_info.get("url") or properties.get("url")
        status = properties.get("status")
        priority = properties.get("priority")
        due_date = properties.get("date:due date:start") or properties.get("due date")
        due_date_end = properties.get("date:due date:end")
        last_edited_at = page_info.get("page_last_edited_at")
        path = page_info.get("path")
        cover = page_info.get("cover")
        icon = page_info.get("icon")

        return {
            "id": clean_id,
            "title": title,
            "name": title,
            "url": url,
            "status": status,
            "priority": priority,
            "due_date": due_date,
            "due_date_end": due_date_end,
            "last_edited_at": last_edited_at,
            "path": path,
            "cover": cover,
            "icon": icon,
            "properties": properties,
            "description": clean_description,
            "content": content_body,
            "raw_text": raw_text,
            "is_error": False,
        }

    async def create_meeting_notes_page(
        self,
        title: str,
        content: str = "",
        parent_page_id: str | None = None,
        parent_database_id: str | None = None,
        icon: str = "📝",
    ) -> dict[str, Any]:
        """Create a new page in Notion for meeting notes or project documentation.

        Args:
            title: Title of the meeting notes page.
            content: Markdown content of the meeting notes.
            parent_page_id: Optional parent page ID to nest under.
            parent_database_id: Optional parent database ID.
            icon: Optional emoji icon (default '📝').

        Returns:
            dict[str, Any]: Result containing status and created page details.
        """
        logger.info("Creating meeting notes page: '%s'", title)

        page_data: dict[str, Any] = {
            "properties": {"title": title},
            "content": content,
            "icon": icon,
        }

        arguments: dict[str, Any] = {
            "pages": [page_data],
        }

        if parent_page_id:
            arguments["parent"] = {
                "page_id": parent_page_id.replace("-", ""),
                "type": "page_id",
            }
        elif parent_database_id:
            arguments["parent"] = {
                "database_id": parent_database_id.replace("-", ""),
                "type": "database_id",
            }
        else:
            arguments["creation_mode"] = "draft"

        result = await self.call_tool("create_pages", arguments)
        logger.info("Page creation completed with status: %s", "error" if result.get("is_error") else "success")
        return result

    # -----------------------------------------------------------------------
    # Authentication & Status Helpers
    # -----------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        """Check if client currently holds a valid access token."""
        return self.storage.is_authenticated()

    def get_status(self) -> dict[str, Any]:
        """Return diagnostic status information for this client."""
        return {
            "authenticated": self.is_authenticated(),
            "server_url": self.server_url,
            "redirect_uri": self.redirect_uri,
            "token_path": str(self.token_path),
            "token_file_exists": self.token_path.exists(),
            "daily_tasks_db_id": self.daily_tasks_db_id,
            "last_auth_url": self.last_auth_url,
            "cached_tools_count": len(self._discovered_tools) if self._discovered_tools else 0,
        }


# ---------------------------------------------------------------------------
# Global Singleton Accessor
# ---------------------------------------------------------------------------

_notion_client_instance: NotionMCPClient | None = None


def get_notion_client() -> NotionMCPClient:
    """Retrieve or create the shared NotionMCPClient singleton instance."""
    global _notion_client_instance
    if _notion_client_instance is None:
        _notion_client_instance = NotionMCPClient()
    return _notion_client_instance


# ---------------------------------------------------------------------------
# Standalone CLI / Verification Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Notion MCP Client CLI")
    parser.add_argument("--list-tools", action="store_true", help="List all available Notion MCP tools")
    parser.add_argument("--tasks", action="store_true", help="Query tasks from the Daily Task database")
    parser.add_argument("--status", action="store_true", help="Show client authentication status")
    parser.add_argument("--create-note", nargs=2, metavar=("TITLE", "CONTENT"), help="Create a meeting note")
    args = parser.parse_args()

    client = get_notion_client()

    async def run_cli():
        print("\n=== Notion MCP Client ===")
        status = client.get_status()
        print(f"Server URL:     {status['server_url']}")
        print(f"Authenticated:  {status['authenticated']}")
        print(f"Token Storage:  {status['token_path']}")
        print("=========================\n")

        if args.status and not (args.list_tools or args.tasks or args.create_note):
            return

        if args.tasks:
            print("\nFetching Daily Tasks...")
            try:
                tasks = await client.query_daily_tasks()
                print(f"\nRetrieved {len(tasks)} task(s):")
                for t in tasks:
                    print(f"- [{t.get('status')}] {t.get('name')} (Priority: {t.get('priority')}, Due: {t.get('due_date')})")
            except Exception as e:
                print(f"Error querying tasks: {e}")

        elif args.create_note:
            title, content = args.create_note
            print(f"\nCreating meeting note: {title}")
            try:
                res = await client.create_meeting_notes_page(title=title, content=content)
                print(f"Result: {json.dumps(res, indent=2)}")
            except Exception as e:
                print(f"Error creating note: {e}")

        else:
            # Default action: list tools
            print("\nConnecting to Notion MCP server and listing tools...")
            try:
                tools = await client.list_tools()
                print(f"\nSuccessfully discovered {len(tools)} tools:")
                for tool in tools:
                    print(f"  • {tool['name']}: {tool['description'][:90]}...")
            except Exception as e:
                print(f"Error listing tools: {e}")

    try:
        asyncio.run(run_cli())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
