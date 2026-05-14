import sqlite3
import os
import json
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def init_db():
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                filename TEXT NOT NULL,
                result_json TEXT NOT NULL,
                total_words INTEGER,
                unique_words INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_history_session
                ON analysis_history(session_id);
        """)

        # Migrate older DBs that pre-date the summary columns. SQLite's ADD COLUMN
        # is cheap; the backfill parses JSON once per legacy row so list queries
        # never have to touch the blob again.
        cols = {row["name"] for row in db.execute("PRAGMA table_info(analysis_history)")}
        if "total_words" not in cols:
            db.execute("ALTER TABLE analysis_history ADD COLUMN total_words INTEGER")
        if "unique_words" not in cols:
            db.execute("ALTER TABLE analysis_history ADD COLUMN unique_words INTEGER")

        legacy = db.execute(
            "SELECT id, result_json FROM analysis_history "
            "WHERE total_words IS NULL OR unique_words IS NULL"
        ).fetchall()
        for row in legacy:
            try:
                data = json.loads(row["result_json"])
                tw = int(data.get("total_words") or 0)
                uw = int(data.get("unique_words") or 0)
            except Exception:
                tw, uw = 0, 0
            db.execute(
                "UPDATE analysis_history SET total_words = ?, unique_words = ? WHERE id = ?",
                (tw, uw, row["id"]),
            )

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
