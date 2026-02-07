"""
User model and database helpers.
"""

import sqlite3
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

import config


def get_db():
    """Return a new SQLite connection with Row factory."""
    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables (and migrate columns) if they don't already exist."""
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            pinned_subs TEXT DEFAULT '',
            banned_subs TEXT DEFAULT '',
            default_volume INTEGER DEFAULT 5,
            default_speed REAL DEFAULT 1.0,
            sidebar_position TEXT DEFAULT 'left',
            feed_pinned_subs TEXT DEFAULT '',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )
    # Migrate columns for older databases --------------------------------
    for stmt in (
        "ALTER TABLE user_settings ADD COLUMN default_volume INTEGER DEFAULT 5",
        "ALTER TABLE user_settings ADD COLUMN default_speed REAL DEFAULT 1.0",
        "ALTER TABLE user_settings ADD COLUMN banned_subs TEXT DEFAULT ''",
        "ALTER TABLE user_settings ADD COLUMN sidebar_position TEXT DEFAULT 'left'",
        "ALTER TABLE user_settings ADD COLUMN feed_pinned_subs TEXT DEFAULT ''",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass  # column already exists
    conn.commit()
    conn.close()


# -----------------------------------------------------------------------
# Flask-Login User
# -----------------------------------------------------------------------

class User(UserMixin):
    """Thin wrapper used by Flask-Login."""

    def __init__(self, id: int, username: str):
        self.id = id
        self.username = username

    @staticmethod
    def get(user_id: int) -> "User | None":
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        if row:
            return User(row["id"], row["username"])
        return None

    @staticmethod
    def get_by_username(username: str) -> dict | None:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()
        if row:
            return {
                "id": row["id"],
                "username": row["username"],
                "password_hash": row["password_hash"],
            }
        return None

    @staticmethod
    def create(username: str, password: str) -> bool:
        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, generate_password_hash(password)),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()


# -----------------------------------------------------------------------
# Settings helpers
# -----------------------------------------------------------------------

def get_user_banned_subs(user_id: int) -> list[str]:
    """Return the list of subreddits a user has banned."""
    conn = get_db()
    row = conn.execute(
        "SELECT banned_subs FROM user_settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    if row and row["banned_subs"]:
        return [s.strip() for s in row["banned_subs"].split(",") if s.strip()]
    return []
