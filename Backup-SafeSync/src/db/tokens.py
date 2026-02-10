import hashlib
import os
import sqlite3
from datetime import datetime, timedelta
from src.db.path_helper import get_db_path

DB_PATH = get_db_path()

def _connect():
    return sqlite3.connect(DB_PATH)

def _connect():
    return sqlite3.connect(DB_PATH)

def hash_token(token: str) -> str:
    """Return SHA256 hash of a token string."""
    return hashlib.sha256(token.encode()).hexdigest()

def verify_and_consume_password_token(user_id: int, token: str) -> bool:
    """Verify token is valid, not expired, not used. If valid → mark used."""
    token_hash = hash_token(token)

    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, expires_at, used FROM password_tokens
        WHERE user_id=? AND token_hash=? AND purpose=?
        ORDER BY id DESC LIMIT 1
    """, (user_id, token_hash, "password_reset"))
    row = cur.fetchone()

    if not row:
        conn.close()
        return False

    token_id, expires_at, used = row
    if used or datetime.fromisoformat(expires_at) < datetime.utcnow():
        conn.close()
        return False

    # Mark as used
    cur.execute("UPDATE password_tokens SET used=1 WHERE id=?", (token_id,))
    conn.commit()
    conn.close()
    return True

def create_password_reset_token(user_id: int, token: str, expires_at: datetime):
    """
    Store a provided token (already generated) in DB with expiry.
    """
    token_hash = hash_token(token)
    expires_str = expires_at.isoformat()

    conn = _connect()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO password_tokens (user_id, token_hash, purpose, expires_at, used)
        VALUES (?, ?, ?, ?, 0)
    """, (user_id, token_hash, "password_reset", expires_str))
    conn.commit()
    conn.close()
