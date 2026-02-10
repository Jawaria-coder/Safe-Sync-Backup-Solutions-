import sqlite3
from datetime import datetime
from src.db.log_migration import DB_PATH


def add_log(user_id, action, status="info", details=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO logs (user_id, action, status, timestamp, details)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, action, status, datetime.now().isoformat(), details))

        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[LOG ERROR] {e}")

def get_logs(user_id=None, limit=10):
    """
    Fetch recent logs. If user_id is provided, fetch logs for that user only.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        if user_id:
            cursor.execute(
                "SELECT action, status, timestamp, details FROM logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
                (user_id, limit)
            )
        else:
            cursor.execute(
                "SELECT action, status, timestamp, details FROM logs ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            logs.append({
                "action": row[0],
                "status": row[1],
                "timestamp": row[2],
                "details": row[3]
            })

        return logs

    except Exception as e:
        print(f"[LOG ERROR] {e}")
        return []
