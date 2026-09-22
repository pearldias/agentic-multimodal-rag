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
          {isUser ? (
            <p className="user-text">{message.content}</p>
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
