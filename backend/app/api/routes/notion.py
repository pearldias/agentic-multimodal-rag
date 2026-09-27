import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from mcp_server.notion_client import get_notion_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/notion",
    tags=["Notion MCP"],
)


class MeetingNotesCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500, description="Title of the meeting notes page")
    content: str = Field(default="", max_length=100000, description="Markdown body for the meeting notes")
    parent_page_id: str | None = Field(default=None, description="Optional parent Notion page ID")
    parent_database_id: str | None = Field(default=None, description="Optional parent Notion database ID")
    icon: str = Field(default="📝", max_length=10, description="Page icon emoji")

    @field_validator("title")
    @classmethod
    def validate_title_not_empty(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("Meeting notes title must not be empty or whitespace only.")
        return trimmed


@router.get("/callback", response_class=HTMLResponse)
async def notion_oauth_callback(
    code: str | None = Query(None, description="Authorization code from Notion"),
    state: str | None = Query(None, description="OAuth state parameter"),
    iss: str | None = Query(None, description="Issuer parameter"),
    error: str | None = Query(None, description="OAuth error code"),
    error_description: str | None = Query(None, description="OAuth error description"),
) -> HTMLResponse:
    """OAuth 2.0 callback endpoint invoked by Notion after user authorization."""
    if error:
        logger.error("Notion OAuth error received: %s - %s", error, error_description)
        html_error = f"""<!DOCTYPE html>
<html>
<head><title>Notion Authorization Failed</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #fafafa;">
  <div style="background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.08); max-width: 480px; text-align: center;">
    <div style="font-size: 48px; margin-bottom: 12px;">❌</div>
    <h2 style="color: #d32f2f; margin: 0 0 12px;">Authorization Failed</h2>
    <p style="color: #555; font-size: 15px;">{error}: {error_description or 'Unknown authorization error'}</p>
    <p style="color: #888; font-size: 13px;">Please check the backend logs and try again.</p>
  </div>
</body>
</html>"""
        return HTMLResponse(content=html_error, status_code=400)

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing required 'code' or 'state' parameters in OAuth callback.",
        )

    logger.info("Notion OAuth callback received with valid code and state.")
    client = get_notion_client()
    client.notify_callback(code=code, state=state, iss=iss)

    html_success = """<!DOCTYPE html>
<html>
<head><title>Notion Authorization Successful</title></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f6f8fa;">
  <div style="background: white; padding: 48px 40px; border-radius: 12px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); max-width: 480px; text-align: center;">
    <div style="font-size: 52px; margin-bottom: 16px;">✅</div>
    <h2 style="color: #1a1a1a; margin: 0 0 12px; font-weight: 600;">Notion Connected Successfully</h2>
    <p style="color: #555; font-size: 15px; line-height: 1.5; margin-bottom: 24px;">Your Notion workspace has been connected to the Agentic RAG system.</p>
    <div style="background: #e6f4ea; color: #137333; padding: 10px 16px; border-radius: 8px; font-size: 14px; font-weight: 500;">
      You may now close this tab and return to the application.
    </div>
  </div>
</body>
</html>"""
    return HTMLResponse(content=html_success)


@router.get("/status")
def get_notion_status() -> dict[str, Any]:
    """Retrieve connection and authentication status of the Notion MCP client."""
    client = get_notion_client()
    return client.get_status()


@router.get("/tools")
async def list_notion_tools() -> dict[str, Any]:
    """List all available tools from the connected Notion MCP server."""
    client = get_notion_client()
    try:
        tools = await client.list_tools()
        return {"tools": tools, "count": len(tools)}
    except Exception as exc:
        logger.error("Failed to list Notion tools: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Notion MCP server: {exc}",
        )


@router.get("/tasks")
async def get_daily_tasks(
    database_id: str | None = Query(None, description="Optional Notion database ID"),
    due_date: str | None = Query(None, description="Filter tasks by due date (YYYY-MM-DD)"),
    status: str | None = Query(None, description="Filter tasks by status"),
) -> dict[str, Any]:
    """Query daily tasks from the Notion tasks database."""
    client = get_notion_client()
    try:
        tasks = await client.query_daily_tasks(
            database_id=database_id,
            due_date=due_date,
            status=status,
        )
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as exc:
        logger.error("Failed to query Notion daily tasks: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to query Notion tasks: {exc}",
        )


@router.get("/tasks/{page_id}")
async def get_task_details(
    page_id: str,
) -> dict[str, Any]:
    """Retrieve full details of a specific Notion task or page using Notion MCP notion-fetch tool.

    This endpoint directly contacts the Notion MCP server and does NOT query ChromaDB or the RAG pipeline.
    """
    clean_id = page_id.strip()
    if not clean_id:
        raise HTTPException(status_code=400, detail="Page ID must not be empty.")

    client = get_notion_client()
    try:
        details = await client.get_task_details(clean_id)
        if details.get("is_error"):
            error_msg = str(details.get("error", ""))
            status_code = 404 if "not found" in error_msg.lower() else 502
            raise HTTPException(
                status_code=status_code,
                detail=f"Failed to fetch Notion task: {error_msg}",
            )
        return details
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to fetch Notion task details for %s: %s", clean_id, exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to communicate with Notion MCP: {exc}",
        )


