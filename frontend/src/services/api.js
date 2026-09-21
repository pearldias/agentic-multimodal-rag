import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

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
