import os
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.db.path_helper import get_db_path

DB_PATH = get_db_path()
print("[DEBUG] Using database at:", DB_PATH)

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db() -> None:
    """Create the backup table if it doesn't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT,
                sources TEXT,
                destination TEXT,
                compression TEXT,
                encryption INTEGER,
                schedule_time TEXT,
                last_run TEXT,
                total_size INTEGER,
                status TEXT,
                artifact_path TEXT,
                artifact_size INTEGER,
                salt BLOB,
                iv BLOB,
                created_at TEXT,
                finished_at TEXT,
                error TEXT
            )
        """)
        conn.commit()


def add_job(job_data: Dict[str, Any]) -> int:
    """Insert a new backup job and return its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()

        salt_value = job_data.get("salt")
        iv_value = job_data.get("iv")

        if isinstance(salt_value, str):
            try:
                salt_value = bytes.fromhex(salt_value)
            except ValueError:
                pass
        if isinstance(iv_value, str):
            try:
                iv_value = bytes.fromhex(iv_value)
            except ValueError:
                pass

        cursor.execute("""
        INSERT INTO backup (
            user_id, name, sources, destination, compression, encryption,
            schedule_time, last_run, total_size, status,
            artifact_path, artifact_size, salt, iv,
            encryption_password,
            created_at, finished_at, error,
            storage_type
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        job_data.get("user_id"),
        job_data.get("name"),
        json.dumps(job_data.get("sources", [])),
        job_data.get("destination"),
        job_data.get("compression"),
        1 if job_data.get("encryption") else 0,
        job_data.get("schedule_time"),
        job_data.get("last_run"),
        job_data.get("total_size"),
        job_data.get("status", "pending"),
        job_data.get("artifact_path"),
        job_data.get("artifact_size"),
        salt_value,
        iv_value,
        job_data.get("encryption_password"),
        job_data.get("created_at", datetime.utcnow().isoformat()),
        job_data.get("finished_at"),
        job_data.get("error"),
        job_data.get("storage_type", "local")  
    ))

        conn.commit()
        print("[DEBUG] Backup inserted successfully with salt/iv and storage_type")
        return cursor.lastrowid



def update_job_status(job_id: int, status: str, **kwargs) -> None:
    """Update the status and optional fields of a backup job."""
    print(f"[DEBUG] update_job_status() called for job_id={job_id}, status={status}")

    for key in ["salt", "iv"]:
        if key in kwargs and isinstance(kwargs[key], str):
            try:
                kwargs[key] = bytes.fromhex(kwargs[key])
            except ValueError:
                pass

    fields = ["status = ?"]
    values = [status]

    for key in [
        "artifact_path", "artifact_size", "finished_at",
        "error", "last_run", "total_size", "salt", "iv", "encryption_password"
    ]:
        if key in kwargs and kwargs[key] is not None:
            fields.append(f"{key} = ?")
            values.append(kwargs[key])

    values.append(job_id)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE backup SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
        print(f"[DEBUG] Database update completed for job_id={job_id}")





def get_all_jobs(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Retrieve all backup jobs, optionally filtered by user ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if user_id is not None:
            cursor.execute("SELECT * FROM backup WHERE user_id=? ORDER BY id DESC", (user_id,))
        else:
            cursor.execute("SELECT * FROM backup ORDER BY id DESC")
        rows = cursor.fetchall()
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in rows]


def get_job_by_id(job_id: int) -> Optional[Dict[str, Any]]:
    """Retrieve a single backup job by its ID."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM backup WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        cols = [col[0] for col in cursor.description]
        return dict(zip(cols, row))
    
def add_storage_type_column():
    """Add the storage_type column if it does not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(backup)")
        columns = [col[1] for col in cursor.fetchall()]
        if "storage_type" not in columns:
            cursor.execute("ALTER TABLE backup ADD COLUMN storage_type TEXT DEFAULT 'local'")
            conn.commit()
            print("[DEBUG] Added 'storage_type' column to backup table.")
        else:
            print("[DEBUG] 'storage_type' column already exists.")

def add_force_run_after_edit_column():
    """Add the force_run_after_edit column if it does not exist."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(backup)")
        columns = [col[1] for col in cursor.fetchall()]
        if "force_run_after_edit" not in columns:
            cursor.execute("ALTER TABLE backup ADD COLUMN force_run_after_edit INTEGER DEFAULT 0")
            conn.commit()
            print("[DEBUG] Added 'force_run_after_edit' column to backup table.")
        else:
            print("[DEBUG] 'force_run_after_edit' column already exists.")




init_db()
add_storage_type_column()
add_force_run_after_edit_column()