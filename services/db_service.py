"""SQLite persistence layer. All database access is centralised here."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

from config import (
    APP_DB,
    MAX_REPORT_CONTENT_LEN,
    MAX_REPORT_URL_LEN,
    MAX_SCAM_ID_LEN,
    MAX_SESSION_ID_LEN,
    MAX_USER_ID_LEN,
    MAX_USER_INPUT_DB,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id  TEXT PRIMARY KEY,
    scam_id     TEXT NOT NULL,
    started_at  TEXT,
    ended_at    TEXT,
    outcome     TEXT,
    final_score INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    risk_level  TEXT,
    risk_score  INTEGER,
    ts          TEXT
);

CREATE TABLE IF NOT EXISTS user_progress (
    user_id     TEXT PRIMARY KEY,
    total_score INTEGER DEFAULT 0,
    streak      INTEGER DEFAULT 0,
    badges      TEXT DEFAULT '[]',
    completed   TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS reports (
    report_id  TEXT PRIMARY KEY,
    session_id TEXT,
    content    TEXT,
    url        TEXT,
    risk_level TEXT,
    ts         TEXT
);

CREATE TABLE IF NOT EXISTS completion_claims (
    user_id    TEXT NOT NULL,
    session_id TEXT NOT NULL,
    scam_id    TEXT NOT NULL,
    ts         TEXT,
    PRIMARY KEY (user_id, session_id, scam_id)
);
"""


def init_db() -> None:
    with sqlite3.connect(APP_DB) as conn:
        conn.executescript(_SCHEMA)


def ensure_session(session_id: str, scam_id: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(APP_DB) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO sessions (session_id, scam_id, started_at) VALUES (?, ?, ?)",
            (session_id, scam_id, ts),
        )


def save_message(
    session_id: str,
    role: str,
    content: str,
    risk_level: str | None = None,
    risk_score: int | None = None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    safe_content = content[:MAX_USER_INPUT_DB]
    with sqlite3.connect(APP_DB) as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, risk_level, risk_score, ts)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, role, safe_content, risk_level, risk_score, ts),
        )


def save_report(
    session_id: str | None,
    content: str,
    url: str,
    risk_level: str | None = None,
) -> str:
    report_id = str(uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    safe_content = content[:MAX_REPORT_CONTENT_LEN]
    safe_url = url[:MAX_REPORT_URL_LEN]
    with sqlite3.connect(APP_DB) as conn:
        conn.execute(
            "INSERT INTO reports (report_id, session_id, content, url, risk_level, ts)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (report_id, session_id, safe_content, safe_url, risk_level, ts),
        )
    return report_id


def get_user_progress(user_id: str) -> dict | None:
    safe_user_id = user_id[:MAX_USER_ID_LEN]
    with sqlite3.connect(APP_DB) as conn:
        row = conn.execute(
            "SELECT total_score, streak, badges, completed FROM user_progress WHERE user_id=?",
            (safe_user_id,),
        ).fetchone()
    if row is None:
        return None

    return {
        "user_id": safe_user_id,
        "total_score": row[0],
        "streak": row[1],
        "badges": json.loads(row[2]),
        "completed": json.loads(row[3]),
    }


def save_user_progress(
    user_id: str,
    total_score: int,
    streak: int,
    badges: list[str],
    completed: dict[str, int],
) -> None:
    safe_user_id = user_id[:MAX_USER_ID_LEN]
    with sqlite3.connect(APP_DB) as conn:
        conn.execute(
            "INSERT INTO user_progress (user_id, total_score, streak, badges, completed)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(user_id) DO UPDATE SET"
            " total_score=excluded.total_score,"
            " streak=excluded.streak,"
            " badges=excluded.badges,"
            " completed=excluded.completed",
            (
                safe_user_id,
                total_score,
                streak,
                json.dumps(badges, ensure_ascii=False),
                json.dumps(completed, ensure_ascii=False),
            ),
        )


def get_session_messages(session_id: str) -> list[dict]:
    safe_session_id = session_id[:MAX_SESSION_ID_LEN]
    with sqlite3.connect(APP_DB) as conn:
        rows = conn.execute(
            "SELECT role, content, risk_level, risk_score, ts FROM messages"
            " WHERE session_id=? ORDER BY id ASC",
            (safe_session_id,),
        ).fetchall()

    return [
        {
            "role": row[0],
            "content": row[1],
            "risk_level": row[2],
            "risk_score": row[3],
            "ts": row[4],
        }
        for row in rows
    ]


def claim_completion(user_id: str, session_id: str, scam_id: str) -> bool:
    safe_user_id = user_id[:MAX_USER_ID_LEN]
    safe_session_id = session_id[:MAX_SESSION_ID_LEN]
    safe_scam_id = scam_id[:MAX_SCAM_ID_LEN]
    ts = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(APP_DB) as conn:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO completion_claims (user_id, session_id, scam_id, ts)"
            " VALUES (?, ?, ?, ?)",
            (safe_user_id, safe_session_id, safe_scam_id, ts),
        )
    return cursor.rowcount == 1
