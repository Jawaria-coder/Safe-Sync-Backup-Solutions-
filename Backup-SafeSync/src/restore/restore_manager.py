import os
import shutil
import zipfile
import tarfile
from pathlib import Path
from typing import Optional, Union
from datetime import datetime
import json
from src.db.backup import get_all_jobs, get_job_by_id
import src.backup.encryption as enc_mod
from src.db.logs_helper import add_log


TMP_RESTORE_DIR = Path.cwd() / "tmp_restored"
TMP_RESTORE_DIR.mkdir(parents=True, exist_ok=True)


def list_user_backups(user_id: int):
    return get_all_jobs(user_id=user_id)


def _to_bytes_hex_or_bytes(x: Union[bytes, str, None]) -> Optional[bytes]:
    if x is None:
        return None
    if isinstance(x, (bytes, bytearray)):
        return bytes(x)
    if isinstance(x, str):
        s = x.strip()
        if s.startswith(("0x", "0X")):
            s = s[2:]
        s = s.strip('\'"')
        try:
            return bytes.fromhex(s)
        except Exception:
            return s.encode("utf-8")
    return None


def _is_archive(path: Path) -> bool:
    try:
        return zipfile.is_zipfile(path) or tarfile.is_tarfile(path)
    except Exception:
        return False


def _extract_archive_to(archive_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if zipfile.is_zipfile(archive_path):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest_dir)
    elif tarfile.is_tarfile(archive_path):
        with tarfile.open(archive_path, "r:*") as tf:
            tf.extractall(dest_dir)
    else:
        raise ValueError(f"Not an archive: {archive_path}")


def _copy_file_to(file_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / file_path.name
    shutil.copy2(file_path, dest)
    return dest


def restore_job(job_id: int, password: Optional[str] = None, custom_dest: Optional[str] = None) -> Path:
    """
    Restore job:
      - If custom_dest is given → restore inside it (new subfolder).
      - If not → restore back to the ORIGINAL folder of the backed-up file.
    """
    job = get_job_by_id(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    artifact_path = Path(job.get("artifact_path", ""))
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")

    # ✅ Determine restore destination
    if custom_dest:
        # User selected custom folder
        base_restore_base = Path(custom_dest)
    else:
        # 🟢 Restore to original folder (where the original file came from)
        try:
            sources = json.loads(job.get("sources", "[]"))
            if sources:
                first_source = Path(sources[0])
                base_restore_base = first_source.parent  # original folder where file was backed up from
            else:
                # fallback in case original path missing
                base_restore_base = Path("D:/Restored_Backups")
        except Exception:
            base_restore_base = Path("D:/Restored_Backups")

    # ✅ Ensure base folder exists
    base_restore_base.mkdir(parents=True, exist_ok=True)

    # ✅ Subfolder for safety (optional)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    restore_dir = base_restore_base / f"Restored_Files_{timestamp}"
    restore_dir.mkdir(parents=True, exist_ok=True)

    working_path = artifact_path
    temp_decrypted_path: Optional[Path] = None


    if job.get("encryption"):
        # Use encryption module to decrypt automatically
        decrypted_result = enc_mod.decrypt_file(str(artifact_path))  # no password needed
        temp_decrypted_path = Path(decrypted_result)
        working_path = temp_decrypted_path


    # 📦 Extract or copy files
    try:
        if _is_archive(working_path):
            _extract_archive_to(working_path, restore_dir)
        else:
            _copy_file_to(working_path, restore_dir)
    finally:
        if temp_decrypted_path and temp_decrypted_path.exists():
            try:
                temp_decrypted_path.unlink()
            except Exception:
                pass

    print(f"[INFO] ✅ Restored successfully to: {restore_dir.resolve()}")
    user_id = job.get("user_id")
    add_log(user_id, f"Backup Restored: {job.get('name')}", "success", str(restore_dir.resolve()))

    return restore_dir
