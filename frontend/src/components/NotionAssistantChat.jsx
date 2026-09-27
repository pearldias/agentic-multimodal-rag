import { useState, useRef, useEffect } from "react";
import { sendNotionChatMessage } from "../services/api";

const STARTER_PROMPTS = [
  "What tasks are currently in progress?",
  "Summarize my current tasks.",
];

/**
 * Unescapes stray markdown backslashes that might originate from raw Notion content.
 */
function cleanMarkdownText(str) {
  if (!str) return "";
  return str
    .replace(/\\-/g, "-")
    .replace(/\\\[/g, "[")
    .replace(/\\\]/g, "]")
    .replace(/\\\(/g, "(")
    .replace(/\\\)/g, ")")
    .replace(/\\\*/g, "*")
    .replace(/\\_/g, "_");
}

/**
 * Parses inline tokens: links [text](url), raw URLs, bold (**text** or __text__),
 * inline code (`code`), and italic (*text*).
 */
function renderInlineTokens(str) {
  if (!str) return null;
  const clean = cleanMarkdownText(str);

  // Match:
  // 1. [text](url) -> group 2 is text, group 3 is url
  // 2. raw url -> group 4
  // 3. **bold** or __bold__ -> group 5/6
  // 4. `code` -> group 7
  // 5. *italic* -> group 8
  const regex = /(\[([^\]]+)\]\((https?:\/\/[^\s)]+|[^\s)]+)\)|(https?:\/\/[^\s<]+[^<.,:;"')\]\s])|\*\*([^*]+?)\*\*|__([^_]+?)__|`([^`]+?)`|(?<!\*)\*([^*\s][^*]*?[^*\s]|\S)\*(?!\*))/g;

  let lastIndex = 0;
  const elements = [];
  let match;

  while ((match = regex.exec(clean)) !== null) {
    if (match.index > lastIndex) {
      elements.push(clean.substring(lastIndex, match.index));
    }

    const tokenKey = `tok-${match.index}`;

    if (match[2] && match[3]) {
      const linkText = match[2];
      const linkUrl = match[3];
      elements.push(
        <a
          key={tokenKey}
          href={linkUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="notion-chat-link"
          title={linkUrl}
        >
          <span>{linkText}</span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            width="12"
            height="12"
            aria-hidden="true"
            className="notion-chat-link-icon"
          >
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      );
    } else if (match[4]) {
      const rawUrl = match[4];
      elements.push(
        <a
          key={tokenKey}
          href={rawUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="notion-chat-link"
          title={rawUrl}
        >
          <span>{rawUrl}</span>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.2"
            width="12"
            height="12"
            aria-hidden="true"
            className="notion-chat-link-icon"
          >
            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
            <polyline points="15 3 21 3 21 9" />
            <line x1="10" y1="14" x2="21" y2="3" />
          </svg>
        </a>
      );
    } else if (match[5] || match[6]) {
      elements.push(
        <strong key={tokenKey}>
          {match[5] || match[6]}
        </strong>
      );
    } else if (match[7]) {
      elements.push(
        <code key={tokenKey} className="notion-chat-inline-code">
          {match[7]}
        </code>
      );
    } else if (match[8]) {
      elements.push(
        <em key={tokenKey}>
          {match[8]}
        </em>
      );
    }

    lastIndex = regex.lastIndex;
  }

  if (lastIndex < clean.length) {
    elements.push(clean.substring(lastIndex));
  }

  return elements.length > 0 ? elements : clean;
}

/**
 * Formats multi-line Markdown text (headings, lists, bold, links, dividers, paragraphs)
 * for the Notion Assistant.
 */
function NotionFormattedMessage({ content }) {
  if (!content) return null;

  const lines = content.split("\n");
  const nodes = [];
  let currentList = null;

  const flushList = () => {
    if (currentList) {
      if (currentList.type === "ul") {
        nodes.push(
          <ul key={`ul-${nodes.length}`} className="notion-bubble-list">
            {currentList.items.map((item, idx) => (
              <li
                key={idx}
                className={item.isSubItem ? "notion-bubble-subitem" : ""}
              >
                {renderInlineTokens(item.content)}
              </li>
            ))}
          </ul>
        );
      } else if (currentList.type === "ol") {
        nodes.push(
          <ol key={`ol-${nodes.length}`} className="notion-chat-numbered-list">
            {currentList.items.map((item, idx) => (
              <li
                key={idx}
                className={item.isSubItem ? "notion-bubble-subitem" : ""}
              >
                {renderInlineTokens(item.content)}
              </li>
            ))}
          </ol>
        );
      }
      currentList = null;
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      flushList();
      continue;
    }

    // Horizontal Rule: ---, ***, ___
    if (/^(---|___|\*\*\*)$/.test(trimmed)) {
      flushList();
      nodes.push(<hr key={`hr-${nodes.length}`} className="notion-chat-divider" />);
      continue;
    }

    // Headings: #, ##, ###, ####
    const headingMatch = trimmed.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length;
      const headingText = headingMatch[2];
      const HeadingTag = level <= 2 ? "h4" : "h5";
      nodes.push(
        <HeadingTag
          key={`h-${nodes.length}`}
          className="notion-bubble-heading"
        >
          {renderInlineTokens(headingText)}
        </HeadingTag>
      );
      continue;
    }

    // Bullet List Items: -, *, +, \- (with optional indent)
    const bulletMatch = rawLine.match(/^(\s*)(?:[-*+]|\\-)\s+(.*)$/);
    if (bulletMatch) {
      const indent = bulletMatch[1].length;
      const itemContent = bulletMatch[2];
      const isSubItem = indent >= 2;

      if (!currentList || currentList.type !== "ul") {
        flushList();
        currentList = { type: "ul", items: [] };
      }
      currentList.items.push({ content: itemContent, isSubItem });
      continue;
    }

    // Numbered List Items: 1., 2. (with optional indent)
    const numMatch = rawLine.match(/^(\s*)(\d+)\.\s+(.*)$/);
    if (numMatch) {
      const indent = numMatch[1].length;
      const itemContent = numMatch[3];
      const isSubItem = indent >= 2;

      if (!currentList || currentList.type !== "ol") {
        flushList();
        currentList = { type: "ol", items: [] };
      }
      currentList.items.push({ content: itemContent, isSubItem });
      continue;
    }

    // Regular paragraph line
    flushList();
    nodes.push(
      <p key={`p-${nodes.length}`} className="notion-bubble-para">
        {renderInlineTokens(trimmed)}
      </p>
    );
  }

  flushList();

  return <div className="notion-formatted-content">{nodes}</div>;
}

export default function NotionAssistantChat({ onOpenTask }) {
  const [messages, setMessages] = useState([
    {
      id: "welcome-1",
      role: "assistant",
      content:
        "Hello! I am your dedicated Notion Workspace Assistant.\n\nI can answer questions about your Daily Tasks, statuses, deadlines, action items, and project notes.",
    },
  ]);

  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (questionText) => {
    const q = (questionText || inputValue).trim();

    if (!q || loading) return;

    setError(null);
    setInputValue("");

    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        content: q,
      },
    ]);

    setLoading(true);

    try {
      const res = await sendNotionChatMessage(q);

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content:
            res.answer || "No response received from Notion Assistant.",
          referencedTasks: res.referenced_tasks || [],
        },
      ]);
    } catch (err) {
      console.error("Notion Assistant error:", err);

      setError(
        err.message || "Failed to communicate with Notion Assistant."
      );

      setMessages((prev) => [
        ...prev,
        {
          id: assistantMsgId,
          role: "assistant",
          content: `⚠️ Error: ${err.message || "Could not retrieve response from Notion."
            }`,
          isError: true,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "assistant",
        content:
          "Chat cleared. Ask any question about your Notion tasks, projects, or action items.",
      },
    ]);

    setError(null);
  };

  return (
    <div
      className="notion-assistant-card"
      aria-label="Notion Assistant Chat"
    >
      {/* Assistant Header */}
      <div className="notion-assistant-header">
        <div className="notion-assistant-title-group">
          <div className="notion-ai-badge-icon" aria-hidden="true">
            <svg
              viewBox="0 0 24 24"
              width="18"
              height="18"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z" />
              <path d="M16 14a6 6 0 0 0-8 0" />
              <line x1="12" y1="20" x2="12" y2="22" />
              <line x1="8" y1="22" x2="16" y2="22" />
            </svg>
          </div>

          <div>
            <h3 className="notion-assistant-title">
              Notion Assistant
            </h3>
          </div>
        </div>

        <button
          type="button"
          className="notion-clear-btn"
          onClick={handleClearChat}
          title="Clear chat history"
          disabled={loading}
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            width="14"
            height="14"
          >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>

          <span>Clear</span>
        </button>
      </div>

      {/* Suggested Starter Chips */}
      <div className="notion-starter-chips-container">
        <span className="notion-chips-label">
          Suggested Questions:
        </span>

        <div className="notion-starter-chips">
          {STARTER_PROMPTS.map((prompt, idx) => (
            <button
              key={idx}
              type="button"
              className="notion-prompt-chip"
              onClick={() => handleSend(prompt)}
              disabled={loading}
            >
              {prompt}
            </button>
          ))}
        </div>
      </div>

      {/* Optional Error Alert */}
      {error && (
        <div
          className="modal-alert alert-error"
          style={{ margin: "10px 18px 0" }}
        >
          <span>⚠️ {error}</span>
        </div>
      )}

      {/* Messages Scroll Area */}
      <div
        className="notion-chat-messages"
        role="log"
        aria-live="polite"
      >
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`notion-chat-row ${msg.role === "user"
              ? "user-row"
              : "assistant-row"
              }`}
          >
            {msg.role === "assistant" && (
              <div
                className="notion-chat-avatar"
                aria-hidden="true"
              >
                <span>N</span>
              </div>
            )}

            <div
              className={`notion-chat-bubble ${msg.role === "user"
                ? "user-bubble"
                : "assistant-bubble"
                } ${msg.isError ? "error-bubble" : ""}`}
            >
              <div className="notion-bubble-text">
                <NotionFormattedMessage content={msg.content} />
              </div>

              {msg.referencedTasks &&
                msg.referencedTasks.length > 0 && (
                  <div className="notion-ref-tasks-box">
                    <span className="notion-ref-title">
                      Referenced Notion Tasks (
                      {msg.referencedTasks.length}):
                    </span>

                    <div className="notion-ref-pills">
                      {msg.referencedTasks.map((t) => (
                        <button
                          key={t.id}
                          type="button"
                          className="notion-ref-pill"
                          onClick={() =>
                            onOpenTask &&
                            onOpenTask(t)
                          }
                          title={`View ${t.name || t.title
                            }`}
                        >
                          <span className="notion-ref-dot" />

                          <span className="notion-ref-name">
                            {t.name || t.title}
                          </span>

                          <span className="notion-ref-status">
                            ({t.status || "Open"})
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="notion-chat-row assistant-row">
            <div className="notion-chat-avatar">
              <span>N</span>
            </div>

            <div className="notion-chat-bubble assistant-bubble notion-thinking-bubble">
              <div
                className="notion-typing-indicator"
                aria-label="Querying Notion"
              >
                <span className="dot" />
                <span className="dot" />
                <span className="dot" />
              </div>

              <span className="notion-thinking-text">
                Querying Notion...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="notion-chat-input-form"
      >
        <input
          type="text"
          className="notion-chat-input"
          placeholder="Ask a question about your Notion tasks, priorities, or next steps..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          disabled={loading}
        />

        <button
          type="submit"
          className="notion-send-btn"
          disabled={
            loading || !inputValue.trim()
          }
          aria-label="Send Notion question"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            width="16"
            height="16"
          >
            <line
              x1="22"
              y1="2"
              x2="11"
              y2="13"
            />

            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </form>
    </div>
  );
}