import SourceCard from "./SourceCard";

/**
 * Format markdown-like text cleanly:
 * Converts bold (**text**), bullet points, and paragraphs into styled elements.
 */
function FormattedContent({ text }) {
  if (!text) return null;

  // Split into lines to preserve structured lists and paragraphs
  const lines = text.split("\n");
  const elements = [];
  let currentList = [];

  const flushList = () => {
    if (currentList.length > 0) {
      elements.push(
        <ul key={`ul-${elements.length}`} className="chat-bullet-list">
          {currentList.map((item, idx) => (
            <li key={idx}>{renderInline(item)}</li>
          ))}
        </ul>
      );
      currentList = [];
    }
  };

  const renderInline = (str) => {
    // Replace **bold** and [Source X] patterns
    const parts = [];
    // Regex for bold (**...**) and citation ([Source ...])
    const regex = /(\*\*.*?\*\*|\[Source\s+\d+\])/g;
    let lastIndex = 0;
    let match;

    while ((match = regex.exec(str)) !== null) {
      if (match.index > lastIndex) {
        parts.push(str.substring(lastIndex, match.index));
      }
      const token = match[0];
      if (token.startsWith("**") && token.endsWith("**")) {
        parts.push(
          <strong key={`b-${match.index}`}>
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith("[Source")) {
        parts.push(
          <span key={`src-${match.index}`} className="citation-tag">
            {token}
          </span>
        );
      }
      lastIndex = regex.lastIndex;
    }

    if (lastIndex < str.length) {
      parts.push(str.substring(lastIndex));
    }

    return parts.length > 0 ? parts : str;
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();

    if (!line) {
      flushList();
      continue;
    }

    if (line.startsWith("* ") || line.startsWith("- ")) {
      currentList.push(line.slice(2));
    } else if (/^\d+\.\s+/.test(line)) {
      flushList();
      const content = line.replace(/^\d+\.\s+/, "");
      elements.push(
        <div key={`ol-${elements.length}`} className="chat-numbered-item">
          <span className="number-bullet">{line.match(/^\d+\./)[0]}</span>
          <span>{renderInline(content)}</span>
        </div>
      );
    } else if (line.startsWith("### ")) {
      flushList();
      elements.push(
        <h4 key={`h4-${elements.length}`} className="chat-section-heading">
          {renderInline(line.slice(4))}
        </h4>
      );
    } else if (line.startsWith("## ")) {
      flushList();
      elements.push(
        <h3 key={`h3-${elements.length}`} className="chat-section-heading">
          {renderInline(line.slice(3))}
        </h3>
      );
    } else {
      flushList();
      elements.push(
        <p key={`p-${elements.length}`} className="chat-paragraph">
          {renderInline(line)}
        </p>
      );
    }
  }

  flushList();

  return <div className="formatted-text">{elements}</div>;
}

export default function ChatMessage({ message }) {
  const isUser = message.role === "user";

  const getTypeBadgeClass = (type) => {
    switch (type?.toUpperCase()) {
      case "PDF":
        return "badge-pdf";
      case "DOCX":
        return "badge-docx";
      case "XLSX":
        return "badge-xlsx";
      default:
        return "badge-generic";
    }
  };

  return (
    <div
      className={`message-wrapper ${isUser ? "user" : "assistant"}`}
      aria-label={isUser ? "Message from you" : "Message from Assistant"}
    >
      {!isUser && (
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
      )}

      <div className={`message-bubble ${isUser ? "user-bubble" : "assistant-bubble"}`}>
        <div className="sender-name">
          {isUser ? "You" : "McLaren Assistant"}
        </div>

        <div className="message-content">
          {message.attachment && (
            <div
              className="chat-attachment-card"
              role="group"
              aria-label={`Attached document: ${message.attachment.name}`}
            >
              <div className="attachment-icon-wrapper" aria-hidden="true">
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  width="18"
                  height="18"
                >
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>

              <div className="attachment-details">
                <span className="attachment-filename" title={message.attachment.name}>
                  {message.attachment.name}
                </span>
                <div className="attachment-badges">
                  <span className={`doc-type-badge ${getTypeBadgeClass(message.attachment.type)}`}>
                    {message.attachment.type}
                  </span>
                  <span className="attachment-status-badge">
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      width="12"
                      height="12"
                      className="check-icon"
                      aria-hidden="true"
                    >
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>{message.attachment.status || "Uploaded"}</span>
                  </span>
                </div>
              </div>
            </div>
          )}

          {isUser ? (
            message.content ? <p className="user-text">{message.content}</p> : null
          ) : (
            <div className="assistant-content-wrapper">
              <FormattedContent text={message.content} />
              {message.isStreaming && (
                <span className="streaming-cursor" aria-hidden="true" />
              )}
            </div>
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceCard sources={message.sources} />
        )}
      </div>

      {isUser && (
        <div className="avatar user-avatar" aria-hidden="true">
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
            <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
            <circle cx="12" cy="7" r="4" />
          </svg>
        </div>
      )}
    </div>
  );
}
