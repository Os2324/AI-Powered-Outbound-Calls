"""
Local logging database (SQLite, single file: calls.db) for the outbound-call
voice assistant. Each row is one call, keyed by Vonage's conversation_uuid so
the outcome (logged by server.py when the customer responds) and the final
duration (logged when the /event webhook reports the call completed) can
both land on the same row even though they arrive at different times.
"""

import sqlite3
from datetime import datetime, timezone

DB_PATH = "calls.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            conversation_uuid TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            to_number TEXT,
            customer_text TEXT,
            classification TEXT,
            reply_text TEXT,
            duration_seconds INTEGER
        )
        """
    )
    conn.commit()
    conn.close()


def log_call_outcome(conversation_uuid, to_number, customer_text, classification, reply_text):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        INSERT INTO calls (conversation_uuid, timestamp, to_number, customer_text, classification, reply_text)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(conversation_uuid) DO UPDATE SET
            to_number=excluded.to_number,
            customer_text=excluded.customer_text,
            classification=excluded.classification,
            reply_text=excluded.reply_text
        """,
        (
            conversation_uuid,
            datetime.now(timezone.utc).isoformat(),
            to_number,
            customer_text,
            classification,
            reply_text,
        ),
    )
    conn.commit()
    conn.close()


def log_call_duration(conversation_uuid, duration_seconds):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "UPDATE calls SET duration_seconds = ? WHERE conversation_uuid = ?",
        (duration_seconds, conversation_uuid),
    )
    conn.commit()
    conn.close()


def get_all_calls():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM calls ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
