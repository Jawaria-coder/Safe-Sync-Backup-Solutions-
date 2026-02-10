# scripts/update_db.py
from src.db.path_helper import get_db_path
import sqlite3
import os

DB_PATH = get_db_path() 
print("Database path:", DB_PATH)

# test opening connection
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in DB:", tables)
conn.close()


def add_salt_iv_columns():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(backup)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'salt' not in columns:
        cursor.execute("ALTER TABLE backup ADD COLUMN salt BLOB")
        print("✅ Added 'salt' column to backup table")
    else:
        print("⚠ 'salt' column already exists")

    if 'iv' not in columns:
        cursor.execute("ALTER TABLE backup ADD COLUMN iv BLOB")
        print("✅ Added 'iv' column to backup table")
    else:
        print("⚠ 'iv' column already exists")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    add_salt_iv_columns()
