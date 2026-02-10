# src/backup/backup_screen.py
import json,os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox,simpledialog
from tkcalendar import Calendar
from src.ui.theme import BACKGROUND_GRAY, PRIMARY_BLUE
from src.backup.backup_manager import BackupManager
import threading
from datetime import datetime
from src.login.login import load_session
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
from plyer import notification
from src.backup.scheduler import start_scheduler, add_and_schedule_job
from datetime import datetime
import pytz
import time

import re  # <-- import re here

# --- Add sanitize_filename here ---
def sanitize_filename(name: str) -> str:
    # Remove invalid characters for file names (Windows, Linux, Mac)
    return re.sub(r'[^A-Za-z0-9_\-\. ]+', '', name)
class BackupJobsScreen(tk.Frame):
    def __init__(self, parent, current_user_id, switch_view_callback=None):
        super().__init__(parent)
        self.current_user_id = current_user_id  
        self.switch_view_callback = switch_view_callback
        self.config(bg=BACKGROUND_GRAY)
        self.manager = BackupManager(ui_ref=self)
        self.encryption_password = None
        self.storage_var = tk.StringVar(value="local")
        self.compression_var = tk.StringVar(value="zip")

        self.style = ttk.Style()
        self.style.configure(
            "Orange.TButton",
            background=PRIMARY_BLUE,
            foreground="white",
            font=('Inter', 9, 'bold'),
            padding=(6, 2),
            borderwidth=2,
            relief="solid",
            highlightthickness=1,
            highlightbackground="#E64A19"
        )
        self.style.map(
            "Orange.TButton",
            background=[("active", "#E64A19")],
            bordercolor=[("active", "#D84315")]
        )
        self.style.configure("Treeview", font=('Inter', 10))
        self.style.theme_use("default") 
        self.style.map(
            "Treeview",
            background=[("selected", "#D3D3D3")],  
            foreground=[("selected", "black")]    
        )


        tk.Label(
            self,
            text="Backup Jobs Configuration",
            font=('Inter', 20, 'bold'),
            bg=BACKGROUND_GRAY,
            anchor='w'
        ).pack(fill='x', pady=(15, 10), padx=20)

        actions_row = tk.Frame(self, bg=BACKGROUND_GRAY)
        actions_row.pack(fill='x', padx=20, pady=10)

        self.style.configure("Primary.TButton", background=PRIMARY_BLUE, foreground="white", font=('Segoe UI', 10, 'bold'))
        ttk.Button(actions_row, text="Create New Job", style="Orange.TButton", command=lambda: self.open_job_config()).pack(side='left', padx=5)
        ttk.Button(actions_row, text="Run All Now", style="Orange.TButton", command=self.run_all_jobs_thread).pack(side='left', padx=5)

        filter_frame = ttk.Frame(self, style="Card.TFrame")
        filter_frame.pack(fill="x", padx=20, pady=(5, 5))

        ttk.Label(filter_frame, text="Search:").pack(side="left", padx=(5, 3))
        self.search_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.search_var, width=25).pack(side="left", padx=(0, 10))

        ttk.Label(filter_frame, text="Schedule:").pack(side="left")
        self.schedule_filter_var = tk.StringVar()
        schedule_filter = ttk.Combobox(
            filter_frame,
            textvariable=self.schedule_filter_var,
            values=["All", "Daily", "Weekly", "Custom", "None"],
            width=10,
            state="readonly"
        )
        schedule_filter.current(0)
        schedule_filter.pack(side="left", padx=(5, 10))

        ttk.Label(filter_frame, text="Encryption:").pack(side="left")
        self.encryption_filter_var = tk.StringVar()
        encryption_filter = ttk.Combobox(
            filter_frame,
            textvariable=self.encryption_filter_var,
            values=["All", "Yes", "No"],
            width=8,
            state="readonly"
        )
        encryption_filter.current(0)
        encryption_filter.pack(side="left", padx=(5, 10))

        ttk.Button(filter_frame, text="Apply",style="Orange.TButton", command=self.apply_filters).pack(side="left", padx=(5, 3))
        ttk.Button(filter_frame, text="Clear",style="Orange.TButton", command=self.clear_filters).pack(side="left", padx=(3, 5))


        tree_frame = tk.Frame(self, padx=20, pady=10, bg='white')
        tree_frame.pack(fill='both', expand=True, padx=20, pady=(0, 20))

        columns = ("Name", "Source", "Destination", "Schedule", "Last Run", "Size", "Encryption","Compression" ,"Actions", "Run Backup")

        self.style = ttk.Style()
        self.style.theme_use("clam")  

        self.style.configure("Custom.Treeview",
                            background="white",
                            foreground="black",
                            rowheight=28,
                            fieldbackground="white",
                            font=('Inter', 10))

        self.style.map("Custom.Treeview",
                    background=[("selected", "#D3D3D3")],  
                    foreground=[("selected", "black")])

        self.tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10, style="Custom.Treeview")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        vsb.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        for col in columns:
            self.tree.heading(col, text=col, anchor='center')
            self.tree.column(col, anchor='center', width=120)

        self.tree.column("Name", width=140, anchor='w')
        self.tree.column("Source", width=200, anchor='w')
        self.tree.column("Size", width=90, anchor='e')
        self.tree.column("Encryption", width=100, anchor='center')
        self.tree.column("Compression", width=110, anchor='center')
        self.tree.column("Actions", width=130, anchor='center')
        self.tree.column("Run Backup", width=120, anchor='center')

        self.tree.bind("<Motion>", self._on_hover)
        self.tree.bind("<Leave>", self._on_leave)
        self.tree.bind("<Button-1>", self._on_click)


        self.load_jobs()
        start_scheduler(user_id=self.current_user_id, gui_callback=self.gui_callback)

        self.progress_frame = tk.Frame(self, bg=BACKGROUND_GRAY)
        self.progress_label = tk.Label(self.progress_frame, text="", bg=BACKGROUND_GRAY, anchor='w')
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self.progress_frame, maximum=100, variable=self.progress_var, style="Blue.Horizontal.TProgressbar")

        self.progress_label.pack(fill='x', padx=20, pady=(20, 5))
        self.progress_bar.pack(fill='x', padx=20, pady=(0, 30))


        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Blue.Horizontal.TProgressbar", troughcolor="#E0E0E0", background="#0078D7", thickness=16)

    def gui_callback(self, job_id, success, error_message=None):
        self.after(100, lambda: self._gui_update(job_id, success, error_message))

    def _gui_update(self, job_id, success, error_message=None):
        self.load_jobs()
        if error_message:
            messagebox.showerror("Backup Failed", f"Job failed: {error_message}")

   
    def open_job_config(self, existing_job=None):
        self.encryption_password = None 
        config_window = tk.Toplevel(self)
        config_window.title("Configure Backup Job")
        config_window.geometry("610x570")
        config_window.config(bg=BACKGROUND_GRAY)
        config_window.transient(self.master)
        config_window.grab_set()

        tk.Label(config_window, text="Backup Job Wizard", font=('Inter', 16, 'bold'), bg=BACKGROUND_GRAY).pack(pady=10)

        # name_frame = tk.LabelFrame(scrollable_frame, text="Job Name", padx=10, pady=10, bg='white')
        # name_frame.pack(fill='x', padx=20, pady=5)
        # # name_entry = ttk.Entry(name_frame, width=60)
        # name_entry = ttk.Entry(name_frame, width=60, state="readonly")

        # name_entry.pack(fill='x', padx=5)
        # if existing_job:
        #     name_entry.insert(0, existing_job.get("name", ""))


        source_frame = tk.LabelFrame(config_window, text="Step 1: Source", padx=10, pady=10, bg='white')
        source_frame.pack(fill='x', padx=20, pady=5)

        tk.Label(source_frame, text="Source Path:", bg='white').pack(side='left', padx=5)

        source_entry = ttk.Entry(source_frame, width=40)
        source_entry.pack(side='left', fill='x', expand=True)

        if existing_job:
            sources = existing_job.get("sources", [])
            if isinstance(sources, str):
                try:
                    sources = json.loads(sources)
                except:
                    sources = [sources]
            source_entry.insert(0, sources[0] if sources else "")

        def select_source_file():
            path = filedialog.askopenfilename(title="Select File to Backup")
            if path:
                source_entry.delete(0, tk.END)
                source_entry.insert(0, path)

                # Auto-generate job name
                source_name = os.path.basename(path.rstrip("/\\"))
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                auto_name = sanitize_filename(f"{source_name}_{timestamp}")
                name_entry.config(state="normal")
                name_entry.delete(0, tk.END)
                name_entry.insert(0, auto_name)
                name_entry.config(state="readonly")


        def select_source_folder():
            path = filedialog.askdirectory(title="Select Folder to Backup")
            if path:
                source_entry.delete(0, tk.END)
                source_entry.insert(0, path)

                # Auto-generate job name
                source_name = os.path.basename(path.rstrip("/\\"))
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                auto_name = sanitize_filename(f"{source_name}_{timestamp}")
                name_entry.config(state="normal")
                name_entry.delete(0, tk.END)
                name_entry.insert(0, auto_name)
                name_entry.config(state="readonly")


        ttk.Button(source_frame, text="Select File", style="Orange.TButton", command=select_source_file).pack(side='left', padx=4)
        ttk.Button(source_frame, text="Select Folder", style="Orange.TButton", command=select_source_folder).pack(side='left', padx=4)
        
        dest_frame = tk.LabelFrame(config_window, text="Step 2: Destination", padx=10, pady=10, bg='white')
        dest_frame.pack(fill='x', padx=20, pady=5)

        dest_var = tk.StringVar(value="local")

        tk.Label(dest_frame, text="Destination Type:", bg='white').pack(anchor='w', padx=5, pady=(0,5))
        tk.Radiobutton(dest_frame, text="Local Path", value="local", variable=dest_var, bg='white', command=lambda: toggle_destination()).pack(side='left',padx=5)
        tk.Radiobutton(dest_frame, text="Cloud Storage", value="drive", variable=dest_var, bg='white', command=lambda: toggle_destination()).pack(side='left',padx=5)

        dest_folder_frame = tk.Frame(dest_frame, bg='white')
        dest_folder_frame.pack(fill='x', padx=5, pady=(10,5))

        dest_folder_entry = ttk.Entry(dest_folder_frame, width=35)
        dest_folder_entry.pack(side='left', padx='5')
        if existing_job:
            dest_folder_entry.insert(0, existing_job.get("destination", ""))
        else:
             settings_file = f"user_data/user_{self.current_user_id}.json"
             if os.path.exists(settings_file):
                try:
                    with open(settings_file, "r", encoding="utf-8") as f:
                         settings = json.load(f)
                         default_location = settings.get("backup_path", "")
                         if default_location:
                            dest_folder_entry.insert(0, default_location)
                except Exception as e:
                       print(f"[DEBUG] Could not load default path: {e}")

        def browse_destination_folder():
            path = filedialog.askdirectory(title="Select Destination Folder")
            if path:
                dest_folder_entry.delete(0, tk.END)
                dest_folder_entry.insert(0, path)

        browse_button = ttk.Button(dest_folder_frame, text="Browse", style="Orange.TButton", command=browse_destination_folder)
        browse_button.pack(side='left', padx=5)

        def toggle_destination():
            """Show browse field only for local path"""
            if dest_var.get() == "local":
                dest_folder_frame.pack(fill='x', padx=5, pady=(10,5))
            else:
                dest_folder_frame.pack_forget()

        toggle_destination()
        schedule_frame = tk.LabelFrame(config_window, text="Step 3: Schedule", padx=10, pady=10, bg='white')
        schedule_frame.pack(fill='x', padx=20, pady=5)
        schedule_var = tk.StringVar(value="none")
        dynamic_widgets = {"hour_combo": None, "minute_combo": None, "day_combo": None, "calendar": None}

        def update_schedule():
            for widget in list(schedule_frame.pack_slaves()):
                if getattr(widget, "_is_dynamic", False):
                    widget.destroy()
            mode = schedule_var.get()
            if mode == "daily":
                lbl = tk.Label(schedule_frame, text="Run daily at:", bg='white'); lbl._is_dynamic=True; lbl.pack(anchor='w', padx=10)
                time_frame = tk.Frame(schedule_frame, bg='white'); time_frame._is_dynamic=True; time_frame.pack(anchor='w', padx=20)
                tk.Label(time_frame, text="Hour:", bg='white').pack(side='left')
                hour_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(24)], width=5, state="readonly"); hour_combo.set("12"); hour_combo.pack(side='left', padx=5)
                tk.Label(time_frame, text="Minute:", bg='white').pack(side='left')
                minute_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(0,60,5)], width=5, state="readonly"); minute_combo.set("00"); minute_combo.pack(side='left', padx=5)
                dynamic_widgets["hour_combo"], dynamic_widgets["minute_combo"] = hour_combo, minute_combo
            elif mode == "weekly":
                lbl = tk.Label(schedule_frame, text="Select day and time:", bg='white'); lbl._is_dynamic=True; lbl.pack(anchor='w', padx=10)
                day_combo = ttk.Combobox(schedule_frame, values=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"], width=20, state="readonly"); day_combo.set("Monday"); day_combo._is_dynamic=True; day_combo.pack(anchor='w', padx=20, pady=(0,10))
                time_frame = tk.Frame(schedule_frame, bg='white'); time_frame._is_dynamic=True; time_frame.pack(anchor='w', padx=20)
                tk.Label(time_frame, text="Hour:", bg='white').pack(side='left')
                hour_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(24)], width=5, state="readonly"); hour_combo.set("12"); hour_combo.pack(side='left', padx=5)
                tk.Label(time_frame, text="Minute:", bg='white').pack(side='left')
                minute_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(0,60,5)], width=5, state="readonly"); minute_combo.set("00"); minute_combo.pack(side='left', padx=5)
                dynamic_widgets["day_combo"], dynamic_widgets["hour_combo"], dynamic_widgets["minute_combo"] = day_combo, hour_combo, minute_combo
            elif mode == "custom":
                lbl = tk.Label(schedule_frame, text="Pick date and time:", bg='white'); lbl._is_dynamic=True; lbl.pack(anchor='w', padx=10)
                cal = Calendar(
                        schedule_frame,
                        selectmode='day',
                        date_pattern='yyyy-mm-dd',
                            
                        font=("Arial", 8),              # text small
                        selectforeground="black",
                        selectbackground="lightblue",
                )
                cal._is_dynamic=True; 
                cal.pack(anchor='w', padx=20, pady=(0,10))
                time_frame = tk.Frame(schedule_frame, bg='white'); time_frame._is_dynamic=True; time_frame.pack(anchor='w', padx=20)
                tk.Label(time_frame, text="Hour:", bg='white').pack(side='left')
                hour_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(24)], width=5, state="readonly"); hour_combo.set("12"); hour_combo.pack(side='left', padx=5)
                tk.Label(time_frame, text="Minute:", bg='white').pack(side='left')
                minute_combo = ttk.Combobox(time_frame, values=[f"{i:02d}" for i in range(0,60,5)], width=3, state="readonly"); minute_combo.set("00"); minute_combo.pack(side='left', padx=5)
                dynamic_widgets["calendar"], dynamic_widgets["hour_combo"], dynamic_widgets["minute_combo"] = cal, hour_combo, minute_combo

        tk.Radiobutton(schedule_frame, text="None", value="none", variable=schedule_var, command=update_schedule, bg='white').pack(side='left')
        tk.Radiobutton(schedule_frame, text="Daily", value="daily", variable=schedule_var, command=update_schedule, bg='white').pack(side='left')
        tk.Radiobutton(schedule_frame, text="Weekly", value="weekly", variable=schedule_var, command=update_schedule, bg='white').pack(side='left')
        tk.Radiobutton(schedule_frame, text="Custom Date & Time", value="custom", variable=schedule_var, command=update_schedule, bg='white').pack(side='left')
        update_schedule()

        if existing_job and existing_job.get("schedule_time"):
            sched = existing_job.get("schedule_time")
            try:
                if sched.startswith("daily"):
                    schedule_var.set("daily")
                    parts = sched.split()
                    if len(parts) == 2 and ":" in parts[1]:
                        hour, minute = parts[1].split(":")
                        dynamic_widgets["hour_combo"].set(hour)
                        dynamic_widgets["minute_combo"].set(minute)
                elif sched.startswith("weekly"):
                    schedule_var.set("weekly")
                    parts = sched.split()
                    if len(parts) == 3 and ":" in parts[2]:
                        day, time_part = parts[1], parts[2]
                        hour, minute = time_part.split(":")
                        dynamic_widgets["day_combo"].set(day)
                        dynamic_widgets["hour_combo"].set(hour)
                        dynamic_widgets["minute_combo"].set(minute)
                else:
                    schedule_var.set("custom")
                    parts = sched.split()
                    if len(parts) == 2 and ":" in parts[1]:
                        date_part, time_part = parts
                        hour, minute = time_part.split(":")
                        dynamic_widgets["calendar"].set_date(date_part)
                        dynamic_widgets["hour_combo"].set(hour)
                        dynamic_widgets["minute_combo"].set(minute)
            except Exception:
                pass


        compression_frame = tk.LabelFrame(config_window, text="Step 4: Compression Type", padx=10, pady=10, bg='white')
        compression_frame.pack(fill='x', padx=20, pady=5)
        self.compression_var = tk.StringVar(value="zip")
        tk.Radiobutton(compression_frame, text="No Compression", value="none", variable=self.compression_var, bg='white').pack(side='left',padx=10)
        tk.Radiobutton(compression_frame, text="ZIP (.zip)", value="zip", variable=self.compression_var, bg='white').pack(side='left',padx=10)
        tk.Radiobutton(compression_frame, text="TAR (.tar)", value="tar", variable=self.compression_var, bg='white').pack(side='left',padx=10)
        if existing_job and existing_job.get("compression"):
            self.compression_var.set(existing_job.get("compression"))


        adv_frame = tk.LabelFrame(config_window, text="Step 5: Advanced Options", padx=10, pady=10, bg='white')
        adv_frame.pack(fill='x', padx=20, pady=5)

        self.encryption_var = tk.BooleanVar()
        self.encryption_password = None  

        tk.Checkbutton(
            adv_frame, 
            text="Enable Encryption", 
            variable=self.encryption_var, 
            bg='white',
            
        ).pack(anchor='w')

        if existing_job:
            self.encryption_var.set(bool(existing_job.get("encryption", 0)))


        def save_job():
            # name = name_entry.get().strip()

            source_path = source_entry.get().strip()
            ####
            source_name = os.path.basename(source_path.rstrip("/\\"))
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            job_name = sanitize_filename(f"{source_name}_{timestamp}")
            ##
            dest_path = dest_folder_entry.get().strip()

            if dest_path:
                settings_file = f"user_data/user_{self.current_user_id}.json"
                os.makedirs(os.path.dirname(settings_file), exist_ok=True)
                try:
                    user_settings = {}
                    if os.path.exists(settings_file):
                        with open(settings_file, "r", encoding="utf-8") as f:
                            user_settings = json.load(f)
                    user_settings["backup_path"] = dest_path
                    with open(settings_file, "w", encoding="utf-8") as f:
                        json.dump(user_settings, f, indent=4)
                    print(f"[DEBUG] Saved default backup path: {dest_path}")
                except Exception as e:
                    print(f"[DEBUG] Could not save default path: {e}")

            compression_choice = self.compression_var.get()
            encrypt_choice = int(bool(self.encryption_var.get()))
            schedule_mode = schedule_var.get()
            schedule_str = None

            try:
                if schedule_mode == "none":
                    schedule_str = None

                elif schedule_mode == "daily":
                    hour_combo = dynamic_widgets.get("hour_combo")
                    minute_combo = dynamic_widgets.get("minute_combo")
                    if not hour_combo or not minute_combo:
                        messagebox.showerror("Error", "Please select hour and minute for daily schedule")
                        return
                    schedule_str = f"daily {hour_combo.get()}:{minute_combo.get()}"
                    print(f"[DEBUG] Daily schedule: {schedule_str}")

                elif schedule_mode == "weekly":
                    day_combo = dynamic_widgets.get("day_combo")
                    hour_combo = dynamic_widgets.get("hour_combo")
                    minute_combo = dynamic_widgets.get("minute_combo")
                    if not day_combo or not hour_combo or not minute_combo:
                        messagebox.showerror("Error", "Please select day, hour, and minute for weekly schedule")
                        return
                    schedule_str = f"weekly {day_combo.get()} {hour_combo.get()}:{minute_combo.get()}"
                    print(f"[DEBUG] Weekly schedule: {schedule_str}")

                elif schedule_mode == "custom":
                    cal_widget = dynamic_widgets.get("calendar")
                    hour_combo = dynamic_widgets.get("hour_combo")
                    minute_combo = dynamic_widgets.get("minute_combo")
                    if not cal_widget or not hour_combo or not minute_combo:
                        messagebox.showerror("Error", "Please select date, hour, and minute for custom schedule")
                        return
                    schedule_str = f"{cal_widget.get_date()} {hour_combo.get()}:{minute_combo.get()}"
                    print(f"[DEBUG] Custom schedule: {schedule_str}")

            except Exception as e:
                print(f"[DEBUG] Error building schedule string: {e}")

          
            if dest_var.get() == "local":
               dest_path = dest_folder_entry.get().strip()
            if dest_var.get() == "local":
                dest_path = dest_folder_entry.get().strip()
                if not dest_path:
                    messagebox.showerror("Error", "Please select a local destination folder.")
                    return

            elif dest_var.get() == "drive":
                from src.db.upload_to_drive import authenticate_drive
                base_dir = os.path.dirname(os.path.abspath(__file__))
                creds_path = os.path.normpath(os.path.join(base_dir, "../../user_data/token.json"))

                if not os.path.exists(creds_path):
                    result = messagebox.askyesno(
                        "Google Account Required",
                        "No Google Account connected. Would you like to connect your Google account now?"
                    )
                    if result:
                        try:
                            authenticate_drive()
                            messagebox.showinfo("Google Account", "Google Drive account connected successfully.")
                        except Exception as e:
                            messagebox.showerror("Drive Authentication Failed", f"Error: {e}")
                            return
                    else:
                        messagebox.showwarning(
                            "Drive Not Connected",
                            "Google account is required to back up to Drive. Job not saved."
                        )
                        return
                else:
                    try:
                        with open(creds_path, "r", encoding="utf-8") as f:
                            creds_data = json.load(f)
                        if not creds_data.get("token"):
                            raise ValueError("Invalid or missing token")
                    except Exception:
                        result = messagebox.askyesno(
                            "Invalid Google Credentials",
                            "Your Google Drive access token is missing or corrupted. Reconnect your account now?"
                        )
                        if result:
                            authenticate_drive()
                            messagebox.showinfo("Google Account", "Google Drive reconnected successfully.")
                        else:
                            return

                dest_path = "drive"


  
            
            if not job_name or not source_path or (dest_var.get() == "local" and not dest_path):
                messagebox.showerror("Error", "Please fill all required fields.")
                return
            self.storage_var.set(dest_var.get())

            job_data = {
                "name": job_name,
                "sources": [source_path],
                "storage_type": self.storage_var.get(),
                "destination": dest_path,
                "compression": compression_choice,
                "encryption": encrypt_choice,
                "salt": None,
                "iv": None,
                "encryption_password": self.encryption_password,
                "schedule_time": schedule_str,
                "last_run": existing_job.get("last_run") if existing_job else None,
                "total_size": existing_job.get("total_size") if existing_job else 0,
                "status": "pending",
                "artifact_path": existing_job.get("artifact_path") if existing_job else None,
                "artifact_size": existing_job.get("artifact_size") if existing_job else 0,
            }
            print("[DEBUG] Compression selected:", self.compression_var.get())

            try:
                from src.backup.scheduler import add_and_schedule_job

                if existing_job:
                    jid = existing_job["id"]
                    job_data["id"] = jid
                    self.manager.update_job_full(jid, job_data)
                    messagebox.showinfo("Success", f"Job '{job_name}' updated successfully!")
                    add_and_schedule_job(job_data)  
                else:
                    jid = self.manager.create_job([source_path], dest_path, job_data, user_id=self.current_user_id)
                    job_data["id"] = jid
                    add_and_schedule_job(job_data) 
                    messagebox.showinfo("Success", f"Job '{job_name}' created successfully!")

            except Exception as e:
                messagebox.showerror("Error", str(e))
                return

            config_window.destroy()
            self.load_jobs()

        ttk.Button(config_window, text="Save Job", style="Orange.TButton", command=save_job).pack(pady=15)
        # ttk.Button(config_window, text="Save Job", style="Orange.TButton", command=save_job).pack(pady=15)
        button_frame = tk.Frame(config_window, bg='white')
        button_frame.pack(pady=15)

        # save_button = tk.Button(
        #     button_frame, 
        #     text="Save Job", 
        #     bg="#212FF3", 
        #     fg="white", 
        #     padx=15, 
        #     command= save_job
        # )
        # save_button.pack(side="left")

        # save_run_button = tk.Button(
        #     button_frame,
        #     text="Run Now",
        #     bg="#F37221",
        #     fg="white",
        #     padx=15,
        #     pady=5,
        #     command=run_now_wrapper
        # )
        # save_run_button.pack(side="left", padx=10)


        
        # def run_now_after_save(job_id):
        #     def run():
        #         manager = BackupManager()
        #         manager.run_job(job_id)  # This will show progress, ask about deletion, etc.
            
        #     Thread(target=run, daemon=True).start()


        # run_now_button = tk.Button(
        #     button_frame,
        #     text="Run Now",
        #     bg="#26EC0C",
        #     fg="white",
        #     padx=15,
        #     pady=5,
        #     command=lambda: run_now_after_save(job_data["id"])  # use the saved job's ID
        # )





    def load_jobs(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        jobs = self.manager.get_all_jobs(user_id=self.current_user_id)
        for job in jobs:
            sources = job.get("sources", [])
            if isinstance(sources, (bytes, bytearray)):
                sources = sources.decode("utf-8", errors="ignore")

            if isinstance(sources, str):
                try:
                    while isinstance(sources, str):
                        sources = json.loads(sources)
                except Exception:
                    sources = [sources]

            if not isinstance(sources, list):
                sources = [sources]

            source_display = ", ".join(sources) if sources else ""
            print("Loaded sources raw:", job.get("sources"))
            print("Decoded:", sources)

            last_run = job.get("last_run") or ""
            if last_run:
                try:
                    dt = datetime.fromisoformat(last_run)
                    if dt.tzinfo is None:
                        dt = pytz.utc.localize(dt)
                    local_time = dt.astimezone(pytz.timezone("Asia/Karachi"))
                    last_run = local_time.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            size_bytes = job.get("total_size") or 0
            if size_bytes >= 1024*1024:
                size_display = f"{size_bytes / (1024*1024):.2f} MB"
            elif size_bytes >= 1024:
                size_display = f"{size_bytes / 1024:.2f} KB"
            else:
                size_display = f"{size_bytes} B"

            destination = job.get("destination") or ""
            if destination == "drive":
                destination_display = "Google Drive"
            else:
                destination_display = destination

            compression_display = job.get("compression") or "zip"

            self.tree.insert("", "end", values=(
                job.get("name"),
                source_display,
                destination_display,
                job.get("schedule_time") or "",
                last_run,
                size_display,
                "Yes" if job.get("encryption") else "No",
                compression_display,      
                "Edit / Delete",
                "Run Now"
            ))



    def apply_filters(self):
        """Filter jobs based on search text, schedule, and encryption."""
        search_text = self.search_var.get().lower().strip()
        schedule_filter = self.schedule_filter_var.get()
        encryption_filter = self.encryption_filter_var.get()

        for row in self.tree.get_children():
            self.tree.delete(row)

        jobs = self.manager.get_all_jobs(user_id=self.current_user_id)

        for job in jobs:
            name = job.get("name", "").lower()
            sources = str(job.get("sources", "")).lower()
            schedule = (job.get("schedule_time") or "None").capitalize()
            encryption = "Yes" if job.get("encryption") else "No"

            if search_text and search_text not in name and search_text not in sources:
                continue
            if schedule_filter != "All" and schedule_filter not in schedule:
                continue
            if encryption_filter != "All" and encryption_filter != encryption:
                continue

            last_run = job.get("last_run") or ""
            if last_run:
                try:
                    dt = datetime.fromisoformat(last_run)
                    last_run = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass

            size_bytes = job.get("total_size") or 0
            if size_bytes >= 1024 * 1024:
                size_display = f"{size_bytes / (1024 * 1024):.2f} MB"
            elif size_bytes >= 1024:
                size_display = f"{size_bytes / 1024:.2f} KB"
            else:
                size_display = f"{size_bytes} B"

            self.tree.insert("", "end", values=(
                job.get("name"),
                sources,
                job.get("destination"),
                job.get("schedule_time") or "",
                last_run,
                size_display,
                encryption,
                job.get("compression") or "zip",
                "Edit / Delete",
                "Run Now"
            ))

    def clear_filters(self):
        """Reset filters and reload all jobs."""
        self.search_var.set("")
        self.schedule_filter_var.set("All")
        self.encryption_filter_var.set("All")
        self.load_jobs()



    def _on_hover(self, event):
        pass
    def _on_leave(self, event):
        pass
    def _on_click(self, event):
        item_id = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item_id:
            return

        job_index = self.tree.index(item_id)
        jobs = self.manager.get_all_jobs(user_id=self.current_user_id)
        if job_index >= len(jobs):
            return
        job = jobs[job_index]

        col_num = int(column.replace("#", ""))
        if col_num == 9: 
            cell_bbox = self.tree.bbox(item_id, column)
            if not cell_bbox:
                return
            x_click = event.x - cell_bbox[0]

            cell_width = cell_bbox[2]
            if x_click < cell_width / 2:
                self.open_job_config(existing_job=job)
            else:
                response = messagebox.askyesno("Delete Backup", f"Are you sure you want to delete backup '{job['name']}'?")
                if response:
                    try:
                        artifact_path = job.get("artifact_path")
                        if artifact_path:
                            import shutil, os
                            if os.path.exists(artifact_path):
                                if os.path.isfile(artifact_path):
                                    os.remove(artifact_path)
                                else:
                                    shutil.rmtree(artifact_path)

                        self.manager.delete_job(job['id'], user_id=self.current_user_id)

                        messagebox.showinfo("Deleted", f"Backup '{job['name']}' deleted successfully!")
                        self.load_jobs()  
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not delete backup: {e}")


        elif col_num == 10: 
            try:
                password = job.get("encryption_password")

                def run_and_refresh():
                    try:
                        self.after(0, self.progress_frame.pack(fill='x'))
                        self.after(0, lambda: self.progress_label.config(text=f"Starting backup for '{job.get('name')}'..."))

                        def progress_callback(percent, copied_bytes, total_bytes, speed, eta):
                            self.after(0, lambda: self.progress_var.set(percent))
                            self.after(0, lambda: self.progress_bar.update_idletasks())
                            self.after(0, lambda: self.progress_label.config(
                                text=f"{job['name']}: {percent:.2f}% ({copied_bytes}/{total_bytes} B) - {speed:.2f} KB/s, ETA {eta}s"
                            ))
                            time.sleep(0.05) 
                        result = self.manager.run_job(job['id'], password=password, progress_callback=progress_callback)

                        if result == "skipped":
                            self.after(0, lambda: self.progress_var.set(100))
                            self.after(0, lambda: self.progress_label.config(
                                text=f"No changes detected for '{job.get('name')}'. Backup skipped."
                            ))

                        self.after(800, lambda: self.progress_var.set(0))
                        self.after(800, lambda: self.progress_label.config(text=""))
                        self.after(1200, lambda: self.progress_frame.pack_forget())

                        self.after(0, self.load_jobs)

                        def show_result():
                            import os
                            if result == "completed" or (isinstance(result, str) and os.path.exists(result)):
                                messagebox.showinfo("Success", f"Backup for '{job.get('name')}' completed successfully!")
                            elif result == "skipped":
                                messagebox.showinfo("Info", f"No changes detected for '{job.get('name')}'. Backup skipped.")
                            else:
                                messagebox.showerror("Failed", f"Backup for '{job.get('name')}' failed.")

                        self.after(0, show_result)

                    except Exception as e:
                        self.after(0, lambda e=e: messagebox.showerror("Error", f"Could not run backup: {e}"))

                threading.Thread(target=run_and_refresh, daemon=True).start()

            except Exception as e:
                messagebox.showerror("Error", f"Could not run backup: {e}")





    def run_all_jobs_thread(self):
        """Prompt for any required passwords on main thread, then run backups in background."""
        jobs = self.manager.get_all_jobs(user_id=self.current_user_id)
        if not jobs:
            messagebox.showinfo("No Jobs", "No backup jobs found for this user.")
            return

        job_passwords = {job['id']: job.get("encryption_password") for job in jobs if job.get("encryption")}

        threading.Thread(
            target=lambda: self._run_all_jobs(jobs, job_passwords),
            daemon=True
        ).start()


    def _run_all_jobs(self, jobs, job_passwords):
        """Perform all backups in background thread with overall progress."""
        total_jobs = len(jobs)
        completed_jobs = 0

        self.after(0, self.progress_frame.pack(fill='x'))

        for idx, job in enumerate(jobs, start=1):
            try:
                if job.get("encryption") and job["id"] not in job_passwords:
                    completed_jobs += 1
                    overall_percent = (completed_jobs / total_jobs) * 100
                    self.after(0, lambda p=overall_percent: self.progress_var.set(p))
                    continue

                password = job_passwords.get(job["id"])

                def progress_callback(percent, copied_bytes, total_bytes, speed, eta):
                    overall_percent = ((completed_jobs + percent / 100) / total_jobs) * 100
                    self.after(0, lambda p=overall_percent: self.progress_var.set(p))
                    self.after(0, lambda: self.progress_label.config(
                        text=f"{job['name']}: {percent:.2f}% ({copied_bytes}/{total_bytes} B) - {speed:.2f} KB/s, ETA {eta}s"
                    ))

                result = self.manager.run_job(job['id'], password=password, progress_callback=progress_callback)

                completed_jobs += 1
                overall_percent = (completed_jobs / total_jobs) * 100
                self.after(0, lambda p=overall_percent: self.progress_var.set(p))

            except Exception as e:
                print(f"[Error] Running job '{job['name']}': {e}")
                completed_jobs += 1
                overall_percent = (completed_jobs / total_jobs) * 100
                self.after(0, lambda p=overall_percent: self.progress_var.set(p))

        self.after(0, lambda: self.progress_var.set(100))
        self.after(0, lambda: self.progress_label.config(text="All backups done."))
        self.after(1000, lambda: self.progress_frame.pack_forget())

        self.after(0, self.load_jobs)
        msg = f"Completed {completed_jobs}/{total_jobs} backups.\n(Skipped jobs were unchanged.)"
        self.after(0, lambda: messagebox.showinfo("All Backups Done", msg))




    def prompt_encryption_password(self):
        """Prompt user for encryption password if toggle is checked."""
        if self.encryption_var.get():
            from tkinter import simpledialog, messagebox
            while True:
                pw = simpledialog.askstring(
                    "Encryption Password", "Enter password:", show='*', parent=self
                )
                if pw is None:  
                    self.encryption_var.set(False)
                    return
                confirm = simpledialog.askstring(
                    "Confirm Password", "Confirm password:", show='*', parent=self
                )
                if confirm is None:
                    self.encryption_var.set(False)
                    return
                if pw != confirm:
                    messagebox.showerror("Error", "Passwords do not match! Try again.")
                else:
                    self.encryption_password = pw
                    break