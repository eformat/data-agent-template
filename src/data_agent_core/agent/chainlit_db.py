"""Chainlit SQLite chat history — schema creation and migration."""

from __future__ import annotations

import os
import sqlite3

EXPECTED_COLUMNS = {
    "steps": [
        "id", "name", "type", "threadId", "parentId", "streaming",
        "waitForAnswer", "isError", "metadata", "tags", "input", "output",
        "createdAt", "start", "end", "generation", "showInput", "language",
        "defaultOpen", "autoCollapse",
    ],
    "threads": [
        "id", "name", "createdAt", "userId", "userIdentifier", "tags", "metadata",
    ],
    "users": ["id", "identifier", "metadata", "createdAt"],
    "elements": [
        "id", "threadId", "type", "name", "url", "chainlitKey", "display",
        "language", "size", "forId", "objectKey", "mime", "page", "props",
    ],
    "feedbacks": ["id", "forId", "threadId", "value", "comment", "strategy"],
}


def init_db(db_path: str | None = None) -> str:
    """Create or migrate the Chainlit SQLite database.

    Returns the connection string for SQLAlchemyDataLayer.
    """
    db_path = db_path or os.environ.get("CHAINLIT_DB_PATH", "/app/data/chainlit.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)

    for table, expected_cols in EXPECTED_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info('{table}')").fetchall()}
        if existing:
            missing = [c for c in expected_cols if c not in existing]
            for col in missing:
                default = "0" if col in ("streaming", "isError", "defaultOpen", "autoCollapse", "waitForAnswer") else "''"
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{col}" DEFAULT {default}')
            if missing:
                conn.commit()
                print(f"[db] Added columns to {table}: {missing}", flush=True)

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            identifier TEXT NOT NULL UNIQUE,
            metadata TEXT DEFAULT '{}',
            "createdAt" TEXT
        );
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            name TEXT,
            "createdAt" TEXT,
            "userId" TEXT,
            "userIdentifier" TEXT,
            tags TEXT DEFAULT '[]',
            metadata TEXT DEFAULT '{}',
            FOREIGN KEY ("userId") REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS steps (
            id TEXT PRIMARY KEY,
            name TEXT,
            type TEXT,
            "threadId" TEXT,
            "parentId" TEXT,
            streaming INTEGER DEFAULT 0,
            "waitForAnswer" INTEGER,
            "isError" INTEGER DEFAULT 0,
            metadata TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            input TEXT,
            output TEXT,
            "createdAt" TEXT,
            "start" TEXT,
            "end" TEXT,
            generation TEXT,
            "showInput" TEXT,
            language TEXT,
            "defaultOpen" INTEGER DEFAULT 0,
            "autoCollapse" INTEGER DEFAULT 0,
            FOREIGN KEY ("threadId") REFERENCES threads(id)
        );
        CREATE TABLE IF NOT EXISTS elements (
            id TEXT PRIMARY KEY,
            "threadId" TEXT,
            type TEXT,
            name TEXT,
            url TEXT,
            "chainlitKey" TEXT,
            display TEXT,
            language TEXT,
            size TEXT,
            "forId" TEXT,
            "objectKey" TEXT,
            mime TEXT,
            page INTEGER,
            props TEXT,
            FOREIGN KEY ("threadId") REFERENCES threads(id)
        );
        CREATE TABLE IF NOT EXISTS feedbacks (
            id TEXT PRIMARY KEY,
            "forId" TEXT,
            "threadId" TEXT,
            value INTEGER,
            comment TEXT,
            strategy TEXT,
            FOREIGN KEY ("threadId") REFERENCES threads(id)
        );
    """)
    conn.close()

    return f"sqlite+aiosqlite:///{db_path}"
