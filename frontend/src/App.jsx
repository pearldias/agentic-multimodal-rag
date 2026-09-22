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
  streamChatMessage,
  fetchConversations,
  fetchConversation,
  deleteConversation,
  uploadDocument,
  fetchDocuments,
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

  // Documents and upload state
  const [documents, setDocuments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [uploadNotification, setUploadNotification] = useState(null);

  const messagesEndRef = useRef(null);

  // Load conversation list and documents on mount
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

    fetchDocuments()
      .then((docs) => {
        if (!ignore && Array.isArray(docs) && docs.length > 0) {
          setDocuments(docs);
        }
      })
      .catch((err) => {
        console.error("Failed to load documents:", err);
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

  const refreshDocuments = useCallback(async () => {
    try {
      const docs = await fetchDocuments();
      if (Array.isArray(docs) && docs.length > 0) {
        setDocuments(docs);
      }
    } catch (err) {
      console.error("Failed to refresh documents:", err);
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

    const userMsgId = `user-${Date.now()}`;
    const assistantMsgId = `assistant-${Date.now()}`;

    // Append user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: userMsgId,
        role: "user",
        content: trimmed,
      },
    ]);

    setLoading(true);

    let streamStarted = false;

    try {
      await streamChatMessage(trimmed, undefined, currentConversationId, {
        onMetadata: (metadata) => {
          if (!currentConversationId && metadata.conversation_id) {
            setCurrentConversationId(metadata.conversation_id);
          }
          setMessages((prev) => {
            const exists = prev.some((m) => m.id === assistantMsgId);
            if (exists) {
              return prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      sources: metadata.sources || [],
                      retrievedDocuments: metadata.retrieved_documents || 0,
                    }
                  : m
              );
            }
            return [
              ...prev,
              {
                id: assistantMsgId,
                role: "assistant",
                content: "",
                sources: metadata.sources || [],
                retrievedDocuments: metadata.retrieved_documents || 0,
                isStreaming: true,
              },
            ];
          });
        },
        onToken: (token) => {
          if (!streamStarted) {
            streamStarted = true;
            setLoading(false);
          }
          setMessages((prev) => {
            const exists = prev.some((m) => m.id === assistantMsgId);
            if (exists) {
              return prev.map((m) =>
                m.id === assistantMsgId
                  ? {
                      ...m,
                      content: m.content + token,
                      isStreaming: true,
                    }
                  : m
              );
            }
            return [
              ...prev,
              {
                id: assistantMsgId,
                role: "assistant",
                content: token,
                sources: [],
                retrievedDocuments: 0,
                isStreaming: true,
              },
            ];
          });
        },
        onDone: async (doneData) => {
          setLoading(false);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantMsgId
                ? {
                    ...m,
                    content: doneData.answer || m.content,
                    sources: doneData.sources || m.sources,
                    isStreaming: false,
                  }
                : m
            )
          );
          if (!currentConversationId && doneData.conversation_id) {
            setCurrentConversationId(doneData.conversation_id);
          }
          await refreshConversations();
        },
        onError: (err) => {
          setLoading(false);
          setMessages((prev) =>
            prev.filter((m) => m.id !== assistantMsgId || m.content.trim().length > 0)
          );
          setError({
            message: err.message,
            question: trimmed,
          });
        },
      });
    } catch (err) {
      console.error("Chat streaming error occurred:", err);
      setLoading(false);
      setMessages((prev) =>
        prev.filter((msg) => msg.id !== assistantMsgId || msg.content.trim().length > 0)
      );
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

  const handleUploadFile = async (file) => {
    if (!file || uploading) return;

    const allowedExtensions = [".pdf", ".docx", ".xlsx", ".txt"];
    const ext = "." + file.name.split(".").pop().toLowerCase();
    if (!allowedExtensions.includes(ext)) {
      setUploadNotification({
        type: "error",
        message: `Unsupported file format "${ext}". Please upload a PDF, DOCX, XLSX, or TXT document.`,
      });
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      setUploadNotification({
        type: "error",
        message: `File "${file.name}" exceeds the maximum size limit of 10 MB.`,
      });
      return;
    }

    setUploading(true);
    setUploadNotification({
      type: "loading",
      message: `Uploading and indexing "${file.name}" into ChromaDB...`,
    });

    try {
      const result = await uploadDocument(file);
      const chunkCount = result.chunks_stored || result.chunks_created || 0;
      setUploadNotification({
        type: "success",
        message: `"${file.name}" uploaded and indexed successfully (${chunkCount} chunks created).`,
      });

      await refreshDocuments();

      setTimeout(() => {
        setUploadNotification((prev) =>
          prev?.type === "success" ? null : prev
        );
      }, 5000);
    } catch (err) {
      console.error("Upload failed:", err);
      setUploadNotification({
        type: "error",
        message: err.message || `Failed to process and index "${file.name}".`,
      });
    } finally {
      setUploading(false);
    }
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
        documentCount={documents.length || 20}
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

        {/* Upload Status Notification Toast */}
        {uploadNotification && (
          <div
            className={`upload-notification-toast toast-${uploadNotification.type}`}
            role="status"
            aria-live="polite"
          >
            <div className="toast-content">
              {uploadNotification.type === "loading" && (
                <div className="upload-spinner-sm" aria-label="Indexing" />
              )}
              {uploadNotification.type === "success" && (
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  width="16"
                  height="16"
                  className="toast-icon toast-success-icon"
                  aria-hidden="true"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
              {uploadNotification.type === "error" && (
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  width="16"
                  height="16"
                  className="toast-icon toast-error-icon"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              )}
              <span className="toast-message">{uploadNotification.message}</span>
            </div>

            {uploadNotification.type !== "loading" && (
              <button
                type="button"
                className="toast-close-btn"
                onClick={() => setUploadNotification(null)}
                aria-label="Dismiss notification"
              >
                &times;
              </button>
            )}
          </div>
        )}

        <main className="content-area">
          {activeTab === "documents" && (
            <DocumentsView
              documents={documents}
              onAskQuestion={(q) => {
                setActiveTab("chat");
                handleSendMessage(q);
              }}
              onUploadFile={handleUploadFile}
              uploading={uploading}
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
                onUploadFile={handleUploadFile}
                disabled={loading}
                uploading={uploading}
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;