import tkinter as tk
from tkinter import ttk, messagebox
from functools import partial

# Project modules
from src.dashboard.dashboard_screen import DashboardScreen
from src.backup.backup_screen import BackupJobsScreen
from src.restore.restore_screen import RestoreDataScreen
from src.settings.settings_screen import SettingsScreen
from src.ui.theme import BACKGROUND_GRAY, SIDEBAR_DARK, ACCENT_GREEN, PRIMARY_BLUE
from src.login import login
from src.backup import scheduler
from src.db.path_helper import get_db_path
from src.db.log_migration import create_logs_table


class BackupProApp(tk.Tk):
    def __init__(self, user_id, account_type, email):
        super().__init__()
        self.title("BackupPro Desktop Solution")
        self.geometry("1280x720")
        self.minsize(800, 600)

        self.user_id = user_id
        self.account_type = account_type
        self.email = email

        self._setup_styles()
        self._setup_layout()
        self._setup_sidebar()
        self._setup_screens()

        self.switch_view("dashboard")
        self.protocol("WM_DELETE_WINDOW", self.handle_close)

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=BACKGROUND_GRAY)
        style.configure("TLabel", background=BACKGROUND_GRAY)
        style.configure(
            "Action.TButton",
            font=("Inter", 10, "bold"),
            padding=10,
            background=PRIMARY_BLUE,
            foreground="white",
            relief="flat",
        )
        style.map("Action.TButton", background=[("active", "#D84315")])
        style.configure(
            "TProgressbar",
            background=ACCENT_GREEN,
            troughcolor="#E5E7EB",
            borderwidth=0,
            thickness=12,
        )
        style.configure(
            "Sidebar.TButton",
            background=SIDEBAR_DARK,
            foreground="white",
            font=("Inter", 10, "bold"),
            padding=[25, 12],
            relief="flat",
        )
        style.map(
            "Sidebar.TButton",
            background=[("active", "#1E293B")],
            foreground=[("active", ACCENT_GREEN)],
        )

    def _setup_layout(self):
        main_frame = tk.Frame(self)
        main_frame.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(main_frame, width=220, bg=SIDEBAR_DARK, relief="flat")
        self.sidebar.pack(side="left", fill="y")

        self.content_frame = tk.Frame(main_frame, bg=BACKGROUND_GRAY)
        self.content_frame.pack(side="right", fill="both", expand=True)

    def _setup_sidebar(self):
        tk.Label(
            self.sidebar,
            text="SafeSync",
            font=("Inter", 18, "bold"),
            bg=SIDEBAR_DARK,
            fg=PRIMARY_BLUE,
            pady=15,
        ).pack(pady=(10, 20))

        nav_items = [
            ("Dashboard", "dashboard"),
            ("Backup Data", "jobs"),
            ("Restore Data", "restore"),
            ("Settings", "settings"),
        ]

        for name, view_id in nav_items:
            ttk.Button(
                self.sidebar,
                text=f"  {name}",
                command=partial(self.switch_view, view_id),
                style="Sidebar.TButton",
            ).pack(fill="x", padx=10, pady=5)

        logout_btn = ttk.Button(
            self.sidebar, text="Logout", command=self.handle_logout, style="Action.TButton"
        )
        logout_btn.pack(side="bottom", fill="x", padx=10, pady=20)

    def _setup_screens(self):
        self.screens = {
            "dashboard": DashboardScreen(self.content_frame, self.switch_view),
            "jobs": BackupJobsScreen(
                self.content_frame, current_user_id=self.user_id, switch_view_callback=self.switch_view
            ),
            "restore": RestoreDataScreen(
                self.content_frame, self.switch_view, current_user_id=self.user_id
            ),
            "settings": SettingsScreen(
                self.content_frame,
                user_id=self.user_id,
                account_type=self.account_type,
                email=self.email,
            ),
        }

    def switch_view(self, view_id):
        if view_id not in self.screens:
            return
        for screen in self.screens.values():
            screen.pack_forget()
        self.screens[view_id].pack(fill="both", expand=True)
        self.title(f"BackupPro - {view_id.replace('_', ' ').title()}")

        if view_id == "dashboard":
            self.after(0, lambda: self.screens["dashboard"].refresh_stats())
            self.after(0, lambda: self.screens["dashboard"].refresh_activity())

    def handle_logout(self):
        try:
            scheduler.stop_scheduler()
        except Exception as e:
            print(f"[WARN] Scheduler stop failed: {e}")

        login.clear_session()
        self.destroy()
        login.start_login()

    def handle_close(self):
        try:
            try:
                scheduler.stop_scheduler()
            except Exception as e:
                print(f"[WARN] Scheduler stop failed: {e}")

            login.clear_session()
            self.destroy()
        except Exception as e:
            print(f"[ERROR] Error during window close: {e}")
            self.destroy()


def run_main_app():
    session_data = login.load_session()
    user_id, account_type, email = None, "Guest", None

    if isinstance(session_data, dict):
        user_id = session_data.get("user_id")
        account_type = session_data.get("account_type", "Guest")
        email = session_data.get("email")
    elif isinstance(session_data, (list, tuple)):
        user_id = session_data[0] if len(session_data) > 0 else None
        account_type = session_data[1] if len(session_data) > 1 else "Guest"
        email = session_data[2] if len(session_data) > 2 else None

    create_logs_table()

    if user_id:
        try:
            scheduler.start_scheduler(user_id=user_id)
        except Exception as e:
            print(f"[WARN] Could not start scheduler: {e}")

    app = BackupProApp(user_id, account_type, email)
    app.mainloop()



if __name__ == "__main__":
    login.start_login()