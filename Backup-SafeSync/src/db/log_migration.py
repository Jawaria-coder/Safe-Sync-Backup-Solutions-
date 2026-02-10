import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "backup.db")

def create_logs_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'info',
            timestamp TEXT NOT NULL,
            details TEXT
        )

    """)
    conn.commit()
    conn.close()
