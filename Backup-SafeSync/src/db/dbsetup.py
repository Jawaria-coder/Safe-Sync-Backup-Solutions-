import sqlite3
import os

from src.db.path_helper import get_db_path

DB_PATH = get_db_path()
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # users table
    cur.execute("""  
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password_hash TEXT,
        oauth_provider TEXT,
        oauth_sub TEXT,
        is_guest INTEGER DEFAULT 0,
        email_verified INTEGER DEFAULT 0,
        created_at TEXT,
        last_login_at TEXT
    )
    """)

    # password tokens table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS password_tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        token_hash TEXT,
        purpose TEXT,
        expires_at TEXT,
        used INTEGER DEFAULT 0
    )
    """)

    # sessions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        token_hash TEXT,
        device_info TEXT,
        created_at TEXT,
        expires_at TEXT
    )
    """)

    # auth logs table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS auth_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        event_type TEXT,
        event_detail TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()
    print("All tables are ready.")

def init_db():
    migrate()

if __name__ == "__main__":
    migrate()
