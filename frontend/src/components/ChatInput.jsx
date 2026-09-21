import { useState, useRef, useEffect } from "react";

export default function ChatInput({ onSendMessage, disabled }) {
  const [text, setText] = useState("");
  const textareaRef = useRef(null);

  // Auto-resize textarea height based on content up to 160px
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 160)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    e?.preventDefault();
    const query = text.trim();
    if (!query || disabled) return;

    onSendMessage(query);
    setText("");

    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.focus();
    }
  };

  const handleKeyDown = (e) => {
    // Enter without shift sends the message
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-input-wrapper">
      <form className="chat-input-form" onSubmit={handleSubmit}>
        <div className="input-box-container">
          <textarea
            ref={textareaRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask anything about company knowledge, policies, or SOPs..."
            disabled={disabled}
            aria-label="Ask a question"
            className="chat-textarea"
          />

          <div className="input-actions">
            {/* Attachment Button UI (Disabled with tooltip) */}
            <button
              type="button"
              className="action-icon-btn attachment-btn"
              disabled
              title="Document attachment (Upload API integration coming soon)"
              aria-label="Attach document"
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
                <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>

            {/* Send Button */}
            <button
              type="submit"
              className={`send-button ${text.trim() && !disabled ? "active" : ""}`}
              disabled={!text.trim() || disabled}
              aria-label="Send message"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                width="16"
                height="16"
                aria-hidden="true"
              >
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            </button>
          </div>
        </div>

        <div className="input-footer-note">
          <span className="privacy-badge">Enterprise Search</span>
          <span>AI-generated answers are based on retrieved company documents.</span>
        </div>
      </form>
    </div>
  );
}
