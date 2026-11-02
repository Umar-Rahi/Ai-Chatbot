"""
Database module — SQLite-backed persistence for conversations and messages.
All queries use parameterised statements to prevent SQL injection.
"""

import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Generator

from backend.config import Config


# ── Connection helper ─────────────────────────────────────────────────────────

@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Yield a database connection, auto-closing on exit."""
    conn = sqlite3.connect(Config.DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL DEFAULT 'New Chat',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id              TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC);
"""


def init_db() -> None:
    """Create tables if they don't exist."""
    with get_db() as conn:
        conn.executescript(SCHEMA)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


# ── Conversations ─────────────────────────────────────────────────────────────

def create_conversation(title: str = "New Chat") -> dict:
    cid = _new_id()
    now = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (cid, title, now, now),
        )
    return {"id": cid, "title": title, "created_at": now, "updated_at": now}


def get_conversation(cid: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (cid,)
        ).fetchone()
    return dict(row) if row else None


def list_conversations() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def rename_conversation(cid: str, new_title: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
            (new_title.strip()[:200], _now(), cid),
        )
    return cur.rowcount > 0


def delete_conversation(cid: str) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (cid,))
    return cur.rowcount > 0


def clear_all_conversations() -> int:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM conversations")
    return cur.rowcount


def touch_conversation(cid: str) -> None:
    with get_db() as conn:
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?", (_now(), cid)
        )


# ── Messages ──────────────────────────────────────────────────────────────────

def add_message(conversation_id: str, role: str, content: str) -> dict:
    mid = _new_id()
    now = _now()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (mid, conversation_id, role, content, now),
        )
    touch_conversation(conversation_id)
    return {"id": mid, "conversation_id": conversation_id, "role": role, "content": content, "created_at": now}


def get_messages(conversation_id: str, limit: int | None = None) -> list[dict]:
    with get_db() as conn:
        if limit:
            rows = conn.execute(
                """SELECT * FROM messages WHERE conversation_id = ?
                   ORDER BY created_at DESC LIMIT ?""",
                (conversation_id, limit),
            ).fetchall()
            return [dict(r) for r in reversed(rows)]
        rows = conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at",
            (conversation_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_messages(conversation_id: str) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
