"""SQLite database connection and initial schema initialization."""

import os
import sqlite3
from contextlib import contextmanager
from typing import Generator, Optional

DEFAULT_DB_PATH = "data/workflows.db"


def get_db_path(db_path: Optional[str] = None) -> str:
    """Return the configured SQLite database file path, ensuring parent dirs exist."""
    if db_path:
        target = db_path
    else:
        target = (
            os.getenv("WORKFLOW_DATABASE_PATH")
            or os.getenv("DATABASE_PATH")
            or os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}").replace("sqlite:///", "")
        )

    directory = os.path.dirname(target)
    if directory:
        os.makedirs(directory, exist_ok=True)

    return target


@contextmanager
def get_db_connection(db_path: Optional[str] = None) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional scope around a series of SQLite operations."""
    path = get_db_path(db_path)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize SQLite database tables for workflows and audit events."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                request TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
