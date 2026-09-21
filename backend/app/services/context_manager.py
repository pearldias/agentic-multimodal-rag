"""Context management and short-term conversational memory service."""

import logging
import re
from typing import Sequence

from backend.app.core.config import settings
from backend.app.models.conversation import MessageResponse
from backend.app.services.conversation_service import ConversationService
from backend.app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Patterns that strongly indicate a question relies on conversational context
DEPENDENCY_PATTERNS = [
    r"\b(it|they|them|their|that|this|these|those|such|same)\b",
    r"^(what\s+about|how\s+about|and\s+what|and\s+for|what\s+if|and|so)\b",
    r"\b(previous|previously|earlier|mentioned|above|former|latter|instead)\b",
    r"^(why|how\s+many|how\s+much|does\s+it|can\s+they|is\s+it|can\s+i|can\s+we)\b",
    r"\b(in\s+that\s+case|for\s+that|about\s+that)\b",
]


class ContextManager:
    """Manages bounded short-term conversation context and query contextualization."""

    def __init__(
        self,
        conversation_service: ConversationService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.conversation_service = conversation_service or ConversationService()
        self.llm_service = llm_service or LLMService()

    def get_context_window(
        self,
        conversation_id: str,
        limit: int = settings.MEMORY_WINDOW_MESSAGES,
    ) -> list[MessageResponse]:
        """Retrieve bounded sliding window of the last `limit` messages."""
        if not conversation_id:
            return []
        return self.conversation_service.get_recent_messages(
            conversation_id=conversation_id,
            limit=limit,
        )

    @staticmethod
    def should_contextualize(
        question: str,
        history: Sequence[MessageResponse],
    ) -> bool:
        """Determine whether the user question requires context resolution."""
        if not history:
            return False

        trimmed = question.strip().lower()
        words = trimmed.split()

        # Short questions (e.g. "What about probation?") almost certainly depend on context
        if len(words) <= 6:
            return True

        # Check regex dependency patterns
        for pattern in DEPENDENCY_PATTERNS:
            if re.search(pattern, trimmed):
                return True

        return False

    def contextualize_query(
        self,
        question: str,
        history: Sequence[MessageResponse],
    ) -> str:
        """Contextualize ambiguous follow-up questions before Chroma retrieval."""
        clean_question = question.strip()

        if not self.should_contextualize(clean_question, history):
            return clean_question

        history_dicts = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]

        try:
            standalone_query = self.llm_service.contextualize_query(
                question=clean_question,
                chat_history=history_dicts,
            )
            logger.info(
                "Contextualized query: '%s' -> '%s'",
                clean_question,
                standalone_query,
            )
            return standalone_query
        except Exception as error:
            logger.warning(
                "Contextualization failed (%s); falling back to raw question.",
                error,
            )
            return clean_question

    @staticmethod
    def format_history_for_llm(
        history: Sequence[MessageResponse],
    ) -> list[dict]:
        """Convert MessageResponse objects into dictionary format for LLMService."""
        return [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
