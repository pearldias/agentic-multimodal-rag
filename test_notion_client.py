"""Verification and test script for the Notion MCP Client integration.

This script tests:
1. Notion MCP Client initialization and settings.
2. TokenStorage integrity and authentication status.
3. OAuth 2.0 PKCE flow initiation (via Streamable HTTP).
4. Tool discovery and Daily Task database query execution.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from mcp_server.notion_client import get_notion_client, NotionMCPClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("test_notion_client")


async def run_diagnostics():
    print("\n" + "=" * 65)
    print("        NOTION MCP CLIENT INTEGRATION DIAGNOSTICS")
    print("=" * 65)

    client = get_notion_client()
    status = client.get_status()

    print(f"MCP Server URL:          {status['server_url']}")
    print(f"OAuth Redirect URI:      {status['redirect_uri']}")
    print(f"Token Storage Path:      {status['token_path']}")
    print(f"Token File Exists:       {status['token_file_exists']}")
    print(f"Authenticated:           {status['authenticated']}")
    print(f"Daily Tasks Database ID: {status['daily_tasks_db_id']}")
    print("=" * 65 + "\n")

    if not status["authenticated"]:
        print("[INFO] Client is not yet authenticated with Notion.")
        print("       When you execute an operation (like listing tools or querying tasks),")
        print("       Notion MCP will automatically trigger the OAuth 2 + PKCE flow,")
        print("       open your web browser to approve access, and store the token safely.\n")

    # Offer options
    print("Available actions:")
    print("  1. List Notion MCP tools (triggers OAuth if unauthenticated)")
    print("  2. Query Daily Tasks database (3e58c53d-f08d-800a-bb8e-cd75db304c97)")
    print("  3. Check status only")
    print("-" * 65)

    action = sys.argv[1] if len(sys.argv) > 1 else "--list-tools"

    if action in ("--tools", "--list-tools", "-t"):
        print("\nConnecting to Notion MCP server at https://mcp.notion.com/mcp...")
        try:
            tools = await client.list_tools()
            print(f"\nDiscovered {len(tools)} Notion MCP Tools:")
            for i, tool in enumerate(tools, start=1):
                name = tool.get("name", "unknown")
                desc = tool.get("description", "").split("\n")[0][:80]
                print(f"  {i:2d}. {name:<25} - {desc}")
        except Exception as exc:
            print(f"\n[ERROR] Error during tool discovery: {exc}")

    elif action in ("--tasks", "-k"):
        print("\nQuerying Daily Tasks from database...")
        try:
            tasks = await client.query_daily_tasks()
            print(f"\nFound {len(tasks)} tasks:")
            for t in tasks:
                status_val = t.get("status") or "Unknown"
                name_val = t.get("name") or "Untitled"
                prio_val = t.get("priority") or "None"
                due_val = t.get("due_date") or "None"
                print(f"  - [{status_val}] {name_val} (Priority: {prio_val}, Due: {due_val})")
        except Exception as exc:
            print(f"\n[ERROR] Error querying daily tasks: {exc}")

    elif action in ("--status", "-s"):
        print("Status check complete.")

    else:
        print(f"Unknown action: {action}")
        print("Use --list-tools, --tasks, or --status")


if __name__ == "__main__":
    try:
        asyncio.run(run_diagnostics())
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
