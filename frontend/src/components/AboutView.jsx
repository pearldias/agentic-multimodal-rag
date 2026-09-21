export default function AboutView() {
  const techStack = [
    {
      name: "React + Vite",
      category: "Frontend UI",
      description: "Modern component-driven chat interface with responsive layout, real-time citation rendering, and fast HMR development.",
      badge: "v19.2",
    },
    {
      name: "FastAPI",
      category: "Backend Framework",
      description: "High-performance Python ASGI backend offering robust routing, automatic validation with Pydantic, and CORS configuration.",
      badge: "Python 3.14",
    },
    {
      name: "LangChain",
      category: "Orchestration & Chunking",
      description: "Document parsing, recursive text chunking, and embedding adapter interfaces for vector store synchronization.",
      badge: "LangChain Core",
    },
    {
      name: "Google Gemini",
      category: "Foundation Models",
      description: "Gemini 3.6 Flash for grounded answer synthesis and gemini-embedding-001 for high-dimensional semantic vector embeddings.",
      badge: "Gemini 3.6 Flash",
    },
    {
      name: "ChromaDB",
      category: "Vector Database",
      description: "Embedded vector database persisting document chunk embeddings, enabling sub-second similarity search.",
      badge: "Persistent Vector Store",
    },
    {
      name: "Cohere Rerank",
      category: "Second-Stage Reranker",
      description: "State-of-the-art rerank-v4.0-fast model scores and reorders candidate chunks from ChromaDB for maximum relevance.",
      badge: "rerank-v4.0-fast",
    },
  ];

  const pipelineSteps = [
    {
      step: "01",
      title: "Document Ingestion & Parsing",
      desc: "Raw company documents (PDF, DOCX, XLSX) are parsed with PyMuPDF and python-docx, extracting clean text and page numbers.",
    },
    {
      step: "02",
      title: "Semantic Chunking & Embedding",
      desc: "Documents are split into contextual chunks and converted to 768-dimensional vectors using Gemini embedding models.",
    },
    {
      step: "03",
      title: "Vector Candidate Retrieval",
      desc: "ChromaDB performs cosine similarity search to retrieve the top 10–15 candidate chunks matching the user query.",
    },
    {
      step: "04",
      title: "Cohere Precision Reranking",
      desc: "Cohere rerank-v4.0-fast scores semantic alignment between query and candidate chunks, selecting the top 4–5 most relevant.",
    },
    {
      step: "05",
      title: "Grounded Answer Generation",
      desc: "Gemini synthesizes an answer using strictly the reranked passages and produces exact [Source X] page citations.",
    },
  ];

  return (
    <div className="about-page" aria-label="About McLaren Knowledge Assistant">
      {/* Hero Header */}
      <div className="about-hero-card">
        <div className="about-badge">RAG Architecture</div>
        <h2 className="about-title">McLaren Knowledge Assistant</h2>
        <p className="about-lead">
          An AI-powered retrieval-augmented generation system that retrieves relevant
          information from company documents and generates grounded responses with source citations.
        </p>
      </div>

      {/* Pipeline Explanation */}
      <section className="about-section">
        <h3 className="section-title">How the RAG Pipeline Works</h3>
        <p className="section-desc">
          Zero hallucination policy: The system answers solely from retrieved company documentation.
        </p>

        <div className="pipeline-grid">
          {pipelineSteps.map((item, idx) => (
            <div key={idx} className="pipeline-card">
              <span className="pipeline-step">{item.step}</span>
              <h4 className="pipeline-title">{item.title}</h4>
              <p className="pipeline-desc">{item.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Technology Stack */}
      <section className="about-section">
        <h3 className="section-title">Technology Stack</h3>
        <p className="section-desc">
          Engineered with enterprise-grade open-source and state-of-the-art AI technologies.
        </p>

        <div className="tech-stack-grid">
          {techStack.map((tech, idx) => (
            <div key={idx} className="tech-card">
              <div className="tech-card-top">
                <div>
                  <h4 className="tech-name">{tech.name}</h4>
                  <span className="tech-category">{tech.category}</span>
                </div>
                <span className="tech-badge">{tech.badge}</span>
              </div>
              <p className="tech-desc">{tech.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Project Meta */}
      <div className="about-meta-box">
        <div className="meta-item">
          <span className="meta-label">Environment</span>
          <span className="meta-value">Development (Localhost:8000)</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">LLM Model</span>
          <span className="meta-value">Gemini 3.6 Flash</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Embedding Model</span>
          <span className="meta-value">gemini-embedding-001 (768-dim)</span>
        </div>
        <div className="meta-item">
          <span className="meta-label">Status</span>
          <span className="meta-value text-green">Online & Operational</span>
        </div>
      </div>
    </div>
  );
}
