import asyncio
import httpx

MCP_URL = "https://mcp.notion.com/mcp"


async def main():
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(
            MCP_URL,
            headers={"Accept": "application/json"},
        )

        print("Status:", response.status_code)
        print("WWW-Authenticate:", response.headers.get("www-authenticate"))
        print("Body:", response.text[:2000])
       


if __name__ == "__main__":
    asyncio.run(main())