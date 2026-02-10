import sqlite3
import os
import hashlib
import binascii
from datetime import datetime, timezone
from src.db.path_helper import get_db_path

DB_PATH = get_db_path()

def get_connection():
    return sqlite3.connect(DB_PATH)



def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return binascii.hexlify(salt + hash_bytes).decode()


def verify_password(stored_hash: str, provided_password: str) -> bool:
    stored_bytes = binascii.unhexlify(stored_hash.encode())
    salt, stored_hash_bytes = stored_bytes[:16], stored_bytes[16:]
    new_hash = hashlib.pbkdf2_hmac("sha256", provided_password.encode(), salt, 100000)
    return new_hash == stored_hash_bytes


def get_connection():
    return sqlite3.connect(DB_PATH)


def create_user(username: str, email: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    password_hash = hash_password(password)
    created_at = datetime.now(timezone.utc)
    try:
        cur.execute("""
            INSERT INTO users (username, email, password_hash, created_at, is_guest)
            VALUES (?, ?, ?, ?, 0)
        """, (username, email, password_hash, created_at))
        conn.commit()
    except sqlite3.IntegrityError:
        print("Error: Username or Email already exists.")
    finally:
        conn.close()


def verify_user(username_or_email: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, password_hash, is_guest FROM users 
        WHERE username = ? OR email = ?
    """, (username_or_email, username_or_email))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, None, None

    user_id, stored_hash, is_guest = row[0], row[1], row[2]
    if verify_password(stored_hash, password):
        account_type = "Guest" if is_guest else "Registered"
        return True, user_id, account_type
    else:
        return False, None, None


def create_or_get_guest():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE is_guest=1")
    guest = cur.fetchone()
    if guest:
        conn.close()
        return guest[0], "Guest"

    created_at = datetime.utcnow().isoformat()
    cur.execute("""
        INSERT INTO users (username, email, password_hash, is_guest, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, ("guest", "guest@example.com", hash_password("guest"), 1, created_at))
    conn.commit()
    user_id = cur.lastrowid
    conn.close()
    return user_id, "Guest"


def reset_password(user_id: int, new_password: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_hash = hash_password(new_password)
        cur.execute("UPDATE users SET password_hash=? WHERE id=?", (new_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error resetting password: {e}")
        return False
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def verify_local_password(user_id: int, current_password: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password_hash, is_guest FROM users WHERE id=?", (user_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False

    stored_hash, is_guest = row
    if is_guest:
        return False

    return verify_password(stored_hash, current_password)


def update_local_password(user_id: int, new_password: str) -> bool:
    conn = get_connection()
    cur = conn.cursor()
    try:
        new_hash = hash_password(new_password)
        cur.execute("UPDATE users SET password_hash=? WHERE id=? AND is_guest=0", (new_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"[Password Update Error] {e}")
        return False
    finally:
        conn.close()

def add_google_account_column_if_missing():
    """Ensure 'google_account' column exists in 'users' table."""
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(users);")
    columns = [col[1] for col in cursor.fetchall()]

    if "google_account" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN google_account TEXT;")
        conn.commit()
        print("Column 'google_account' added successfully.")
    else:
        print("Column 'google_account' already exists.")

    conn.close()


def update_google_email(user_id: int, google_account: str) -> bool:
    """Save or update user's connected Google email."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE users SET google_account = ? WHERE id = ?", (google_account, user_id))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"[Google Email Update Error] {e}")
        return False


def get_google_email(user_id: int):
    """Retrieve the connected Google email for a user."""
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT google_account FROM users WHERE id = ?", (user_id,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else None
    except Exception:
        return None


