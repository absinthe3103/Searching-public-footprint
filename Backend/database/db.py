"""
db.py - Candidate database
Stores candidate name, per-source usernames, and the 9 dimension
scores using SQLite (no more single "rescoring_score" column).
"""

import sqlite3
import os
import json

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

# The 7 organizational culture dimensions HR can select as "relevant" in
# the Preferences page (see Backend/src/Logic.py preferences endpoints)
CULTURE_DIMENSIONS = [
    "innovation_risk_taking",
    "attention_to_detail",
    "outcome_orientation",
    "people_orientation",
    "team_orientation",
    "aggressiveness",
    "stability",
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
                original_tier  TEXT,
                university     TEXT,
                summary_profile TEXT,
                culture_fit_dimensions TEXT,
                fit_direction  TEXT,
                whats_changed_summary TEXT,
                re_engage_flag BOOLEAN,
                status         TEXT,
                executive_summary TEXT,
                {username_cols_sql},
                {dim_cols_sql},
                created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def init_interviews_table():
    """Create the interviews table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS interviews (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                title             TEXT NOT NULL,
                description       TEXT,
                candidate_name    TEXT NOT NULL,
                google_meet_link  TEXT,
                scheduled_time    TEXT,
                date              TEXT,
                status            TEXT DEFAULT 'SCHEDULED',
                transcript_text   TEXT,
                generated_cv_url  TEXT,
                created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def init_preferences_tables():
    """Create the culture_preferences (singleton) and preferred_universities
    tables if they don't exist."""
    dim_cols_sql = ",\n                ".join(
        f"{col} INTEGER NOT NULL DEFAULT 0" for col in CULTURE_DIMENSIONS
    )
    with get_connection() as conn:
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS culture_preferences (
                id             INTEGER PRIMARY KEY CHECK (id = 1),
                {dim_cols_sql},
                updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("INSERT OR IGNORE INTO culture_preferences (id) VALUES (1)")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS preferred_universities (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def insert_candidate(name: str, dimensions: dict, usernames: dict | None = None,
                     original_role: str = "", original_tier: str = "",
                     fit_direction: str = "", whats_changed_summary: str = "",
                     re_engage_flag: bool = False, status: str = "",
                     executive_summary: str = "",
                     university: str = "", summary_profile: str = "",
                     culture_fit_dimensions: list | None = None) -> int:
    """
    Insert a candidate and return the new row id.

    culture_fit_dimensions: optional list of CULTURE_DIMENSIONS keys the AI
    determined match the candidate's summary_profile, e.g.
    ["team_orientation", "stability"]. Stored as JSON text. Only populated
    when the candidate has a summary_profile; empty list otherwise.
    """
    usernames = usernames or {}
    culture_fit_dimensions = culture_fit_dimensions or []

    columns = (
        ["name", "original_role", "original_tier", "university", "summary_profile",
         "culture_fit_dimensions",
         "fit_direction", "whats_changed_summary", "re_engage_flag", "status", "executive_summary"]
        + USERNAME_COLUMNS + DIMENSION_COLUMNS
    )
    values = (
        [name, original_role, original_tier, university, summary_profile,
         json.dumps(culture_fit_dimensions),
         fit_direction, whats_changed_summary, re_engage_flag, status, executive_summary]
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


def _parse_candidate_row(row: sqlite3.Row) -> dict:
    """Convert a raw candidates row into a dict, decoding culture_fit_dimensions
    from its stored JSON string back into a Python list."""
    d = dict(row)
    raw = d.get("culture_fit_dimensions")
    try:
        d["culture_fit_dimensions"] = json.loads(raw) if raw else []
    except (TypeError, json.JSONDecodeError):
        d["culture_fit_dimensions"] = []
    return d


def get_all_candidates() -> list:
    """Return all candidates, best role_domain_relevance first."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY role_domain_relevance DESC"
        ).fetchall()
        return [_parse_candidate_row(row) for row in rows]


def get_candidate_by_id(candidate_id: int) -> dict | None:
    """Return a single candidate by id."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        return _parse_candidate_row(row) if row else None


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


def get_culture_preferences() -> dict:
    """Return the current HR culture-fit selection as {dimension: True/False}."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM culture_preferences WHERE id = 1").fetchone()
        return {col: bool(row[col]) for col in CULTURE_DIMENSIONS} if row else {}


def set_culture_preferences(selected: list) -> bool:
    """Overwrite the HR culture selection.
    selected: list of dimension keys that are ON (e.g. ["team_orientation", "stability"]).
    Any CULTURE_DIMENSIONS key not in the list is turned OFF."""
    values = [1 if col in selected else 0 for col in CULTURE_DIMENSIONS]
    set_clause = ", ".join(f"{col} = ?" for col in CULTURE_DIMENSIONS)
    with get_connection() as conn:
        conn.execute(
            f"UPDATE culture_preferences SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
            values,
        )
        conn.commit()
        return True


def get_preferred_universities() -> list:
    """Return all preferred universities, alphabetically."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM preferred_universities ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]


def add_preferred_university(name: str) -> int | None:
    """Add a preferred university. Returns the new row id, or None if it
    already exists (name is UNIQUE)."""
    with get_connection() as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO preferred_universities (name) VALUES (?)", (name.strip(),)
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def delete_preferred_university(university_id: int) -> bool:
    """Remove a preferred university by id."""
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM preferred_universities WHERE id = ?", (university_id,)
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


def get_interviews() -> list:
    """Return all interviews, ordered by date descending."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM interviews ORDER BY date DESC, scheduled_time DESC").fetchall()
        return [dict(row) for row in rows]


def get_interview_by_id(interview_id: int) -> dict | None:
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
        return dict(row) if row else None


def create_interview(title: str, candidate_name: str, google_meet_link: str, 
                     date: str, scheduled_time: str, description: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO interviews (title, description, candidate_name, google_meet_link, date, scheduled_time) 
               VALUES (?, ?, ?, ?, ?, ?)""",
            (title, description, candidate_name, google_meet_link, date, scheduled_time)
        )
        conn.commit()
        return cursor.lastrowid


def update_interview_status(interview_id: int, status: str, transcript_text: str = None) -> bool:
    with get_connection() as conn:
        if transcript_text is not None:
            cursor = conn.execute(
                "UPDATE interviews SET status = ?, transcript_text = ? WHERE id = ?",
                (status, transcript_text, interview_id)
            )
        else:
            cursor = conn.execute(
                "UPDATE interviews SET status = ? WHERE id = ?",
                (status, interview_id)
            )
        conn.commit()
        return cursor.rowcount > 0


# Auto-init on import
init_db()
init_preferences_tables()
init_interviews_table()