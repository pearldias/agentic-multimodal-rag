"""Service for managing persistent conversations and messages in SQLite."""

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
import uuid

from backend.app.core.config import settings
from backend.app.db.database import get_db_connection
from backend.app.models.conversation import (
    ConversationDetail,
    ConversationSummary,
    MessageResponse,
)

logger = logging.getLogger(__name__)


class ConversationService:
    """Handles CRUD operations for conversation sessions and messages."""

    def __init__(self, db_path: Path | str | None = None) -> None:
        self.db_path = db_path

    def _get_connection(self):
        return get_db_connection(self.db_path)

    @staticmethod
    def generate_title_from_question(question: str) -> str:
        """Derive a clean, concise conversation title from the initial user prompt."""
        cleaned = question.strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if len(cleaned) <= 45:
            return cleaned.rstrip(".?! ")

        # Truncate to first 45 chars at word boundary
        truncated = cleaned[:45]
        last_space = truncated.rfind(" ")
        if last_space > 20:
            truncated = truncated[:last_space]

        return truncated.rstrip(".?! ")

    def create_conversation(
        self,
        title: str,
        conversation_id: str | None = None,
    ) -> ConversationSummary:
        """Create a new conversation session."""
        conv_id = conversation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        clean_title = title.strip() or "New Conversation"

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?);
                """,
                (conv_id, clean_title, now, now),
            )

        logger.info("Created conversation %s: '%s'", conv_id, clean_title)
        return ConversationSummary(
            id=conv_id,
            title=clean_title,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        """Retrieve conversation by ID along with its full message history."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = ?;
                """,
                (conversation_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            msg_cursor = conn.execute(
                """
                SELECT id, role, content, sources_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC;
                """,
                (conversation_id,),
            )
            messages = []
            for msg_row in msg_cursor.fetchall():
                sources = []
                if msg_row["sources_json"]:
                    try:
                        sources = json.loads(msg_row["sources_json"])
                    except Exception:
                        sources = []

                messages.append(
                    MessageResponse(
                        id=msg_row["id"],
                        role=msg_row["role"],
                        content=msg_row["content"],
                        sources=sources,
                        created_at=msg_row["created_at"],
                    )
                )

        return ConversationDetail(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=messages,
        )

    def list_conversations(self, limit: int = 50) -> list[ConversationSummary]:
        """List past conversations ordered by most recently updated."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT 
                    c.id, 
                    c.title, 
                    c.created_at, 
                    c.updated_at, 
                    COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()

        return [
            ConversationSummary(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                message_count=row["message_count"],
            )
            for row in rows
        ]

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation and all its associated messages."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM conversations WHERE id = ?;",
                (conversation_id,),
            )
            if not cursor.fetchone():
                return False

            conn.execute(
                "DELETE FROM messages WHERE conversation_id = ?;",
                (conversation_id,),
            )
            conn.execute(
                "DELETE FROM conversations WHERE id = ?;",
                (conversation_id,),
            )

        logger.info("Deleted conversation %s and associated messages.", conversation_id)
        return True

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        sources: list[dict] | None = None,
        message_id: str | None = None,
    ) -> MessageResponse:
        """Persist a message and touch conversation updated_at."""
        msg_id = message_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        sources_json = json.dumps(sources) if sources else None

        with self._get_connection() as conn:
            # Ensure conversation exists
            check = conn.execute(
                "SELECT id FROM conversations WHERE id = ?;",
                (conversation_id,),
            ).fetchone()
            if not check:
                # Auto-create if not present
                title = self.generate_title_from_question(content)
                conn.execute(
                    """
                    INSERT INTO conversations (id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?);
                    """,
                    (conversation_id, title, now, now),
                )

            conn.execute(
                """
                INSERT INTO messages (id, conversation_id, role, content, sources_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                (msg_id, conversation_id, role, content, sources_json, now),
            )

            conn.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?;",
                (now, conversation_id),
            )

        return MessageResponse(
            id=msg_id,
            role=role,
            content=content,
            sources=sources or [],
            created_at=now,
        )

    def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = settings.MEMORY_WINDOW_MESSAGES,
    ) -> list[MessageResponse]:
        """Fetch the last `limit` messages in chronological order."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, role, content, sources_json, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (conversation_id, limit),
            )
            rows = cursor.fetchall()

        # Reverse so they are chronological (oldest to newest)
        chronological_rows = list(reversed(rows))
        messages = []
        for row in chronological_rows:
            sources = []
            if row["sources_json"]:
                try:
                    sources = json.loads(row["sources_json"])
                except Exception:
                    sources = []

            messages.append(
                MessageResponse(
                    id=row["id"],
                    role=row["role"],
                    content=row["content"],
                    sources=sources,
                    created_at=row["created_at"],
                )
            )

        return messages
