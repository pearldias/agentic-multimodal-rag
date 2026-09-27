# Production-Grade Multimodal RAG Chatbot

An enterprise-ready Multimodal Retrieval-Augmented Generation (RAG) chatbot designed to ingest, process, and retrieve knowledge from heterogeneous document formats (TXT, PDF, DOCX, XLSX) with verifiable citations and conversational reasoning.

---

## Implemented Milestones

### Milestone 1: Project Foundation
- **FastAPI backend** structured with modular routers and application lifespan management.
- **Pydantic Settings** environment-variable configuration with `.env` support.
- **Centralized application logging** standardizing timestamps, levels, and uvicorn integration.
- **Health check endpoint** (`GET /health`) returning runtime status, version, and environment.
- **Pytest test suite** covering health check response schemas and status codes.

### Milestone 2: Embedding Service
- **Google Gemini Embeddings** via `langchain-google-genai`.
- **Configurable Model & Dimensions**: Defaults to `gemini-embedding-001` with `768` dimensions.
- **Strict Validation**: Enforces exact dimension checks for both query and batch document vectors.
- **Zero Exposed Secrets**: `GOOGLE_API_KEY` is loaded securely through settings and is never logged or printed.
- **Robust Error Handling**: Explicit detection for missing or placeholder API keys.
- **Separated Testing**: Offline mocked unit tests for CI and isolated live Gemini API integration tests.

### Milestone 3: Document Ingestion Foundation (LexiRAG)
- **Multi-Format Parsing**: Production parsers for TXT/MD, PDF (via `pymupdf`), DOCX (via `python-docx`), and XLSX (via `openpyxl`).
- **Legal Structure Preservation**: Unicode NFKC normalization, hyphenation repair for line breaks, preservation of section headers, paragraph breaks, numbered clauses `(1)`, `(a)`, `(i)`, and Markdown table generation.
- **Granular Metadata Tracking**: Preserves filename, file type, title, source URL, page numbers, Excel sheet names, and ISO 8601 UTC ingestion timestamps.
- **Validation Engine**: Robust custom exceptions for unsupported file types, 0-byte or whitespace-only documents, and corrupted file structures.
- **Practical Pydantic Models**: Clean schemas for `ParsedDocument`, `ParsedPage`, and `DocumentMetadata`.
### Milestone 4: Notion MCP Client & Workspace Integration
- **Notion Model Context Protocol (MCP)**: Native integration connecting to Notion's official MCP server (`https://mcp.notion.com/mcp`) using Python MCP SDK v2.2.0 and Streamable HTTP.
- **OAuth 2.0 + PKCE Authorization**: Dynamic client registration, PKCE S256 code challenge, and RFC 6749 §2.3.1 compliant client authentication (`client_secret_basic`).
- **Secure Token Storage**: Persists OAuth tokens and client registration locally in `data/.notion_auth.json` (strictly excluded from Git and Docker images).
- **Dynamic Tool Discovery**: Automatic discovery and negotiation of 45 Notion MCP tools (including `notion-fetch`, `notion-create-pages`, `notion-query-data-sources`, etc.).
- **Live Daily Tasks Integration**: Direct live querying of Notion databases without hardcoded entries.
- **Meeting Notes Generation**: Creates rich Markdown meeting notes pages directly in Notion workspace using the `notion-create-pages` tool.
- **React Frontend UI**: Integrated "Notion Tasks" dashboard card and workspace view with status/priority badges, external links, refresh button, and meeting notes creator modal.

---

## Notion MCP Architecture

```text
┌─────────────────┐        HTTP (Axios)        ┌─────────────────────────┐
│   React UI      │ ─────────────────────────> │   FastAPI Backend       │
│ (Notion Tasks / │                            │   (/api/notion/*)       │
│  Meeting Notes) │ <───────────────────────── │                         │
└─────────────────┘        JSON Payload        └────────────┬────────────┘
                                                            │
                                                            │ Python In-Process
                                                            ▼
                                               ┌─────────────────────────┐
                                               │    NotionMCPClient      │
                                               │ (mcp_server/notion_... )│
                                               └────────────┬────────────┘
                                                            │
                                                            │ Streamable HTTP (SSE)
                                                            ▼
                                               ┌─────────────────────────┐
                                               │  Notion Official MCP    │
                                               │ (https://mcp.notion.com)│
                                               └────────────┬────────────┘
                                                            │
                                                            │ Internal Notion API
                                                            ▼
                                               ┌─────────────────────────┐
                                               │    Notion Workspace     │
                                               │ (Daily Tasks / Pages)   │
                                               └─────────────────────────┘
```

### Notion MCP Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/notion/status` | Diagnostic connection status, redirect URI, database ID, and token status |
| `GET` | `/api/notion/tools` | Dynamically reports all discovered tools from the Notion MCP server |
| `GET` | `/api/notion/tasks` | Live queries the Daily Tasks database via Notion MCP (`notion-query-data-sources`) |
| `POST` | `/api/notion/meeting-notes` | Creates a new page in Notion via `notion-create-pages` with title, content, and icon |
| `GET` | `/api/notion/callback` | OAuth 2.0 PKCE browser authorization callback endpoint |

