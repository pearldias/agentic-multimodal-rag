export default function Header({ onToggleSidebar, activeTab }) {
  const getTitle = () => {
    switch (activeTab) {
      case "documents":
        return "Knowledge Base Documents";
      case "about":
        return "About McLaren Knowledge Assistant";
      case "chat":
      default:
        return "McLaren Knowledge Assistant";
    }
  };

  const getSubtitle = () => {
    switch (activeTab) {
      case "documents":
        return "Catalog of indexed company policies, guides, and engineering standards.";
      case "about":
        return "Architecture, design, and capabilities of the RAG system.";
      case "chat":
      default:
        return "Ask questions about company documents, policies, processes, and knowledge.";
    }
  };

  return (
    <header className="top-header">
      <div className="header-left">
        <button
          type="button"
          className="mobile-menu-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            width="20"
            height="20"
            aria-hidden="true"
          >
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>

        <div className="header-title-block">
          <h1 className="header-title">{getTitle()}</h1>
          <p className="header-subtitle">{getSubtitle()}</p>
        </div>
      </div>

      <div className="header-right">
        <div className="status-pill" title="Backend connected & RAG pipeline ready">
          <span className="status-dot-pulse" aria-hidden="true" />
          <span className="status-text">AI Assistant Online</span>
        </div>
      </div>
    </header>
  );
}
