export default function Sidebar({
  isOpen,
  onClose,
  activeTab,
  onSelectTab,
  onNewChat,
  documentCount = 20,
  conversations = [],
  currentConversationId = null,
  onSelectConversation,
  onDeleteConversation,
}) {
  const handleNavClick = (tab) => {
    onSelectTab(tab);
    if (window.innerWidth <= 768) {
      onClose();
    }
  };

  const handleNewChatClick = () => {
    onNewChat();
    if (window.innerWidth <= 768) {
      onClose();
    }
  };

  return (
    <>
      {/* Backdrop for mobile drawer */}
      <div
        className={`sidebar-backdrop ${isOpen ? "visible" : ""}`}
        onClick={onClose}
        aria-hidden="true"
      />

      <aside
        className={`sidebar ${isOpen ? "open" : ""}`}
        aria-label="Sidebar navigation"
      >
        {/* Brand Header */}
        <div className="sidebar-header">
          <div className="brand-logo-wrapper">
            <div className="brand-icon">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                width="20"
                height="20"
                aria-hidden="true"
              >
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
            </div>
            <div className="brand-text">
              <span className="brand-name">McLaren</span>
              <span className="brand-tag">Knowledge AI</span>
            </div>
          </div>

          <button
            type="button"
            className="sidebar-close-btn"
            onClick={onClose}
            aria-label="Close sidebar navigation"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              width="18"
              height="18"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {/* New Chat Button */}
        <div className="sidebar-action-container">
          <button
            type="button"
            className="new-chat-button"
            onClick={handleNewChatClick}
            aria-label="Start a new chat session"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="16"
              height="16"
              aria-hidden="true"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            <span>New Chat</span>
          </button>
        </div>

        {/* Navigation Items */}
        <nav className="sidebar-nav" aria-label="Main menu">
          <div className="nav-group-title">WORKSPACE</div>

          <button
            type="button"
            className={`nav-item ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => handleNavClick("chat")}
            aria-current={activeTab === "chat" ? "page" : undefined}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
            <span className="nav-label">Chat</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "documents" ? "active" : ""}`}
            onClick={() => handleNavClick("documents")}
            aria-current={activeTab === "documents" ? "page" : undefined}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <polyline points="10 9 9 9 8 9" />
            </svg>
            <span className="nav-label">Documents</span>
            <span className="nav-badge">{documentCount}</span>
          </button>

          <button
            type="button"
            className={`nav-item ${activeTab === "about" ? "active" : ""}`}
            onClick={() => handleNavClick("about")}
            aria-current={activeTab === "about" ? "page" : undefined}
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="18"
              height="18"
              aria-hidden="true"
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <span className="nav-label">About</span>
          </button>
        </nav>

        {/* Recent Chats Section */}
        <div className="sidebar-recent-section">
          <div className="nav-group-title recent-title">
            <span>RECENT CHATS</span>
            {conversations && conversations.length > 0 && (
              <span className="recent-count">{conversations.length}</span>
            )}
          </div>

          <div className="recent-chats-list" role="list">
            {!conversations || conversations.length === 0 ? (
              <div className="recent-empty-state">No recent chats</div>
            ) : (
              conversations.map((conv) => {
                const isActive = conv.id === currentConversationId;
                return (
                  <div
                    key={conv.id}
                    className={`recent-chat-item ${isActive ? "active" : ""}`}
                    onClick={() => {
                      if (onSelectConversation) {
                        onSelectConversation(conv.id);
                      }
                      if (window.innerWidth <= 768) {
                        onClose();
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        if (onSelectConversation) onSelectConversation(conv.id);
                      }
                    }}
                    aria-label={`Open conversation: ${conv.title}`}
                  >
                    <svg
                      className="recent-chat-icon"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      width="15"
                      height="15"
                      aria-hidden="true"
                    >
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>

                    <span className="recent-chat-title" title={conv.title}>
                      {conv.title}
                    </span>

                    <button
                      type="button"
                      className="recent-chat-delete-btn"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onDeleteConversation) {
                          onDeleteConversation(conv.id);
                        }
                      }}
                      title="Delete conversation"
                      aria-label={`Delete conversation ${conv.title}`}
                    >
                      <svg
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        width="13"
                        height="13"
                      >
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* System Status Indicator */}
        <div className="sidebar-status-box">
          <div className="status-indicator-header">
            <span className="status-ping" />
            <span className="status-title">RAG Assistant</span>
          </div>
          <p className="status-sub">ChromaDB Vector Store Connected</p>
        </div>

        {/* Footer */}
        <div className="sidebar-footer">
          <div className="footer-powered">Powered by AI</div>
          <div className="footer-version">Version 0.1.0</div>
        </div>
      </aside>
    </>
  );
}