### Authentication Flow (OAuth 2.0 + PKCE)
1. **Dynamic Client Registration**: Registers with Notion authorization server, obtaining `client_id` and `client_secret`.
2. **PKCE S256**: Generates `code_verifier` and `code_challenge` (S256).
3. **Browser Consent**: Launches default browser for user approval.
4. **Callback Handling**: Notion redirects to `http://localhost:8000/api/notion/callback`.
5. **RFC 6749 §2.3.1 Token Exchange**: Credentials are sent strictly via HTTP Basic header (`Authorization: Basic ...`), purging duplicate body credentials.
6. **Token Persistence**: Tokens are stored atomically in `data/.notion_auth.json` for automatic reuse and background refresh.

---

## Running Tests

### 1. Offline Unit Test Suite (Default)
Runs all unit tests (including Notion MCP mock tests):

```bash
python -m pytest backend/tests -v
```

### 2. Live Notion Integration Diagnostics
To run verification against your live Notion workspace:

```bash
python test_notion_client.py --list-tools
python test_notion_client.py --tasks
```

---

## Docker Deployment

The application includes a production-ready multi-container Docker setup:

```bash
# Build and run with Docker Compose
docker compose up -d --build
```

- **Backend**: Python 3.12-slim container exposing port `8000`. Includes `mcp_server` package and dependencies.
- **Frontend**: Nginx-based multi-stage container serving optimized React production build on port `80`.
- **Security**: Local persistent tokens (`data/.notion_auth.json`), `.env`, and OAuth credentials are kept outside of images via `.dockerignore` and `.gitignore`. Mounting `./data:/app/data` preserves local state at runtime.

## Project Structure

```text
agentic-multimodal-rag/
│
├── data/
│   ├── raw/                         # Raw incoming documents (.gitkeep)
│   ├── processed/                   # Parsed and normalized JSON documents (.gitkeep)
│   └── metadata/                    # Standalone metadata JSON records (.gitkeep)
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entrypoint & lifespan
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Pydantic BaseSettings for env & storage paths
│   │   │   ├── exceptions.py        # Domain exceptions (Empty, Unsupported, Corrupted)
│   │   │   └── logging.py           # Centralized structured logging setup
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       └── health.py        # Health check endpoint (GET /health)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── document.py          # Pydantic schemas (ParsedDocument, ParsedPage)
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── embedding.py         # Google Gemini EmbeddingService (768-dim)
│   │       └── document_parser/     # Document ingestion and parsing package
│   │           ├── __init__.py
│   │           ├── base.py          # Abstract BaseDocumentParser interface
│   │           ├── normalizer.py    # Legal structure & text normalization engine
│   │           ├── txt_parser.py    # Text parser with encoding fallback
│   │           ├── pdf_parser.py    # PyMuPDF page-by-page PDF parser
│   │           ├── docx_parser.py   # Word parser preserving reading order & tables
│   │           ├── xlsx_parser.py   # openpyxl multi-sheet spreadsheet parser
│   │           └── service.py       # DocumentParserService facade & storage
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py              # Test fixtures (TestClient setup)
│   │   ├── test_health.py           # Health endpoint tests
│   │   ├── test_embedding.py        # Offline mocked unit tests for EmbeddingService
│   │   ├── test_embedding_integration.py # Live Gemini API integration test
│   │   └── test_document_parser.py  # 18 unit tests for parsers, validation & normalizer
│   └── requirements.txt             # Bounded backend dependencies
│
├── .env.example                     # Environment variable template
├── .gitignore                       # Secrets and build artifact exclusions
├── pytest.ini                       # Pytest configuration (separates live integration tests)
├── PLAN.md                          # Comprehensive roadmap and milestone tracking
├── CHANGELOG.md                     # Detailed change log for all milestones
└── README.md                        # Documentation and instructions
```


---

## Getting Started

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.14.7)
- Git

### 2. Environment Setup

Clone the repository and create a virtual environment:

```bash
# Clone repository
git clone <repo-url>
cd agentic-multimodal-rag

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
# On Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 3. Configure Environment Variables

Copy the example `.env.example` to create your local `.env`:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Available configuration variables:

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PROJECT_NAME` | Name of the API application | `Multimodal RAG API` |
| `VERSION` | Current application version | `0.1.0` |
| `ENVIRONMENT` | Deployment environment (`development`, `production`, etc.) | `development` |
| `DEBUG` | Enable/disable debug mode | `false` |
| `LOG_LEVEL` | Python logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `HOST` | Server bind address | `127.0.0.1` |
| `PORT` | Server bind port | `8000` |
| `GOOGLE_API_KEY` | Google Gemini API key for embeddings | `None` |
| `GEMINI_EMBEDDING_MODEL` | Gemini embedding model name | `gemini-embedding-001` |
| `EMBEDDING_DIMENSION` | Target output vector dimensionality | `768` |

---

## Running the Backend

From the repository root, start the development server:

```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server will be available at:
- API Base URL: `http://127.0.0.1:8000`
- Interactive API Docs (Swagger UI): `http://127.0.0.1:8000/docs`
- Alternative API Docs (ReDoc): `http://127.0.0.1:8000/redoc`

---

## Health Check Endpoint

Verify application status:

```bash
curl http://127.0.0.1:8000/health
```

Response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "development"
}
```

---

## Running Tests

### 1. Offline Unit Test Suite (Default)
By default, integration tests that call external APIs are excluded:

```bash
python -m pytest backend/tests -v
```

### 2. Live Gemini API Integration Test
To run the live integration test against the real Google Gemini API (requires a valid `GOOGLE_API_KEY` in `.env`):

```bash
python -m pytest backend/tests/test_embedding_integration.py -v -m integration
```