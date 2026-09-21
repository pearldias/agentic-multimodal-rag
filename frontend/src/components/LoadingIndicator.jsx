export default function LoadingIndicator() {
  return (
    <div className="message-wrapper assistant" aria-live="polite" aria-label="Assistant is thinking">
      <div className="avatar assistant-avatar" aria-hidden="true">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          width="16"
          height="16"
        >
          <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z" />
          <path d="M16 14a6 6 0 0 0-8 0" />
          <line x1="12" y1="20" x2="12" y2="22" />
          <line x1="8" y1="22" x2="16" y2="22" />
        </svg>
      </div>

      <div className="message-bubble assistant-bubble loading-bubble">
        <div className="sender-name">Assistant</div>
        <div className="typing-indicator" aria-label="Loading response">
          <span className="typing-dot" />
          <span className="typing-dot" />
          <span className="typing-dot" />
        </div>
        <span className="loading-status-text">Searching documents & generating answer...</span>
      </div>
    </div>
  );
}
