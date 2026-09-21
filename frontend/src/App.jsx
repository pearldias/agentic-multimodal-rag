import { useState, useRef, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import WelcomeScreen from "./components/WelcomeScreen";
import ChatMessage from "./components/ChatMessage";
import ChatInput from "./components/ChatInput";
import LoadingIndicator from "./components/LoadingIndicator";
import ErrorMessage from "./components/ErrorMessage";
import DocumentsView from "./components/DocumentsView";
import AboutView from "./components/AboutView";
import {
  sendChatMessage,
  fetchConversations,
  fetchConversation,
  deleteConversation,
} from "./services/api";
import "./App.css";

function App() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastQuestion, setLastQuestion] = useState("");
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Conversation history state
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [conversations, setConversations] = useState([]);

  const messagesEndRef = useRef(null);

  // Load conversation list on mount
  useEffect(() => {
    let ignore = false;
    fetchConversations()
      .then((list) => {
        if (!ignore) {
          setConversations(list || []);
        }
      })
      .catch((err) => {
        console.error("Failed to load conversations:", err);
      });
    return () => {
      ignore = true;
    };
  }, []);

  const refreshConversations = useCallback(async () => {
    try {
      const list = await fetchConversations();
      setConversations(list || []);
    } catch (err) {
      console.error("Failed to refresh conversations:", err);
    }
  }, []);

  // Auto-scroll to bottom whenever messages or loading state changes
  useEffect(() => {
    if (activeTab === "chat") {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, error, activeTab]);

  const handleSendMessage = async (userQuestion) => {
    const trimmed = userQuestion.trim();
    if (!trimmed || loading) return;

    // Reset error on new attempt
    setError(null);
    setLastQuestion(trimmed);

    // Switch to chat view if triggered from Documents or Welcome
    setActiveTab("chat");

    // Append user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content: trimmed,
      },
    ]);

    setLoading(true);

    try {
      const data = await sendChatMessage(trimmed, undefined, currentConversationId);

      // If new session, set active conversation ID
      if (!currentConversationId && data.conversation_id) {
        setCurrentConversationId(data.conversation_id);
      }

      setMessages((prev) => [
        ...prev,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          retrievedDocuments: data.retrieved_documents,
        },
      ]);

      // Refresh recent conversations list so new chat or update appears
      await refreshConversations();
    } catch (err) {
      console.error("Chat error occurred:", err);
      setError({
        message: err.message,
        question: trimmed,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleSelectConversation = async (convId) => {
    if (convId === currentConversationId || loading) return;

    setError(null);
    setLoading(true);
    try {
      const detail = await fetchConversation(convId);
      setCurrentConversationId(convId);

      const restoredMessages = (detail.messages || []).map((m) => ({
        id: m.id,
        role: m.role,
        content: m.content,
        sources: m.sources || [],
        retrievedDocuments: m.sources ? m.sources.length : 0,
      }));

      setMessages(restoredMessages);
      setActiveTab("chat");
      setLastQuestion("");
    } catch (err) {
      console.error("Failed to restore conversation:", err);
      setError({
        message: "Failed to load conversation history.",
        question: "",
      });
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteConversation = async (convId) => {
    try {
      await deleteConversation(convId);
      setConversations((prev) => prev.filter((c) => c.id !== convId));

      // If the deleted conversation was the active one, start fresh
      if (currentConversationId === convId) {
        setCurrentConversationId(null);
        setMessages([]);
        setError(null);
        setLastQuestion("");
        setActiveTab("chat");
      }
    } catch (err) {
      console.error("Failed to delete conversation:", err);
    }
  };

  const handleRetry = () => {
    if (lastQuestion) {
      setError(null);
      // Remove last user message if we are retrying to avoid duplicate display
      setMessages((prev) => {
        if (prev.length > 0 && prev[prev.length - 1].role === "user") {
          return prev.slice(0, -1);
        }
        return prev;
      });
      handleSendMessage(lastQuestion);
    }
  };

  const handleNewChat = () => {
    setCurrentConversationId(null);
    setMessages([]);
    setError(null);
    setLastQuestion("");
    setActiveTab("chat");
  };

  return (
    <div className="app-shell">
      {/* Sidebar Navigation */}
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        activeTab={activeTab}
        onSelectTab={setActiveTab}
        onNewChat={handleNewChat}
        documentCount={20}
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      {/* Main Workspace */}
      <div className="workspace-container">
        <Header
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          activeTab={activeTab}
        />

        <main className="content-area">
          {activeTab === "documents" && (
            <DocumentsView
              onAskQuestion={(q) => {
                setActiveTab("chat");
                handleSendMessage(q);
              }}
            />
          )}

          {activeTab === "about" && <AboutView />}

          {activeTab === "chat" && (
            <div className="chat-interface">
              <div className="messages-scroll-area">
                {messages.length === 0 ? (
                  <WelcomeScreen onSelectQuestion={handleSendMessage} />
                ) : (
                  <div className="messages-list" role="log" aria-live="polite">
                    {messages.map((msg) => (
                      <ChatMessage key={msg.id} message={msg} />
                    ))}

                    {loading && <LoadingIndicator />}

                    {error && (
                      <ErrorMessage
                        error={error}
                        onRetry={handleRetry}
                      />
                    )}

                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              {/* Sticky Chat Input Box */}
              <ChatInput
                onSendMessage={handleSendMessage}
                disabled={loading}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;