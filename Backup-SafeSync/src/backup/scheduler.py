# src/backup/scheduler.py
import os
import json
import threading
import time
from datetime import datetime, timezone, timedelta
import time
import schedule
from src.backup.backup_manager import BackupManager
import src.db.backup as db

manager = BackupManager()

_scheduled_jobs = {}
_gui_callback = None
_scheduler_started = False
_scheduler_lock = threading.Lock()
_scheduler_running = False

_gui_root = None

def set_gui_root(root):
    global _gui_root
    _gui_root = root


def execute_job(job_id):
    """
    Scheduler-safe job execution.
    Fetches job from DB and runs it through _run_job.
    """
    job = db.get_job_by_id(job_id)
    if not job:
        print(f"[WARN] Scheduled Job {job_id} not found in DB. Skipping execution.")
        remove_job(job_id)
        return

    try:
        _run_job(job)
    except Exception as e:
        print(f"[ERROR] Failed to execute scheduled job {job_id}: {e}")


def _parse_schedule_time(job):
    """
    Parse job['schedule_time'] and return:
    - 'daily', 'weekly', or 'custom'
    - time details tuple
    """
    sched_raw = job.get("schedule_time")
    sched = str(sched_raw).strip() if sched_raw else ""
    if not sched:
        return None, None

    parts = sched.split()
    try:
        if sched.startswith("daily"):
            hour, minute = map(int, parts[1].split(":"))
            return "daily", (hour, minute)

        elif sched.startswith("weekly"):
            day = parts[1].lower()
            hour, minute = map(int, parts[2].split(":"))
            return "weekly", (day, hour, minute)

        else:
            date_part = parts[0]
            hour, minute = map(int, parts[1].split(":"))
            return "custom", (date_part, hour, minute)

    except Exception as e:
        print(f"[ERROR] Failed to parse schedule_time '{sched}' for job '{job.get('name')}': {e}")
        return None, None



def _run_job(job):
    try:
        sources_raw = job.get("sources", "[]")
        if isinstance(sources_raw, list):
            sources = sources_raw
        elif isinstance(sources_raw, str):
            try:
                sources = json.loads(sources_raw) if sources_raw.strip() else []
            except json.JSONDecodeError:
                sources = []
        else:
            sources = []

        db.update_job_status(job["id"], status="running")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔹 Starting backup for '{job.get('name')}'")

        password = job.get("encryption_password") if job.get("encryption") else None
        manager.run_job(job["id"], password=password)

        total_size = 0
        for path in sources:
            if os.path.exists(path):
                if os.path.isfile(path):
                    total_size += os.path.getsize(path)
                elif os.path.isdir(path):
                    for root, dirs, files in os.walk(path):
                        for f in files:
                            total_size += os.path.getsize(os.path.join(root, f))

        last_run_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        db.update_job_status(job["id"], status="completed", last_run=last_run_utc, size=total_size)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Backup completed for '{job.get('name')}' (Size: {total_size} bytes)")

        # ✅ Refresh BackupJobsScreen instantly
        if _gui_root:
            try:
                from src.backup.backup_screen import BackupJobsScreen
                for widget in _gui_root.winfo_children():
                    if isinstance(widget, BackupJobsScreen):
                        widget.load_jobs()
                        widget.update_idletasks()
                        print("[INFO] BackupJobsScreen refreshed immediately after scheduled job.")
            except Exception as e:
                print(f"[WARN] Could not refresh BackupJobsScreen: {e}")

        # ✅ Callback (no popup)
        if _gui_callback:
            try:
                _gui_callback(job["id"], True, None)
            except Exception as e:
                print(f"[WARN] GUI callback failed: {e}")

    except Exception as e:
        last_run_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Backup failed for '{job.get('name')}': {e}")
        db.update_job_status(job["id"], status="failed", last_run=last_run_utc)
        if _gui_callback:
            _gui_callback(job["id"], False, str(e))

