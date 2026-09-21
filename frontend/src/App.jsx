import { useState } from "react";
import axios from "axios";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  const askQuestion = async (event) => {
    event.preventDefault();

    if (!question.trim() || loading) return;

    const userQuestion = question.trim();

    setMessages((previous) => [
      ...previous,
      {
        role: "user",
        content: userQuestion,
      },
    ]);

    setQuestion("");
    setLoading(true);

    try {
      const response = await axios.post(`${API_URL}/api/chat`, {
        question: userQuestion,
      });

      const data = response.data;

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
        },
      ]);
    } catch (error) {
      console.error("Chat error:", error);

      const errorMessage =
        (typeof error.response?.data?.detail === "string" && error.response.data.detail) ||
        "Sorry, something went wrong while processing your question. Please check whether the backend is running.";

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: errorMessage,
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>McLaren Knowledge Assistant</h1>
          <p>Ask questions about company documents and policies.</p>
        </div>
      </header>

      <main className="chat-container">
        {messages.length === 0 && (
          <section className="welcome-card">
            <h2>How can I help you?</h2>
            <p>
              Ask about employee policies, onboarding, projects, leave,
              training, cybersecurity, and other company documents.
            </p>

            <div className="example-questions">
              <button
                onClick={() =>
                  setQuestion("What is the employee leave policy?")
                }
              >
                What is the employee leave policy?
              </button>

              <button
                onClick={() =>
                  setQuestion("Explain the employee onboarding process.")
                }
              >
                Explain the employee onboarding process.
              </button>

              <button
                onClick={() =>
                  setQuestion("What are the software development standards?")
                }
              >
                What are the software development standards?
              </button>
            </div>
          </section>
        )}

        <section className="messages">
          {messages.map((message, index) => (
            <div
              className={`message ${message.role === "user" ? "user-message" : "assistant-message"
                }`}
              key={index}
            >
              <div className="message-role">
                {message.role === "user" ? "You" : "Assistant"}
              </div>

              <div className="message-content">{message.content}</div>

              {message.sources && message.sources.length > 0 && (
                <div className="sources">
                  <h4>Sources</h4>

                  {message.sources.map((source, sourceIndex) => (
                    <div className="source-item" key={sourceIndex}>
                      <strong>
                        {source.filename || source.source || "Document"}
                      </strong>

                      {source.page && (
                        <span> — Page {source.page}</span>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="message assistant-message">
              <div className="message-role">Assistant</div>
              <div className="message-content loading">
                Thinking...
              </div>
            </div>
          )}
        </section>
      </main>

      <form className="chat-input-area" onSubmit={askQuestion}>
        <input
          type="text"
          placeholder="Ask a question about company documents..."
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          disabled={loading}
        />

        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? "Sending..." : "Send"}
        </button>
      </form>
    </div>
  );
}

export default App;