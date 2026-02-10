import os
import json
from datetime import datetime
from src.db import backup as db
from src.backup import compression, encryption
from src.login.login import load_session
from plyer import notification
import shutil
from src.db.upload_to_drive import upload_to_drive
import tkinter.messagebox as messagebox
from src.db.logs_helper import add_log


class BackupManager:
    def __init__(self, ui_ref=None):
        self.ui_ref = ui_ref

    def send_desktop_notification(self, title: str, message: str):
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Backup Manager",
                timeout=5
            )
        except Exception as e:
            print(f"[WARN] Desktop notification failed: {e}")

    def _load_user_settings(self, user_id):
        settings_path = os.path.join("user_data", f"user_{user_id}.json")
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get_current_user(self):
        session_data = load_session()
        if not session_data:
            raise RuntimeError("No active session! Please login first.")
        return session_data

    def get_default_backup_path(self, user_id):
        settings_file = os.path.join("user_data", f"user_{user_id}.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    path = data.get("backup_path")
                    if path and os.path.exists(path):
                        return path
            except Exception:
                pass
        return ""

    def create_job(self, sources, destination, job_data, user_id):
        if not user_id:
            raise ValueError("user_id is required")

        if not destination or destination.strip() == "":
            destination = self.get_default_backup_path(user_id)
            if not destination:
                raise ValueError("Destination path not set. Please configure in Settings.")

        job_data_to_insert = {
            "user_id": user_id,
            "name": job_data.get("name"),
            "sources": json.dumps(sources),
            "destination": job_data.get("destination"),
            "storage_type": job_data.get("storage_type", "local"),
            "compression": job_data.get("compression") or "zip",
            "encryption": job_data.get("encryption") or 0,
            "encryption_password": job_data.get("encryption_password"),
            "salt": job_data.get("salt"),
            "iv": job_data.get("iv"),
            "schedule_time": job_data.get("schedule_time"),
            "last_run": job_data.get("last_run"),
            "total_size": job_data.get("total_size") or 0,
            "status": job_data.get("status") or "pending",
            "artifact_path": job_data.get("artifact_path"),
            "artifact_size": job_data.get("artifact_size") or 0,
            "created_at": datetime.utcnow().isoformat(),
            "finished_at": job_data.get("finished_at"),
            "error": job_data.get("error"),
        }

        job_id = db.add_job(job_data_to_insert)

        from src.backup import scheduler
        scheduler.add_and_schedule_job(db.get_job_by_id(job_id))

        return job_id

    def run_job(self, job_id: int, password: str = None, progress_callback=None):
        job = db.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job ID {job_id} not found")

        if not self._has_source_changed(job):
            print(f"[INFO] No changes detected for '{job.get('name')}'. Skipping backup.")
            add_log(job.get("user_id"), f"Backup Skipped: {job.get('name')}", "warning")
            return "skipped"


        storage_type = (job.get("storage_type") or "local").lower()

        try:
            if storage_type == "drive":
                job_for_drive = {**job, "destination": "user_data", "compression": "zip"}
                artifact_path = self._run_backup(job_for_drive, password, progress_callback)
                if not artifact_path or not os.path.exists(artifact_path):
                    raise FileNotFoundError(f"Artifact not found: {artifact_path}")
                current_user_email = job.get("user_id")
                drive_id = upload_to_drive(artifact_path,user_email=current_user_email)
                if not drive_id:
                    raise RuntimeError("Drive upload failed.")

                # Save drive_file_id to DB
                try:
                    with db.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("UPDATE backup SET drive_file_id=? WHERE id=?", (drive_id, job["id"]))
                        conn.commit()
                except Exception as e:
                    print(f"[ERROR] Could not save drive_file_id: {e}")

                # Remove local temp artifact
                if os.path.exists(artifact_path):
                    os.remove(artifact_path)

                db.update_job_status(job["id"], status="completed", artifact_path=None, error=None)
                return "completed"
            else:
                result = self._run_backup(job, password, progress_callback=progress_callback)
                return result
        except Exception as e:
            print(f"[ERROR] Backup failed for '{job.get('name')}': {e}")
            db.update_job_status(job["id"], status="failed", error=str(e))
            raise

    def run_all_now(self, user_id=None, password: str = None, progress_callback=None):
        """Run all backup jobs now and show overall progress."""
        jobs = self.get_all_jobs(user_id)
        if not jobs:
            from tkinter import messagebox
            messagebox.showinfo("No Jobs", "No backup jobs found.")
            return

        job_files_count = {}
        total_files_all_jobs = 0
        jobs_files_list = {}
        for job in jobs:
            sources = json.loads(job.get("sources")) if isinstance(job.get("sources"), str) else job.get("sources", [])
            all_files = self._expand_sources(sources)
            jobs_files_list[job["id"]] = all_files
            job_files_count[job["id"]] = len(all_files) or 1
            total_files_all_jobs += job_files_count[job["id"]]

        processed_files = 0
        completed = skipped = failed = 0

        for job in jobs:
            try:
                all_files = jobs_files_list[job["id"]]

                def job_progress(percent, copied_bytes, total_bytes, speed, eta):
                    nonlocal processed_files
                    processed_files += copied_bytes / total_bytes * len(all_files) if total_bytes > 0 else 1
                    overall_percent = min((processed_files / total_files_all_jobs) * 100, 100)
                    if progress_callback:
                        progress_callback("All Jobs", overall_percent, int(processed_files), total_files_all_jobs, speed, eta)

                result = self.run_job(job["id"], password=password, progress_callback=job_progress)

                if result == "completed":
                    completed += 1
                elif result == "skipped":
                    skipped += 1
                else:
                    failed += 1

            except Exception as e:
                print(f"[ERROR] Backup failed for {job.get('name')}: {e}")
                failed += 1

        from tkinter import messagebox
        msg = (
            f"Total Jobs: {len(jobs)}\n"
            f"Completed: {completed}\n"
            f"Skipped (No Changes): {skipped}\n"
            f"Failed: {failed}"
        )
        messagebox.showinfo("All Backups Finished", msg)

    def _has_source_changed(self, job):
        try:
            # --- Force backup if job was edited ---
            if job.get("force_run_after_edit", 0):
                return True

            artifact_path = job.get("artifact_path")
            if not artifact_path or not os.path.exists(artifact_path):
                return True

            raw_sources = job.get("sources")
            if isinstance(raw_sources, str):
                sources = json.loads(raw_sources)
                while isinstance(sources, str):
                    sources = json.loads(sources)
            else:
                sources = raw_sources or []

            src_paths = [os.path.normpath(p) for p in sources if os.path.exists(p)]
            if not src_paths:
                return True

            last_run = job.get("last_run")
            if not last_run:
                return True

            try:
                last_backup_time = datetime.fromisoformat(last_run)
            except Exception:
                return True

            for path in src_paths:
                if os.path.isfile(path):
                    if os.path.getmtime(path) > last_backup_time.timestamp():
                        return True
                elif os.path.isdir(path):
                    for root, _, files in os.walk(path):
                        for file in files:
                            full_path = os.path.join(root, file)
                            try:
                                if os.path.getmtime(full_path) > last_backup_time.timestamp():
                                    return True
                            except FileNotFoundError:
                                return True

            # No changes detected
            return False

        except Exception as e:
            print(f"[WARNING] Change check failed: {e}")
            return True


    def _run_backup(self, job: dict, password: str = None, progress_callback=None):
        from src.db.logs_helper import add_log  # ensure logging is imported
        import shutil
        import os
        from datetime import datetime

        job_id = job.get("id")
        now_iso = datetime.now().astimezone().isoformat()

        # --- Mark job as running ---
        db.update_job_status(job_id, status="running", last_run=now_iso)

        # --- Reset force_run_after_edit immediately after marking running ---
        if job.get("force_run_after_edit", 0):
            with db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE backup SET force_run_after_edit = 0 WHERE id = ?",
                    (job_id,)
                )
                conn.commit()
            print(f"[DEBUG] force_run_after_edit reset for job_id={job_id}")

        if self.ui_ref and callable(self.ui_ref):
            self.ui_ref(job_id, True, "running")

        try:
            raw_sources = job.get("sources")
            sources = json.loads(raw_sources) if isinstance(raw_sources, str) else raw_sources or []
            while isinstance(sources, str):
                sources = json.loads(sources)
            src = [os.path.normpath(p) for p in sources if os.path.isdir(p) or os.path.isfile(p)]
            schedule_time = job.get("schedule_time")

            if not src:
                if schedule_time:
                    print(f"[INFO] No source files exist for scheduled job '{job.get('name')}'. Skipping.")
                    db.update_job_status(job.get("id"), status="skipped", error="No source files")
                    add_log(job.get("user_id"), f"Backup Skipped: {job.get('name')}", "warning", "No source files found")
                    return "skipped"
                else:
                    raise ValueError("Backup cannot run because original file/folders were deleted.")

            dest = os.path.normpath(job.get("destination", ""))
            os.makedirs(dest, exist_ok=True)
            all_files = self._expand_sources(src)

            compression_type = str(job.get("compression") or "none").strip().lower()
            encrypt = bool(job.get("encryption", 0))
            storage_type = (job.get("storage_type", "local") or "local").lower()
            if storage_type == "drive":
                compression_type = "zip"

            # --- Backup files / folders ---
            if compression_type in ["", "none", "no", "off"] and storage_type != "drive":
                # artifact_path = os.path.join(dest, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                artifact_path = os.path.join(dest, job["name"])
                os.makedirs(artifact_path, exist_ok=True)

                for src_path in src:
                    if os.path.isfile(src_path):
                        shutil.copy2(src_path, artifact_path)
                    else:
                        for root, _, files in os.walk(src_path):
                            for f in files:
                                file_path = os.path.join(root, f)
                                rel_path = os.path.relpath(file_path, src_path)
                                dest_file_path = os.path.join(artifact_path, os.path.basename(src_path), rel_path)
                                os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
                                shutil.copy2(file_path, dest_file_path)
            else:
                # artifact_path = os.path.join(dest, f"{job['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")
                artifact_path = os.path.join(dest, f"{job['name']}.zip")
                artifact_path = compression.create_archive(src, artifact_path, compression_type, progress_callback)

            # --- ENCRYPTION ---
            iv_hex = None
            if encrypt:
                if os.path.isdir(artifact_path):
                    temp_zip = artifact_path + ".zip"
                    artifact_path = compression.create_archive(all_files, temp_zip, "zip")
                    shutil.rmtree(artifact_path.replace(".zip", ""), ignore_errors=True)

                artifact_path = encryption.encrypt_file(artifact_path)
                unencrypted_path = artifact_path.replace(".enc", "")
                if os.path.exists(unencrypted_path):
                    os.remove(unencrypted_path)
            

            artifact_size = os.path.getsize(artifact_path) if os.path.exists(artifact_path) else 0
            total_size = sum(os.path.getsize(f) for f in all_files)

            # --- Update job status to completed ---
            db.update_job_status(
                job_id,
                status="completed",
                artifact_path=artifact_path,
                artifact_size=artifact_size,
                finished_at=now_iso,
                last_run=now_iso,
                total_size=total_size,
                error=None,
                salt=None,
                iv=iv_hex
            )

            add_log(job.get("user_id"), f"Backup Completed: {job.get('name')}", "success", artifact_path)

            settings = self._load_user_settings(job.get("user_id"))
            if settings.get("desktop_notifications_enabled", True) and settings.get("notify_success", True):
                self.send_desktop_notification(
                    title="Backup Completed",
                    message=f"Backup '{job['name']}' completed successfully!"
                )

            # --- ASK BEFORE DELETING ORIGINALS (Manual Backups Only) ---
            try:
                if not schedule_time:
                    answer = messagebox.askyesno(
                        "Delete Original Files?",
                        "Backup completed successfully!\nDo you want to delete the original files/folders?"
                    )
                    if answer:
                        self._delete_original(src)
            except Exception as e:
                print(f"[WARN] Could not show delete prompt: {e}")

            return artifact_path

        except Exception as e:
            add_log(job.get("user_id"), f"Backup Failed: {job.get('name')}", "failed", str(e))

            db.update_job_status(
                job_id,
                status="failed",
                error=str(e),
                finished_at=datetime.now().astimezone().isoformat()
            )
            settings = self._load_user_settings(job.get("user_id"))
            if settings.get("desktop_notifications_enabled", True) and settings.get("notify_failure", True):
                self.send_desktop_notification(
                    title="Backup Failed",
                    message=f"Backup '{job['name']}' failed!\nError: {e}"
                )
            return "failed"



    def _expand_sources(self, sources):
        all_files = []
        for path in sources:
            if os.path.isfile(path):
                all_files.append(path)
            elif os.path.isdir(path):
                for root, _, files in os.walk(path):
                    all_files.extend([os.path.join(root, f) for f in files])
        return all_files

    def get_all_jobs(self, user_id=None):
        return db.get_all_jobs(user_id)

    def get_backup_stats(self, user_id):
        """Return total backups and total scheduled backups for the given user."""
        try:
            jobs = db.get_all_jobs(user_id)
            total = len(jobs)
            scheduled = sum(1 for j in jobs if j.get("schedule_time"))

            completed = sum(1 for j in jobs if j.get("status") == "completed")
            failed = sum(1 for j in jobs if j.get("status") == "failed")

            return {
                "total_backups": total,
                "scheduled": scheduled,
                "completed": completed,
                "failed": failed,
            }

        except Exception as e:
            print(f"[ERROR] Could not fetch backup stats: {e}")
            return {
                "total_backups": 0,
                "scheduled": 0,
                "completed": 0,
                "failed": 0,
            }




    def delete_job_by_name(self, job_name: str):
        all_jobs = self.get_all_jobs()
        job = next((j for j in all_jobs if j["name"] == job_name), None)
        if not job:
            raise ValueError("Job not found")
        self.delete_job(job["id"], job.get("user_id"))
    

    def update_job_full(self, job_id, job_data):
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE backup
                SET name = ?,
                    sources = ?,
                    destination = ?,
                    compression = ?,
                    encryption = ?,
                    salt = ?,
                    iv = ?,
                    schedule_time = ?,
                    last_run = ?,
                    total_size = ?,
                    status = ?,
                    artifact_path = ?,
                    artifact_size = ?,
                    finished_at = ?,
                    error = ?,
                    force_run_after_edit = 1   -- <-- set flag here
                WHERE id = ?
            """, (
                job_data.get("name"),
                json.dumps(job_data.get("sources", [])),
                job_data.get("destination"),
                job_data.get("compression"),
                job_data.get("encryption"),
                job_data.get("salt"),
                job_data.get("iv"),
                job_data.get("schedule_time"),
                job_data.get("last_run"),
                job_data.get("total_size"),
                job_data.get("status", "pending"),
                job_data.get("artifact_path"),
                job_data.get("artifact_size"),
                job_data.get("finished_at"),
                job_data.get("error"),
                job_id
            ))
            conn.commit()

        print(f"[DEBUG] Job ID {job_id} fully updated! (force flag set)")

        # --- Log the edit/update ---
        user_id = job_data.get("user_id") or db.get_job_by_id(job_id).get("user_id")
        if user_id:
            add_log(user_id, f"Backup Edited: {job_data.get('name')}", "info", "Backup details updated")

        

    def _delete_original(self, paths):
        """Delete original files/folders after user confirmation."""
        for path in paths:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.isfile(path):
                    os.remove(path)
                print(f"[INFO] Deleted original: {path}")
            except Exception as e:
                print(f"[ERROR] Could not delete {path}: {e}")


    def delete_job(self, job_id, user_id=None):

            #  Get job from DB FIRST 
            job = next((j for j in self.get_all_jobs(user_id) if j["id"] == job_id), None)

            if job is None:
                raise Exception(f"Backup with ID {job_id} not found. Cannot delete.")

        #  Remove from scheduler
            try:
                from src.backup import scheduler
                scheduler.remove_job(job_id)
                print(f"[INFO] Job {job_id} removed from scheduler.")
            except Exception as e:
                print(f"[WARN] Could not remove job from scheduler: {e}")

        #  Delete from Google Drive
            if job.get("drive_file_id"):
                try:
                    from src.db.upload_to_drive import get_drive_credentials, delete_drive_file
                    creds = get_drive_credentials(job.get("user_email", None))

                    file_id = job["drive_file_id"]
                    ok = delete_drive_file(file_id, creds)

                    if ok:
                        print(f"[INFO] Deleted from Drive: {file_id}")
                    else:
                        print(f"[ERROR] Failed to delete from Drive: {file_id}")

                except Exception as e:
                    print(f"[ERROR] Drive deletion exception: {e}")

        # Delete local artifact
            artifact_path = job.get("artifact_path")
            if artifact_path and os.path.exists(artifact_path):
                try:
                    if os.path.isdir(artifact_path):
                        shutil.rmtree(artifact_path)
                    else:
                        os.remove(artifact_path)
                    print(f"[INFO] Deleted artifact: {artifact_path}")
                except Exception as e:
                    print(f"[ERROR] Could not delete artifact: {e}")

        #  Delete job from DB
            with db.get_connection() as conn:
                cursor = conn.cursor()
                if user_id:
                    cursor.execute("DELETE FROM backup WHERE id=? AND user_id=?", (job_id, user_id))
                else:
                    cursor.execute("DELETE FROM backup WHERE id=?", (job_id,))
                conn.commit()

        # Log the deletion
            add_log(user_id or job.get("user_id"), f"Backup Deleted: {job.get('name')}", "warning")

            print(f"[INFO] Job ID {job_id} deleted successfully.")