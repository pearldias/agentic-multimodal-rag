# Production-Grade Multimodal RAG Chatbot

## Objective

Build a production-grade multimodal RAG chatbot that accepts TXT, PDF,
DOCX, and XLSX files, retrieves relevant information, and generates
grounded answers with source citations.

## Core Requirements

- [ ] Chat-based frontend
- [ ] Streaming responses
- [ ] Conversation history
- [ ] File upload
- [ ] Source citations
- [ ] FastAPI backend
- [ ] LangChain RAG pipeline
- [ ] Vector-based retrieval
- [ ] Reranking
- [ ] Free-tier or open-source LLM
- [ ] Embeddings
- [x] TXT parsing
- [x] PDF parsing
- [x] DOCX parsing
- [x] XLSX parsing
- [ ] MCP integration
- [ ] Docker Compose
- [ ] Kubernetes manifests
- [ ] Jenkins CI/CD
- [ ] Automated tests
- [ ] Logging and error handling
- [ ] Architecture diagram
- [ ] Complete README

## Planned Technology Stack

- Frontend: React + Vite
- Backend: FastAPI
- RAG framework: LangChain
- Workflow: LangGraph
- LLM: Google Gemini API
- Embeddings: Gemini Embeddings
- Vector database: Chroma
- Reranker: Cohere Rerank
- PDF text extraction: PyMuPDF
- OCR fallback: Tesseract OCR
- Word parsing: python-docx
- Excel parsing: pandas + openpyxl
- Database: SQLite initially
- Containerization: Docker
- Local orchestration: Docker Compose
- Deployment: Kubernetes
- CI/CD: Jenkins
- Testing: pytest

## Fallbacks

- If Gemini Embeddings are unavailable or quota-limited, use a local
  Hugging Face embedding model.
- If Cohere Rerank is unavailable or quota-limited, use a local BGE reranker.
- If OCR is unavailable, return a clear extraction error for scanned PDFs.

## Development Phases

### Phase 1: Project Foundation
- [x] Repository structure
- [x] FastAPI setup
- [x] Configuration
- [x] Logging
- [x] Health endpoint
- [x] Initial tests

### Phase 2: Document Processing
- [x] TXT parser
- [x] PDF parser
- [x] DOCX parser
- [x] XLSX parser
- [ ] Chunking
- [x] Metadata and source tracking

### Phase 3: RAG Pipeline
- [x] Embeddings
- [ ] Vector database
- [ ] Retrieval
- [ ] Reranking
- [ ] Prompt construction
- [ ] Grounded answer generation
- [ ] Citations

### Phase 4: API
- [ ] Upload endpoint
- [ ] Chat endpoint
- [ ] Document listing
- [ ] Streaming responses
- [ ] Error handling

### Phase 5: Frontend
- [ ] React setup
- [ ] Chat interface
- [ ] File upload
- [ ] Streaming display
- [ ] Conversation history
- [ ] Citation display

### Phase 6: Advanced Integration
- [ ] LangGraph workflow
- [ ] MCP server and tool
- [ ] Evaluation
- [ ] Guardrails

### Phase 7: Deployment
- [ ] Backend Dockerfile
- [ ] Frontend Dockerfile
- [ ] MCP Dockerfile
- [ ] Docker Compose
- [ ] Kubernetes manifests
- [ ] Jenkinsfile

### Phase 8: Finalization
- [ ] Tests
- [ ] README
- [ ] Architecture diagram
- [ ] Demo
- [ ] Final GitHub cleanup