@router.post("/meeting-notes")
async def create_meeting_notes(
    request: MeetingNotesCreateRequest,
) -> dict[str, Any]:
    """Create a new page in Notion for meeting notes."""
    client = get_notion_client()
    try:
        result = await client.create_meeting_notes_page(
            title=request.title,
            content=request.content,
            parent_page_id=request.parent_page_id,
            parent_database_id=request.parent_database_id,
            icon=request.icon,
        )

        if result.get("is_error"):
            error_msg = result.get("error") or "Notion MCP create-pages returned an error"
            logger.error("Notion MCP create_pages failed: %s", result)
            raise HTTPException(
                status_code=400,
                detail=f"Notion page creation failed: {error_msg}",
            )

        # Extract created page details if available
        page_id = None
        page_url = None
        content_items = result.get("content", [])
        if content_items and isinstance(content_items, list):
            pages = content_items[0].get("pages", [])
            if pages and isinstance(pages, list):
                page_id = pages[0].get("id")
                page_url = pages[0].get("url")

        return {
            "status": "success",
            "message": f"Meeting notes page '{request.title}' created successfully in Notion.",
            "page_id": page_id,
            "page_url": page_url,
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to create Notion meeting notes: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Failed to create meeting notes in Notion: {exc}",
        )


class NotionChatRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Question about Notion tasks/workspace")
    conversation_id: str | None = Field(None, description="Optional conversation session ID")


@router.post("/chat")
async def chat_with_notion(
    request: NotionChatRequest,
) -> dict[str, Any]:
    """Dedicated Notion Assistant Chat.

    Retrieves task data and details through Notion MCP (query_daily_tasks, notion-fetch, notion-search)
    and answers questions using Gemini without touching ChromaDB or the document RAG pipeline.
    """
    clean_q = request.question.strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    client = get_notion_client()
    try:
        # 1. Fetch current daily tasks via MCP
        tasks = await client.query_daily_tasks()

        # 2. Gather full details for tasks in parallel
        async def _fetch_details(t: dict[str, Any]) -> dict[str, Any]:
            try:
                tid = t.get("id")
                if tid:
                    return await client.get_task_details(tid)
            except Exception as e:
                logger.warning("Could not fetch details for task %s: %s", t.get("id"), e)
            return t

        task_details_list = await asyncio.gather(*[_fetch_details(t) for t in tasks])

        # 3. Optional targeted search for extra context if user mentions specific query
        extra_notion_info = []
        try:
            search_res = await client.call_tool("notion-search", {"query": clean_q})
            search_content = search_res.get("content", [])
            search_results = (
                search_content[0].get("results", [])
                if search_content and isinstance(search_content[0], dict)
                else []
            )
            for item in search_results[:3]:
                if item.get("id") not in [t.get("id") for t in tasks]:
                    extra_notion_info.append(
                        f"Matched Notion Entity: '{item.get('title')}' (Path: {item.get('path')}, URL: {item.get('url')})"
                    )
        except Exception as search_err:
            logger.debug("Optional notion-search skipped: %s", search_err)

        # 4. Format structured Notion workspace context
        lines = []
        for t in task_details_list:
            lines.append(f"Task: {t.get('title') or t.get('name')}")
            lines.append(f"  ID: {t.get('id')}")
            lines.append(f"  Status: {t.get('status')}")
            lines.append(f"  Priority: {t.get('priority')}")
            lines.append(f"  Due Date: {t.get('due_date')}")
            if t.get("url"):
                lines.append(f"  URL: {t.get('url')}")
            if t.get("description"):
                lines.append(f"  Description: {t.get('description')}")
            if t.get("content"):
                raw_c = str(t.get("content"))
                clean_c = (
                    raw_c.replace(r"\-", "-")
                    .replace(r"\[", "[")
                    .replace(r"\]", "]")
                    .replace(r"\(", "(")
                    .replace(r"\)", ")")
                )
                lines.append(f"  Notes / Page Content:\n{clean_c}")
            lines.append("")

        if extra_notion_info:
            lines.append("Additional Related Notion Search Matches:")
            lines.extend(extra_notion_info)
            lines.append("")

        notion_context = "\n".join(lines)

        # 5. Call LLMService to synthesize an accurate, grounded answer
        from backend.app.services.llm_service import LLMService
        llm = LLMService()

        prompt = f"""You are the McLaren Notion Workspace Assistant.
Your task is to answer user questions about tasks, projects, priorities, statuses, and action items in the user's Notion workspace.
You are connected directly to the Notion Model Context Protocol (MCP) server.

CRITICAL INSTRUCTIONS:
1. Ground your answers ONLY in the Notion workspace data provided below.
2. If the user asks about tasks in progress, completed tasks, priorities, or due dates, inspect the task statuses and metadata below and give a direct, helpful answer.
3. If next steps or action items are mentioned in the task notes or description (such as LangGraph next steps, Docker setup, etc.), clearly list them.
4. If a task or information is not found in the Notion data below, reply: "I couldn't find this information in your Notion workspace."
5. Do NOT refer to ChromaDB, document collections, or internal file search.
6. Format your response cleanly using standard Markdown: use section headings (###), bullet points (- or *), bold text (**text**), and clean Markdown links like [View in Notion](url) for task URLs. Do not escape markdown characters (do not output \\-, \\[, or \\]).

NOTION WORKSPACE DATA:
{notion_context}

USER QUESTION:
{clean_q}

ASSISTANT RESPONSE:"""

        response = llm.client.models.generate_content(
            model=llm.model,
            contents=prompt,
        )
        answer_text = response.text or "I could not generate an answer from the Notion workspace data."

        # Ensure no accidental escaped markdown characters from Notion MCP or LLM
        clean_answer = (
            answer_text.replace(r"\-", "-")
            .replace(r"\[", "[")
            .replace(r"\]", "]")
            .replace(r"\(", "(")
            .replace(r"\)", ")")
        )

        return {
            "question": clean_q,
            "answer": clean_answer,
            "referenced_tasks": tasks,
        }

    except Exception as exc:
        logger.error("Error in Notion chat: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Notion Assistant encountered an error communicating with Notion MCP: {exc}",
        )

