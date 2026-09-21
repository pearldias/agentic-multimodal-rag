export default function ErrorMessage({ error, onRetry }) {
  if (!error) return null;

  const errorMessage =
    typeof error === "string"
      ? error
      : error?.message || "An unexpected error occurred while communicating with the AI service.";

  return (
    <div className="message-wrapper assistant" role="alert">
      <div className="avatar assistant-avatar error-avatar" aria-hidden="true">
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
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>

      <div className="message-bubble assistant-bubble error-bubble">
        <div className="error-card-header">
          <div className="error-title">Unable to generate a response</div>
        </div>

        <p className="error-description">{errorMessage}</p>

        {onRetry && (
          <div className="error-actions">
            <button
              type="button"
              className="retry-button"
              onClick={onRetry}
              aria-label="Retry generating response"
            >
              <svg
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
                <polyline points="23 4 23 10 17 10" />
                <polyline points="1 20 1 14 7 14" />
                <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
              </svg>
              <span>Retry</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
