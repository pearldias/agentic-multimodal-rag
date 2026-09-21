const SUGGESTIONS = [
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" aria-hidden="true">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
        <line x1="16" y1="2" x2="16" y2="6" />
        <line x1="8" y1="2" x2="8" y2="6" />
        <line x1="3" y1="10" x2="21" y2="10" />
      </svg>
    ),
    title: "Leave & Attendance",
    question: "What is the employee leave policy?",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" aria-hidden="true">
        <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="8.5" cy="7" r="4" />
        <polyline points="17 11 19 13 23 9" />
      </svg>
    ),
    title: "HR & Onboarding",
    question: "How does the employee onboarding process work?",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" aria-hidden="true">
        <polyline points="16 18 22 12 16 6" />
        <polyline points="8 6 2 12 8 18" />
      </svg>
    ),
    title: "Engineering SOP",
    question: "What are the software development standards?",
  },
  {
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18" aria-hidden="true">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      </svg>
    ),
    title: "Security & Compliance",
    question: "What cybersecurity practices are required?",
  },
];

export default function WelcomeScreen({ onSelectQuestion }) {
  return (
    <section className="welcome-screen" aria-label="Welcome and suggested questions">
      <div className="welcome-badge">
        <div className="welcome-ai-icon" aria-hidden="true">
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            width="28"
            height="28"
          >
            <path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z" />
            <path d="M16 14a6 6 0 0 0-8 0" />
            <line x1="12" y1="20" x2="12" y2="22" />
            <line x1="8" y1="22" x2="16" y2="22" />
          </svg>
        </div>
      </div>

      <h2 className="welcome-title">How can I help you?</h2>

      <p className="welcome-description">
        Ask any questions about McLaren company documents, policies, engineering standards, and HR guidelines. Answers are retrieved and grounded directly from internal documents with source citations.
      </p>

      <div className="suggestions-grid" role="region" aria-label="Suggested starter questions">
        {SUGGESTIONS.map((item, index) => (
          <button
            key={index}
            type="button"
            className="suggestion-card"
            onClick={() => onSelectQuestion(item.question)}
          >
            <div className="suggestion-icon-wrapper">{item.icon}</div>
            <div className="suggestion-text-wrapper">
              <span className="suggestion-category">{item.title}</span>
              <span className="suggestion-question">{item.question}</span>
            </div>
            <div className="suggestion-arrow" aria-hidden="true">
              <svg viewBox="0 0 20 20" fill="currentColor" width="14" height="14">
                <path
                  fillRule="evenodd"
                  d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}
