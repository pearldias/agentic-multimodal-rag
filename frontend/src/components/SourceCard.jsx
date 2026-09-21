import { useState } from "react";

export default function SourceCard({ sources }) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!sources || sources.length === 0) {
    return null;
  }

  const toggleExpand = () => {
    setIsExpanded((prev) => !prev);
  };

  return (
    <div className="sources-container">
      <button
        type="button"
        className="sources-toggle-btn"
        onClick={toggleExpand}
        aria-expanded={isExpanded}
        aria-label={`Toggle sources list, ${sources.length} sources available`}
      >
        <span className="sources-toggle-left">
          <svg
            className="sources-icon"
            viewBox="0 0 20 20"
            fill="currentColor"
            width="16"
            height="16"
            aria-hidden="true"
          >
            <path d="M9 2a2 2 0 00-2 2v8a2 2 0 002 2h6a2 2 0 002-2V6.414A2 2 0 0016.414 5L14 2.586A2 2 0 0012.586 2H9z" />
            <path d="M3 8a2 2 0 012-2v10h8a2 2 0 01-2 2H5a2 2 0 01-2-2V8z" />
          </svg>
          <span className="sources-title">
            Sources ({sources.length})
          </span>
        </span>

        <svg
          className={`sources-arrow ${isExpanded ? "rotated" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          width="16"
          height="16"
          aria-hidden="true"
        >
          <path
            fillRule="evenodd"
            d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isExpanded && (
        <div className="sources-grid" role="region" aria-label="Cited sources">
          {sources.map((source, index) => {
            const pageNumber = source.page ?? source.page_number;
            const filename = source.filename || "Document";
            const title = source.title && source.title !== "Untitled document" ? source.title : null;

            return (
              <div
                key={source.source_id || index}
                className="source-card"
                title={title || filename}
              >
                <div className="source-card-header">
                  <span className="source-number">
                    Source {source.source_id || index + 1}
                  </span>
                  {pageNumber != null && (
                    <span className="source-page-badge">
                      Page {pageNumber}
                    </span>
                  )}
                </div>

                <div className="source-filename">
                  <svg
                    className="doc-file-icon"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    width="14"
                    height="14"
                    aria-hidden="true"
                  >
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                  <span className="filename-text" title={filename}>
                    {filename}
                  </span>
                </div>

                {title && (
                  <div className="source-doc-title" title={title}>
                    {title}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
