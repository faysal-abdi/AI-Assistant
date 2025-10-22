"""SQLite-backed conversation memory store."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from robot_assistant.config.defaults import MemoryConfig


@dataclass
class MemoryTurn:
    """Structured representation of a stored conversation turn."""

    role: str
    content: str
    metadata: Dict[str, str]
    created_at: float


class ConversationMemory:
    """Provides short-term buffers backed by persistent SQLite storage."""

    def __init__(self, config: MemoryConfig) -> None:
        self.config = config
        self.db_path = Path(config.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_turns (
                session_id TEXT NOT NULL,
                turn_index INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at REAL NOT NULL,
                PRIMARY KEY (session_id, turn_index)
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (session_id, key)
            )
            """
        )
        self._conn.commit()

    def append_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """Persist a conversation turn."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT COALESCE(MAX(turn_index), -1) FROM conversation_turns WHERE session_id = ?",
            (session_id,),
        )
        next_index = cursor.fetchone()[0] + 1
        cursor.execute(
            """
            INSERT OR REPLACE INTO conversation_turns
            (session_id, turn_index, role, content, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                next_index,
                role,
                content,
                json.dumps(metadata or {}),
                time.time(),
            ),
        )
        self._conn.commit()

    def get_recent_turns(self, session_id: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
        """Return the latest turns for a session."""
        limit = limit or self.config.history_window
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT role, content, metadata, created_at
            FROM conversation_turns
            WHERE session_id = ?
            ORDER BY turn_index DESC
            LIMIT ?
            """,
            (session_id, limit),
        )
        rows = cursor.fetchall()
        turns: List[Dict[str, str]] = []
        for row in reversed(rows):
            metadata = {}
            if row["metadata"]:
                try:
                    metadata = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    metadata = {}
            turns.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "metadata": metadata,
                    "created_at": row["created_at"],
                }
            )
        return turns

    def set_preference(self, session_id: str, key: str, value: str) -> None:
        """Persist a preference for a session."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO preferences (session_id, key, value, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, key, value, time.time()),
        )
        self._conn.commit()

    def get_preferences(self, session_id: str) -> Dict[str, str]:
        """Return all stored preferences for a session."""
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT key, value FROM preferences WHERE session_id = ?",
            (session_id,),
        )
        return {row["key"]: row["value"] for row in cursor.fetchall()}

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()
