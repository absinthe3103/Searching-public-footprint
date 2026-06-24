"""
db.py - Candidate database
Stores candidate name and rescoring score using SQLite.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "candidates.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the candidates table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS candidates (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                rescoring_score REAL   NOT NULL DEFAULT 0.0,
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def insert_candidate(name: str, rescoring_score: float) -> int:
    """Insert a candidate and return the new row id."""
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO candidates (name, rescoring_score) VALUES (?, ?)",
            (name, rescoring_score)
        )
        conn.commit()
        return cursor.lastrowid


def get_all_candidates() -> list:
    """Return all candidates ordered by score descending."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY rescoring_score DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_candidate_by_id(candidate_id: int) -> dict | None:
    """Return a single candidate by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        return dict(row) if row else None


def update_score(candidate_id: int, new_score: float) -> bool:
    """Update the rescoring score for a candidate."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE candidates SET rescoring_score = ? WHERE id = ?",
            (new_score, candidate_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def delete_candidate(candidate_id: int) -> bool:
    """Delete a candidate by id."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM candidates WHERE id = ?", (candidate_id,)
        )
        conn.commit()
        return cursor.rowcount > 0


# Auto-init on import
init_db()