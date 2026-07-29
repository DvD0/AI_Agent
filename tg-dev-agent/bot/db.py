"""
db.py — вся работа с SQLite (модули знаний, подтверждённая память, настройки).
Все функции блокирующие; вызываются через asyncio.to_thread из хендлеров,
чтобы не блокировать event loop aiogram.
"""

import sqlite3
import os
from datetime import datetime, timezone
from typing import Optional

DB_PATH = os.environ.get("DB_PATH", "/app/data/agent.db")


def _conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            topic TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',  -- pending | confirmed | skipped
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,       -- user | assistant
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def add_module(category: str, topic: str, content: str) -> int:
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO modules (category, topic, content, status, created_at) "
        "VALUES (?, ?, ?, 'pending', ?)",
        (category, topic, content, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    module_id = cur.lastrowid
    conn.close()
    return module_id


def get_pending_modules() -> list[sqlite3.Row]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM modules WHERE status = 'pending' ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return rows


def get_module(module_id: int) -> Optional[sqlite3.Row]:
    conn = _conn()
    row = conn.execute("SELECT * FROM modules WHERE id = ?", (module_id,)).fetchone()
    conn.close()
    return row


def set_module_status(module_id: int, status: str):
    conn = _conn()
    conn.execute("UPDATE modules SET status = ? WHERE id = ?", (status, module_id))
    conn.commit()
    conn.close()


def get_confirmed_modules(limit: int = 30) -> list[sqlite3.Row]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM modules WHERE status = 'confirmed' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return rows


def get_setting(key: str) -> Optional[str]:
    conn = _conn()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row["value"] if row else None


def set_setting(key: str, value: str):
    conn = _conn()
    conn.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value)
    )
    conn.commit()
    conn.close()


def add_chat_message(role: str, content: str):
    conn = _conn()
    conn.execute(
        "INSERT INTO chat_history (role, content, created_at) VALUES (?, ?, ?)",
        (role, content, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()


def get_recent_chat(limit: int = 12) -> list[sqlite3.Row]:
    conn = _conn()
    rows = conn.execute(
        "SELECT * FROM chat_history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return list(reversed(rows))
