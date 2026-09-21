"""SQLite database connection and schema management."""

import logging
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from typing import Generator

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


@contextmanager
def get_db_connection(
    db_path: Path | str | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    """Yield a configured SQLite connection with foreign keys and WAL mode enabled."""
    target_path = Path(db_path or settings.DATABASE_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(
        str(target_path),
        timeout=10.0,
        detect_types=sqlite3.PARSE_DECLTYPES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path | str | None = None) -> None:
    """Initialize SQLite database tables and indexes."""
    target_path = Path(db_path or settings.DATABASE_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with get_db_connection(target_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
            ON messages(conversation_id);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
            ON conversations(updated_at DESC);
            """
        )

    logger.info("Initialized SQLite database at %s", target_path)
