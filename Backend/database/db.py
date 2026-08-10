"""
db.py - Candidate database
Stores candidate name, per-source usernames, and the 9 dimension
scores using SQLite (no more single "rescoring_score" column).
"""

import sqlite3
import os
import uuid

DB_PATH = os.path.join(os.path.dirname(__file__), "candidates.db")

# The 9 scoring dimensions (see Backend/AI/api_AI.py for definitions)
DIMENSION_COLUMNS = [
    "technical_competency",
    "problem_solving",
    "communication",
    "career_stability",
    "company_exposure",
    "academic_signal",
    "initiative",
    "risk_indicators",
    "role_domain_relevance",
]

# Sources where the candidate supplies an exact username
# (Google Scholar / ResearchGate are searched by full name, so no column)
USERNAME_COLUMNS = [
    "github_username",
    "linkedin_username",
    "kaggle_username",
    "devto_username",
    "medium_username",
    "hashnode_username",
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the candidates table if it doesn't exist."""
    dim_cols_sql = ",\n                ".join(
        f"{col} REAL NOT NULL DEFAULT 0.0" for col in DIMENSION_COLUMNS
    )
    username_cols_sql = ",\n                ".join(
        f"{col} TEXT" for col in USERNAME_COLUMNS
    )
    with get_connection() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS candidates (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                name           TEXT    NOT NULL,
                original_role  TEXT,
                fit_direction  TEXT,
                whats_changed_summary TEXT,
                re_engage_flag BOOLEAN,
                status         TEXT,
                {username_cols_sql},
                {dim_cols_sql},
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def insert_candidate(name: str, dimensions: dict, usernames: dict | None = None,
                     original_role: str = "",
                     fit_direction: str = "", whats_changed_summary: str = "",
                     re_engage_flag: bool = False, status: str = "") -> int:
    """
    Insert a candidate and return their auto-incremented id.
    """
    usernames = usernames or {}

    columns = ["name", "original_role", "fit_direction", "whats_changed_summary", "re_engage_flag", "status"] + USERNAME_COLUMNS + DIMENSION_COLUMNS
    values = (
        [name, original_role, fit_direction, whats_changed_summary, re_engage_flag, status]
        + [usernames.get(col) for col in USERNAME_COLUMNS]
        + [dimensions.get(col, 0) for col in DIMENSION_COLUMNS]
    )
    placeholders = ", ".join(["?"] * len(columns))
    col_list = ", ".join(columns)

    with get_connection() as conn:
        cursor = conn.execute(
            f"INSERT INTO candidates ({col_list}) VALUES ({placeholders})",
            values,
        )
        conn.commit()
        return cursor.lastrowid

def update_candidate(candidate_id: int, dimensions: dict, usernames: dict | None = None,
                     fit_direction: str = "", whats_changed_summary: str = "",
                     re_engage_flag: bool = False, status: str = "") -> bool:
    """
    Update an existing candidate's evaluation data.
    """
    usernames = usernames or {}
    
    set_fields = ["fit_direction = ?", "whats_changed_summary = ?", "re_engage_flag = ?", "status = ?"]
    values = [fit_direction, whats_changed_summary, re_engage_flag, status]
    
    for col in USERNAME_COLUMNS:
        if col in usernames:
            set_fields.append(f"{col} = ?")
            values.append(usernames[col])
            
    for col in DIMENSION_COLUMNS:
        if col in dimensions:
            set_fields.append(f"{col} = ?")
            values.append(dimensions[col])
            
    set_clause = ", ".join(set_fields)
    values.append(candidate_id)
    
    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE candidates SET {set_clause}, created_at = CURRENT_TIMESTAMP WHERE id = ?",
            values,
        )
        conn.commit()
        return cursor.rowcount > 0


def get_all_candidates() -> list:
    """Return all candidates, best role_domain_relevance first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY role_domain_relevance DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_candidate_by_id(candidate_id: int) -> dict | None:
    """Return a single candidate by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        return dict(row) if row else None


def update_dimension_scores(candidate_id: int, dimensions: dict) -> bool:
    """Update one or more of the 9 dimension scores for a candidate."""
    updates = {k: v for k, v in dimensions.items() if k in DIMENSION_COLUMNS}
    if not updates:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [candidate_id]

    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE candidates SET {set_clause} WHERE id = ?", values
        )
        conn.commit()
        return cursor.rowcount > 0


def update_usernames(candidate_id: int, usernames: dict) -> bool:
    """Update one or more of the source usernames for a candidate."""
    updates = {k: v for k, v in usernames.items() if k in USERNAME_COLUMNS}
    if not updates:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [candidate_id]

    with get_connection() as conn:
        cursor = conn.execute(
            f"UPDATE candidates SET {set_clause} WHERE id = ?", values
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