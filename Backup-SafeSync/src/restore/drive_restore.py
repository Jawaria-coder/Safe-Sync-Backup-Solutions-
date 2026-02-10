# src/restore/drive_restore.py
import os
import io
import tempfile
import shutil
import traceback
import zipfile
import tarfile
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload

from src.db import backup as db
from src.db.drive_auth import get_drive_credentials
from src.backup import encryption  # uses whatever decrypt_file implementation you have


def _to_bytes_hex_or_bytes(x) -> Optional[bytes]:
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


def _build_service(user_email):
    creds = get_drive_credentials(user_email)
    if not creds:
        raise RuntimeError("Google Drive credentials not available. Authenticate first.")
    svc = build("drive", "v3", credentials=creds, cache_discovery=False)
    return svc


def download_drive_file(service, file_id: str, local_path: Path) -> None:
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(str(local_path), mode='wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.close()


def _upload_file_to_parent(service, local_path: Path, parent_id: str, overwrite: bool = True) -> Dict[str, Any]:
    fname = local_path.name
    mimetype, _ = mimetypes.guess_type(str(local_path))
    mimetype = mimetype or 'application/octet-stream'

    if overwrite:
        qname = fname.replace("'", "\\'")
        q = f"name = '{qname}' and '{parent_id}' in parents and trashed=false"
        try:
            res = service.files().list(q=q, fields="files(id, name)").execute()
            files = res.get("files", [])
            if files:
                file_id = files[0]["id"]
                media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
                updated = service.files().update(fileId=file_id, media_body=media).execute()
                return updated
        except Exception:
            pass

    file_metadata = {"name": fname, "parents": [parent_id]}
    media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
    uploaded = service.files().create(body=file_metadata, media_body=media, fields="id, name").execute()
    return uploaded


def _ensure_drive_folder(service, name: str, parent_id: Optional[str] = None) -> str:
    parent_clause = f" and '{parent_id}' in parents" if parent_id else ""
    escaped_name = name.replace("'", "\\'")
    q = (
        f"name = '{escaped_name}' "
        f"and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false"
        f"{parent_clause}"
    )

    res = service.files().list(q=q, fields="files(id, name)").execute()
    files = res.get("files", [])
    if files:
        return files[0]["id"]
    meta = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        meta["parents"] = [parent_id]
    created = service.files().create(body=meta, fields="id").execute()
    return created["id"]


def _upload_directory_recursive(service, src_dir: Path, parent_id: str, overwrite: bool = True):
    created_folder_cache = {}
    created_folder_cache["."] = parent_id

    for root, dirs, files in os.walk(src_dir):
        root_path = Path(root)
        rel = root_path.relative_to(src_dir)
        rel_str = str(rel) if rel != Path('.') else "."
        drive_parent_for_root = created_folder_cache.get(rel_str, parent_id)

        for d in dirs:
            folder_rel = root_path.joinpath(d).relative_to(src_dir)
            folder_rel_str = str(folder_rel)
            folder_id = _ensure_drive_folder(service, d, parent_id=drive_parent_for_root)
            created_folder_cache[folder_rel_str] = folder_id

        for f in files:
            local_file = root_path / f
            _upload_file_to_parent(service, local_file, drive_parent_for_root, overwrite=overwrite)


# ---------------------------
# New helper: attempt many decrypt strategies
# ---------------------------
# New helper: attempt many decrypt strategies with debug
def _attempt_decrypt(artifact_local: Path, job: Dict[str, Any], password: Optional[str]) -> Tuple[Optional[Path], List[Tuple[str, str]]]:
    """
    Attempt decryption for a Drive artifact.
    Since your encryption.decrypt_file only takes 1 argument (path),
    just call it directly.
    """
    errors: List[Tuple[str, str]] = []

    try:
        print("[DEBUG] Attempting decryption using single-arg decrypt_file")
        res = encryption.decrypt_file(str(artifact_local))
        p = Path(res) if isinstance(res, (str, Path)) else artifact_local.with_suffix('')
        if p.exists():
            print(f"[DEBUG] Decryption successful: {p}")
            return (p, errors)
        else:
            errors.append(("single_arg", f"decrypt_file returned {res} but file not found"))
            return (None, errors)
    except Exception as e:
        errors.append(("single_arg", repr(e)))
        print(f"[DEBUG] Decryption failed: {repr(e)}")
        return (None, errors)

# ---------------------------
# Main restore API with debug
# ---------------------------
def restore_drive_job(
    job_id: int,
    drive_service=None,
    password: Optional[str] = None,
    overwrite: bool = True,
    custom_local_dest: Optional[str] = None
) -> Dict[str, Any]:
    job = db.get_job_by_id(job_id)
    if not job:
        raise ValueError(f"Job {job_id} not found")

    drive_file_id = job.get("drive_file_id")
    if not drive_file_id:
        raise ValueError("Job row does not contain 'drive_file_id'. Cannot restore from Drive automatically.")

    svc = drive_service or _build_service(user_email='None')

    target_parent_id = job.get("original_parent_id")
    if not target_parent_id and not custom_local_dest:
        try:
            meta = svc.files().get(fileId=drive_file_id, fields="parents").execute()
            parents = meta.get("parents", [])
            if parents:
                target_parent_id = parents[0]
            else:
                raise ValueError("No parent folder found for the artifact on Drive. Please set original_parent_id in DB.")
        except Exception as e:
            raise ValueError(f"Could not determine parent folder for artifact: {e}")

    tmpdir = Path(tempfile.mkdtemp(prefix="restore_drive_"))
    temp_decrypted_path: Optional[Path] = None

    try:
        artifact_local = tmpdir / "artifact.bin"
        download_drive_file(svc, drive_file_id, artifact_local)
        print("[DEBUG] Downloaded artifact exists:", artifact_local.exists(), artifact_local)
        working_path = artifact_local

        # If encrypted, attempt robust decrypt automatically
        if job.get("encryption"):
            decrypted_path, decrypt_errors = _attempt_decrypt(artifact_local, job, password=None)
            if not decrypted_path:
                print("[DEBUG] Decryption failed. Errors:", decrypt_errors)
                return {"status": "error", "error": "decrypt_failed", "decrypt_attempts": decrypt_errors}
            temp_decrypted_path = decrypted_path
            working_path = temp_decrypted_path
            print("[DEBUG] Using decrypted path:", working_path)

        # Local restore
        if custom_local_dest:
            dest_path = Path(custom_local_dest)
            dest_path.mkdir(parents=True, exist_ok=True)
            if _is_archive(working_path):
                _extract_archive_to(working_path, dest_path)
                return {"status": "ok", "detail": "extracted_to_local", "restored_path": str(dest_path.resolve())}
            else:
                dst_file = dest_path / working_path.name
                shutil.copy2(working_path, dst_file)
                return {"status": "ok", "detail": "copied_to_local", "restored_path": str(dst_file.resolve())}

        # Restore to Drive
        if _is_archive(working_path):
            extract_dir = tmpdir / "extracted"
            extract_dir.mkdir(parents=True, exist_ok=True)
            _extract_archive_to(working_path, extract_dir)
            _upload_directory_recursive(svc, extract_dir, target_parent_id, overwrite=overwrite)
            return {"status": "ok", "detail": "archive_extracted_to_drive", "target_parent": target_parent_id}
        else:
            uploaded = _upload_file_to_parent(svc, working_path, target_parent_id, overwrite=overwrite)
            return {"status": "ok", "uploaded_file_id": uploaded.get("id"), "target_parent": target_parent_id}

    except Exception as e:
        tb = traceback.format_exc()
        print("[ERROR] Drive restore failed:", e)
        print(tb)
        return {"status": "error", "error": str(e), "trace": tb}
    finally:
        if temp_decrypted_path and temp_decrypted_path.exists():
            try:
                temp_decrypted_path.unlink()
            except Exception:
                pass
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass
