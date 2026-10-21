import sqlite3
import json
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent / "data" / "jarvis_memory.db"

class MemoryManager:
    def __init__(self, db_path: Path = DB_FILE):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. 对话短期/长期记忆表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 2. 用户个性化档案与事实记忆（长期记忆）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS long_term_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # 3. 日历日程表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    description TEXT,
                    is_completed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # --- 对话历史管理 ---
    def add_message(self, role: str, content: str):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO conversation_history (role, content) VALUES (?, ?)",
                (role, content)
            )

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, str]]:
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT role, content FROM conversation_history ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]

    def clear_history(self):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM conversation_history")

    # --- 长期偏好与事实存储 ---
    def set_memory(self, category: str, key: str, value: str):
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO long_term_memories (category, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """, (category, key, value))

    def get_memories(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if category:
                rows = conn.execute(
                    "SELECT category, key, value FROM long_term_memories WHERE category = ?",
                    (category,)
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value FROM long_term_memories"
                ).fetchall()
            return [dict(row) for row in rows]

    # --- 日程事件 ---
    def add_event(self, title: str, start_time: str, end_time: str = "", description: str = "") -> int:
        with self._get_connection() as conn:
            cursor = conn.execute(
                "INSERT INTO calendar_events (title, start_time, end_time, description) VALUES (?, ?, ?, ?)",
                (title, start_time, end_time, description)
            )
            return cursor.lastrowid

    def list_events(self, include_completed: bool = False) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            sql = "SELECT id, title, start_time, end_time, description, is_completed FROM calendar_events"
            if not include_completed:
                sql += " WHERE is_completed = 0"
            sql += " ORDER BY start_time ASC"
            rows = conn.execute(sql).fetchall()
            return [dict(row) for row in rows]

    def complete_event(self, event_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE calendar_events SET is_completed = 1 WHERE id = ?", (event_id,))
