# LexiRAG Development Changelog & Implementation Log

This document provides a comprehensive log of all architectural changes, additions, and milestones completed so far for the **LexiRAG — Indian Legal Document Research Assistant** (Production-Grade Multimodal RAG Chatbot).

---

## 1. Project Overview & Progress Summary

To date, **three milestones** have been implemented and validated with automated unit and integration tests:

| Milestone | Focus Area | Status | Test Coverage |
| :--- | :--- | :--- | :--- |
| **Milestone 1** | Project Foundation (FastAPI, Lifespan, Config, Logging, Health Route) | Completed | 1 passed |
| **Milestone 2** | Embedding Service (Gemini API, 768-dim Vectors, Validation, Secret Masking) | Completed | 12 passed, 1 deselected (live) |
| **Milestone 3** | Document Ingestion Foundation (TXT, PDF, DOCX, XLSX Parsers, Legal Normalization, Validation, Metadata) | Completed | 18 passed |
| **Total** | Full Test Suite | **31 Passed, 1 Deselected (live), 0 Failures** | |

---

## 2. Milestone 3 Detailed Change Log

### A. Data Directory Foundation & Storage
- **`data/raw/.gitkeep`** [NEW]: Created to serve as the local repository dropzone for raw incoming legal files (judgments, gazettes, acts, agreements).
- **`data/processed/.gitkeep`** [NEW]: Created for storing parsed and normalized JSON documents ready for chunking.
- **`data/metadata/.gitkeep`** [NEW]: Created for storing standalone metadata JSON files for fast querying and indexing.
- **`.gitignore`** [MODIFIED]: Added ignore rules for `data/raw/*`, `data/processed/*`, and `data/metadata/*`, while explicitly keeping `.gitkeep` tracked so clean directories exist on fresh clones.

### B. Dependency Management
- **`backend/requirements.txt`** [MODIFIED]: Added bounded versions for document extraction libraries:
  - `pymupdf>=1.25.0,<2.0.0`: High-speed PDF text and page metadata extraction.
  - `python-docx>=1.1.0,<2.0.0`: Word document parsing for paragraphs and tables.
  - `openpyxl>=3.1.5,<4.0.0`: Excel spreadsheet parsing for multi-sheet schedules.
  - *Design Decision*: In accordance with architectural review, `pandas` was excluded to maintain minimal dependencies, avoid heavy binary overhead, and reduce cold-start latency.

### C. Application Configuration & Startup Cleanliness
- **`backend/app/core/config.py`** [MODIFIED]:
  - Added path attributes to `Settings`: `BASE_DIR`, `DATA_DIR`, `RAW_DATA_DIR`, `PROCESSED_DATA_DIR`, `METADATA_DIR`.
  - *Design Decision*: Directory creation side-effects (`mkdir`) were strictly omitted from `config.py` import time. Directories are only created explicitly when the ingestion or setup service runs.

### D. Custom Ingestion Exceptions
- **`backend/app/core/exceptions.py`** [NEW]: Created domain-specific exception classes inheriting from `DocumentIngestionError`:
  - `UnsupportedFileTypeError`: Raised when an unhandled file extension (e.g. `.zip`, `.exe`, `.jpg`) is supplied.
  - `EmptyDocumentError`: Raised when a file is 0 bytes, has 0 pages, or contains only whitespace/blank text.
  - `CorruptedDocumentError`: Raised when a file header is malformed, encrypted, or unreadable by underlying parsers.

### E. Practical Domain Models (Pydantic v2)
- **`backend/app/models/__init__.py`** [NEW]: Model package exports.
- **`backend/app/models/document.py`** [NEW]:
  - `DocumentType(str, Enum)`: Supported types (`txt`, `pdf`, `docx`, `xlsx`).
  - `DocumentMetadata(BaseModel)`: Captures `filename`, `file_type`, `title`, `source_url`, `ingestion_timestamp` (ISO 8601 UTC), `file_size_bytes`, `total_pages`, and extensible `extra` metadata.
  - `ParsedPage(BaseModel)`: Represents an individual page (PDF/DOCX/TXT) or sheet (XLSX), containing normalized `text`, `page_number`, `sheet_name`, and page-level metadata.
  - `ParsedDocument(BaseModel)`: Root document container holding `metadata`, list of `pages`, and consolidated `raw_text`.