def _schedule_job(job):
    """
    Schedules a backup job based on its schedule_time (daily/weekly/custom).
    Prevents duplicate immediate runs if the scheduled time has already passed today.
    """
    job_id = job["id"]
    sched_type, details = _parse_schedule_time(job)
    if not sched_type:
        return

    # Cancel any existing schedule for this job
    if job_id in _scheduled_jobs:
        schedule.cancel_job(_scheduled_jobs[job_id])
        print(f"[DEBUG] Previous schedule canceled for job_id={job_id}")

    def job_runner():
        threading.Thread(target=execute_job, args=(job_id,), daemon=True).start()

    now = datetime.now()

    # Daily schedule
    if sched_type == "daily":
        hour, minute = details
        scheduled_time_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        last_run_str = job.get("last_run")
        last_run_date = None
        if last_run_str:
            try:
                last_run_date = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
            except:
                pass

        # If scheduled time already passed today and job hasn't run yet today, run immediately
        if scheduled_time_today <= now and not (last_run_date and last_run_date.date() == now.date() and last_run_date >= scheduled_time_today):
            print(f"[DEBUG] Daily job '{job['name']}' already passed today, running immediately")
            threading.Thread(target=job_runner, daemon=True).start()
            # Schedule next run for tomorrow
            sched_obj = schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(job_runner)
            _scheduled_jobs[job_id] = sched_obj
            print(f"[INFO] Scheduled daily job '{job['name']}' for tomorrow at {hour:02d}:{minute:02d}")
        else:
            # Scheduled time is in the future today
            sched_obj = schedule.every().day.at(f"{hour:02d}:{minute:02d}").do(job_runner)
            _scheduled_jobs[job_id] = sched_obj
            print(f"[INFO] Scheduled daily job '{job['name']}' at {hour:02d}:{minute:02d}")

    # Weekly schedule
    elif sched_type == "weekly":
        day, hour, minute = details
        day_func = getattr(schedule.every(), day)

        scheduled_time_this_week = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        # Adjust weekday if needed
        weekday_map = {"monday":0, "tuesday":1, "wednesday":2, "thursday":3, "friday":4, "saturday":5, "sunday":6}
        target_weekday = weekday_map.get(day.lower(), 0)
        days_ahead = (target_weekday - now.weekday()) % 7
        scheduled_time_this_week += timedelta(days=days_ahead)

        last_run_str = job.get("last_run")
        last_run_date = None
        if last_run_str:
            try:
                last_run_date = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
            except:
                pass

        if scheduled_time_this_week <= now and not (last_run_date and last_run_date.date() == now.date() and last_run_date >= scheduled_time_this_week):
            print(f"[DEBUG] Weekly job '{job['name']}' already passed this week, running immediately")
            threading.Thread(target=job_runner, daemon=True).start()
            sched_obj = day_func.at(f"{hour:02d}:{minute:02d}").do(job_runner)
            _scheduled_jobs[job_id] = sched_obj
            print(f"[INFO] Scheduled weekly job '{job['name']}' for next week on {day} at {hour:02d}:{minute:02d}")
        else:
            sched_obj = day_func.at(f"{hour:02d}:{minute:02d}").do(job_runner)
            _scheduled_jobs[job_id] = sched_obj
            print(f"[INFO] Scheduled weekly job '{job['name']}' on {day} at {hour:02d}:{minute:02d}")

    # Custom schedule
    elif sched_type == "custom":
        date_str, hour, minute = details
        target_dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}", "%Y-%m-%d %H:%M")

        def custom_runner():
            delta = (target_dt - datetime.now()).total_seconds()
            if delta > 0:
                print(f"[INFO] Custom job '{job['name']}' will run in {int(delta)} seconds at {target_dt}")
                time.sleep(delta)
            job_runner()

        # Only start thread if custom datetime is in the future
        if target_dt > now:
            threading.Thread(target=custom_runner, daemon=True).start()
        else:
            print(f"[DEBUG] Custom job '{job['name']}' time already passed; running immediately")
            threading.Thread(target=job_runner, daemon=True).start()


def load_and_schedule_all_jobs(user_id):
    jobs = manager.get_all_jobs(user_id=user_id)
    print(f"[INFO] Loading {len(jobs)} jobs for user_id={user_id}")
    for job in jobs:
        if job.get("schedule_time"):
            _schedule_job(job)
        else:
            print(f"[INFO] Job '{job['name']}' has no schedule, will remain pending")


def run_scheduler():
    """Runs schedule.run_pending() in a separate thread"""
    global _scheduler_running
    _scheduler_running = True

    def loop():
        while _scheduler_running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except Exception as e:
                print(f"[Scheduler error]: {e}")

    threading.Thread(target=loop, daemon=True).start()
    print("[INFO] Scheduler loop started.")


def start_scheduler(user_id, gui_callback=None):
    """
    Start scheduler for a specific user.
    Ensures only one scheduler loop runs per app session.
    """
    global _gui_callback, _scheduler_started, _scheduler_running
    _gui_callback = gui_callback

    with _scheduler_lock:
        if _scheduler_started:
            print(f"[INFO] Scheduler already running, skipping duplicate start for user_id={user_id}")
            return
        _scheduler_started = True
        _scheduler_running = True

    print(f"[INFO] Starting scheduler for user_id={user_id} at {datetime.now()}")
    load_and_schedule_all_jobs(user_id)
    run_scheduler()


def stop_scheduler():
    """Stops the running scheduler loop."""
    global _scheduler_running, _scheduler_started

    _scheduler_running = False
    _scheduler_started = False
    schedule.clear()
    print("[INFO] Scheduler stopped and cleared all scheduled jobs.")


def add_and_schedule_job(job):
    """
    Add a new backup job and schedule it if it has a schedule_time.
    Jobs with no schedule_time will remain pending and NOT run immediately.
    """
    from src.db.backup import update_job_status

    update_job_status(job["id"], status="pending")
    print(f"[INFO] New job added: {job['name']} (ID: {job['id']})")

    if job.get("schedule_time"):
        print(f"[INFO] Scheduling job '{job['name']}' with schedule: {job['schedule_time']}")
        _schedule_job(job)
    else:
        print(f"[INFO] Job '{job['name']}' has no schedule_time; saved as pending.")


def remove_job(job_id):
    job_obj = _scheduled_jobs.get(job_id)
    if job_obj:
        try:
            schedule.cancel_job(job_obj)
            print(f"[INFO] Job {job_id} removed from scheduler")
        except Exception as e:
            print(f"[WARN] Could not remove scheduled job {job_id}: {e}")
        del _scheduled_jobs[job_id]