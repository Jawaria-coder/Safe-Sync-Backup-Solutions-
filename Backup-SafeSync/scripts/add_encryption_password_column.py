import sqlite3
import os

import sqlite3
from src.db.path_helper import get_db_path

DB_PATH = get_db_path()

def add_encryption_password_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(backup)")
    columns = [col[1] for col in cursor.fetchall()]

    if "encryption_password" not in columns:
        cursor.execute("ALTER TABLE backup ADD COLUMN encryption_password TEXT")
        conn.commit()
        print(" Added 'encryption_password' column to backup table")
    else:
        print("'encryption_password' column already exists")

    conn.close()

if __name__ == "__main__":
    add_encryption_password_column()
