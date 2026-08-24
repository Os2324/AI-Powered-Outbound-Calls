"""
Local logging database (SQLite, single file: logs.db).
Every question asked in app.py gets one row here. This is the shared
foundation for:
  - Phase 5 (audit trail): the log itself is the record of who asked what, when.
  - Phase 6 (feedback): thumbs up/down updates the `feedback` column.
  - Phase 7 (metrics dashboard): a separate page reads and summarizes this table.
"""

import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs.db")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            agent_name TEXT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            sources TEXT,
            latency_seconds REAL,
            feedback TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def log_interaction(agent_name, question, answer, sources, latency_seconds):
    """Saves one Q&A interaction and returns its row id (needed later to attach feedback)."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute(
        """
        INSERT INTO interactions (timestamp, agent_name, question, answer, sources, latency_seconds, feedback)
        VALUES (?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            agent_name,
            question,
            answer,
            ", ".join(sources),
            latency_seconds,
        ),
    )
    conn.commit()
    row_id = cursor.lastrowid
    conn.close()
    return row_id


def set_feedback(row_id, feedback):
    """feedback should be 'up' or 'down'."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE interactions SET feedback = ? WHERE id = ?", (feedback, row_id))
    conn.commit()
    conn.close()


def get_all_interactions():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM interactions ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