### F. Legal Text Normalization & Structure Preservation
- **`backend/app/services/document_parser/normalizer.py`** [NEW]:
  - `normalize_unicode`: Performs `NFKC` normalization, replaces invisible characters/BOM, converts typographic double/single curly quotes (`“` `”` $\rightarrow$ `"`, `‘` `’` $\rightarrow$ `'`), and standardizes em/en dashes.
  - `repair_hyphenation`: Repairs line-broken legal terms common in justified court judgment columns (e.g., `constitu-\ntional` $\rightarrow$ `constitutional`) without affecting bullet points or hyphenated statute names.
  - `normalize_legal_text`: Standardizes line endings (`\r\n` $\rightarrow$ `\n`), trims trailing whitespace per line while preserving indentation for sub-clauses, and collapses 3+ consecutive newlines to 2. It strictly preserves section titles, paragraph breaks, and numbered legal clauses like `1.`, `(a)`, `(i)`.
  - `format_table_as_markdown`: Converts tabular data from Excel sheets and Word tables into structured Markdown tables with headers and separators to maintain column alignment for vector retrieval.

### G. Modular Parsers (Strategy Pattern)
- **`backend/app/services/document_parser/base.py`** [NEW]: Abstract base class `BaseDocumentParser` defining `supported_extensions` and `parse(file_path: Path, **kwargs) -> ParsedDocument`.
- **`backend/app/services/document_parser/txt_parser.py`** [NEW]: Reads plain text / markdown files with UTF-8 priority and fallbacks to Latin-1/CP1252. Emits a single `ParsedPage` with 1-indexed page attribution.
- **`backend/app/services/document_parser/pdf_parser.py`** [NEW]: Uses PyMuPDF (`fitz`) to iterate through pages, extracting normalized text, recording 1-indexed `page_number`, and capturing embedded PDF metadata (title, author, creation date).
- **`backend/app/services/document_parser/docx_parser.py`** [NEW]: Uses `python-docx` to iterate over document body XML elements (`CT_P` and `CT_Tbl`), ensuring the sequential reading order between paragraphs and legal tables is preserved.
- **`backend/app/services/document_parser/xlsx_parser.py`** [NEW]: Uses `openpyxl` with `data_only=True` to read spreadsheet sheets, skip empty sheets, tag each sheet with `sheet_name`, and format tabular data into Markdown tables.
- **`backend/app/services/document_parser/service.py`** [NEW]: Central `DocumentParserService` facade providing:
  - File existence and format extension validation.
  - Routing to registered parser strategies.
  - `ensure_data_directories()` for explicit folder creation.
  - `save_parsed_document(parsed_doc, doc_id)` for persisting normalized JSON to `data/processed/` and metadata to `data/metadata/`.
- **`backend/app/services/document_parser/__init__.py`** [NEW]: Package exports.
- **`backend/app/services/__init__.py`** [MODIFIED]: Cleanly exports `EmbeddingService` and `DocumentParserService`.

### H. Test Suite
- **`backend/tests/test_document_parser.py`** [NEW]: 18 comprehensive, deterministic, offline unit tests:
  - **Normalization**: Unicode ligatures, smart quotes, hyphenation repair, preservation of section numbers `(1)`, `(a)`, `(i)`, newline preservation, and markdown tables.
  - **Validation**: Missing files (`FileNotFoundError`), unsupported extensions (`UnsupportedFileTypeError`), 0-byte files (`EmptyDocumentError`), whitespace-only files (`EmptyDocumentError`), and corrupted files (`CorruptedDocumentError` for PDF, DOCX, XLSX).
  - **Parsers**: Plain text parsing, multi-page PDF with page numbers, DOCX paragraph/table reading order, and XLSX multi-sheet extraction.
  - **Storage & Metadata**: Explicit directory creation and JSON file persistence.

### I. Roadmap Tracking
- **`PLAN.md`** [MODIFIED]: Checked off completed tasks for Phase 2 (TXT parser, PDF parser, DOCX parser, XLSX parser, and Metadata/source tracking).

---

## 3. How Milestone 3 Connects to the Overall RAG Architecture

```
[ Raw Legal Document ] (PDF, DOCX, XLSX, TXT)
        │
        ▼
[ DocumentParserService ] (Milestone 3)
  ├─ Validates format & file integrity
  ├─ Normalizes text (Unicode NFKC, legal clauses, tables)
  ├─ Enriches metadata (source_url, page_number, sheet_name, timestamp)
  └─ Explicitly persists to data/processed and data/metadata
        │
        ▼
[ ParsedDocument / ParsedPage Objects ]
        │
        ▼  [Upcoming Milestone 4: Legal-Aware Chunking]
[ Text Chunks with Granular Citations ]
        │
        ▼  [Milestone 2 Integration]
[ EmbeddingService.embed_documents([chunk.text]) ]
        │
        ▼  [Upcoming Milestone 4: Vector Storage]
[ ChromaDB / Vector Store ]
```

Milestone 3 guarantees that all text fed into `EmbeddingService` is non-empty, clean, and structurally coherent, while preserving granular page and sheet attributions necessary for legal citations in downstream LLM responses.
