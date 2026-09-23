import axios from "axios";

const API_BASE_URL =
  import.meta.env.VITE_API_URL !== undefined
    ? import.meta.env.VITE_API_URL
    : import.meta.env.DEV
    ? "http://127.0.0.1:8000"
    : "";

/**
 * Send a question to the RAG backend with optional conversation session.
 * @param {string} question - The user query.
 * @param {number} [k] - Number of chunks to retrieve.
 * @param {string|null} [conversationId] - Optional conversation session ID.
 * @returns {Promise<{conversation_id: string, question: string, answer: string, sources: Array, retrieved_documents: number}>}
 */
export async function sendChatMessage(question, k, conversationId) {
  try {
    const payload = { question: question.trim() };
    if (k != null) {
      payload.k = k;
    }
    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    const response = await axios.post(
      `${API_BASE_URL}/api/chat`,
      payload,
      {
        headers: {
          "Content-Type": "application/json",
        },
        timeout: 60000,
      }
    );

    return response.data;
  } catch (error) {
    console.error("API error during chat request:", error);

    let message = "Unable to process your request at this time.";
    const status = error.response?.status || 0;

    if (typeof error.response?.data?.detail === "string") {
      message = error.response.data.detail;
    } else if (error.code === "ECONNABORTED") {
      message = "Request timed out. The server took too long to respond.";
    } else if (!error.response) {
      message =
        "Cannot connect to the backend server. Please ensure the backend is running on http://127.0.0.1:8000.";
    }

    const err = new Error(message);
    err.status = status;
    err.originalError = error;
    throw err;
  }
}

/**
 * Stream a question to the RAG backend using Server-Sent Events (SSE).
 * @param {string} question - The user query.
 * @param {number} [k] - Number of chunks to retrieve.
 * @param {string|null} [conversationId] - Optional conversation session ID.
 * @param {object} callbacks - Stream event callbacks.
 * @param {function} [callbacks.onMetadata] - Called with initial metadata {conversation_id, sources, retrieved_documents}.
 * @param {function} [callbacks.onToken] - Called for each text chunk/token.
 * @param {function} [callbacks.onDone] - Called when streaming finishes {conversation_id, answer, sources}.
 * @param {function} [callbacks.onError] - Called if an error event is received or thrown.
 * @param {AbortSignal} [callbacks.signal] - Optional abort signal.
 */
export async function streamChatMessage(
  question,
  k,
  conversationId,
  { onMetadata, onToken, onDone, onError, signal } = {}
) {
  try {
    const payload = { question: question.trim() };
    if (k != null) {
      payload.k = k;
    }
    if (conversationId) {
      payload.conversation_id = conversationId;
    }

    const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      signal,
    });

    if (!response.ok) {
      let errorDetail = "Unable to process your request at this time.";
      try {
        const errorJson = await response.json();
        if (typeof errorJson?.detail === "string") {
          errorDetail = errorJson.detail;
        }
      } catch {
        // Fallback to HTTP status text if json parse fails
        errorDetail = `Server returned error (${response.status} ${response.statusText})`;
      }
      const err = new Error(errorDetail);
      err.status = response.status;
      if (onError) {
        onError(err);
      }
      throw err;
    }

    if (!response.body) {
      throw new Error("Response body is missing from streaming endpoint.");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith("data:")) continue;

        const jsonStr = trimmed.replace(/^data:\s*/, "");
        let data = null;
        try {
          data = JSON.parse(jsonStr);
          if (data.type === "metadata") {
            onMetadata?.(data);
          } else if (data.type === "token") {
            onToken?.(data.content);
          } else if (data.type === "done") {
            onDone?.(data);
          } else if (data.type === "error") {
            const err = new Error(data.error || "Streaming error encountered.");
            err.status = data.status_code || 500;
            onError?.(err);
            throw err;
          }
        } catch (parseError) {
          if (parseError.status || (data && parseError.message === data.error)) {
            throw parseError;
          }
          console.warn("Could not parse SSE JSON:", jsonStr, parseError);
        }
      }
    }
  } catch (error) {
    if (signal?.aborted) return;
    console.error("Error during chat streaming:", error);
    let message = error.message || "An unexpected streaming error occurred.";
    if (!error.status && error.name === "TypeError") {
      message =
        "Cannot connect to the backend server. Please ensure the backend is running on http://127.0.0.1:8000.";
    }
    const err = new Error(message);
    err.status = error.status || 0;
    err.originalError = error;
    if (onError) {
      onError(err);
    }
    throw err;
  }
}

/**
 * Fetch all conversation sessions ordered by most recently active.
 * @param {number} [limit=50]
 * @returns {Promise<Array<{id: string, title: string, created_at: string, updated_at: string, message_count: number}>>}
 */
export async function fetchConversations(limit = 50) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/conversations?limit=${limit}`);
    return response.data;
  } catch (error) {
    console.error("API error fetching conversations:", error);
    return [];
  }
}

/**
 * Fetch details and messages for a specific conversation session.
 * @param {string} conversationId
 * @returns {Promise<{id: string, title: string, created_at: string, updated_at: string, messages: Array}>}
 */
export async function fetchConversation(conversationId) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/conversations/${conversationId}`);
    return response.data;
  } catch (error) {
    console.error(`API error fetching conversation ${conversationId}:`, error);
    throw error;
  }
}

/**
 * Delete a conversation session and all its messages.
 * @param {string} conversationId
 * @returns {Promise<{status: string, id: string}>}
 */
export async function deleteConversation(conversationId) {
  try {
    const response = await axios.delete(`${API_BASE_URL}/api/conversations/${conversationId}`);
    return response.data;
  } catch (error) {
    console.error(`API error deleting conversation ${conversationId}:`, error);
    throw error;
  }
}

/**
 * Upload a document (PDF, DOCX, XLSX, TXT) to the backend for ingestion and indexing.
 * @param {File} file - The file object to upload.
 * @param {function} [onProgress] - Optional upload progress callback (percent: number).
 * @returns {Promise<{message: string, filename: string, file_type: string, pages: number, chunks_created: number, chunks_stored: number, processed: boolean}>}
 */
export async function uploadDocument(file, onProgress) {
  try {
    const formData = new FormData();
    formData.append("file", file);

    const response = await axios.post(`${API_BASE_URL}/api/upload`, formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      timeout: 120000,
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          );
          onProgress(percentCompleted);
        }
      },
    });

    return response.data;
  } catch (error) {
    console.error("API error uploading document:", error);
    let message = "Failed to upload document.";
    if (typeof error.response?.data?.detail === "string") {
      message = error.response.data.detail;
    } else if (error.code === "ECONNABORTED") {
      message = "Upload timed out. The file processing took too long.";
    } else if (!error.response) {
      message =
        "Cannot connect to the backend server. Please ensure the backend is running on http://127.0.0.1:8000.";
    }
    const err = new Error(message);
    err.status = error.response?.status || 0;
    err.originalError = error;
    throw err;
  }
}

/**
 * Fetch list of indexed documents.
 * @returns {Promise<Array<{name: string, type: string, category: string, status: string, source: string, size_bytes?: number}>>}
 */
export async function fetchDocuments() {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/upload`);
    return response.data;
  } catch (error) {
    console.warn("Could not fetch documents dynamically from API, falling back:", error);
    return [];
  }
}
