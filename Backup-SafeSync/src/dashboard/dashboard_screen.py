import tkinter as tk
from tkinter import ttk, messagebox
from src.ui.theme import BACKGROUND_GRAY
from src.ui.utils import create_status_badge
from src.backup.backup_manager import BackupManager
from src.login.login import load_session
from src.db.logs_helper import get_logs
import os
from datetime import datetime

class DashboardScreen(tk.Frame):
    def __init__(self, parent, switch_view_callback):
        super().__init__(parent)
        self.config(bg=BACKGROUND_GRAY)
        self.switch_view_callback = switch_view_callback

        session = load_session()
        self.user_id = session[0] if session else None
        self.manager = BackupManager()

        # ---------------- Header ----------------
        header = tk.Frame(self, bg=BACKGROUND_GRAY)
        header.pack(fill='x', padx=30, pady=(20, 10))
        tk.Label(
            header,
            text="SafeSync! One Click To Away Your Backup",
            font=("Inter", 26, "bold"),
            bg=BACKGROUND_GRAY,
            fg="#EB7A2E"
        ).pack(anchor='w')

        # ---------------- Cards ----------------
        cards_frame = tk.Frame(self, bg=BACKGROUND_GRAY)
        cards_frame.pack(pady=(40, 40), padx=40, fill="x")

        cards = [
            {"title": "Create Backup", "desc": "Backup Your Data", "btn_text": "Backup", "color": "#E05930",
             "command": lambda: self.switch_view_callback("jobs")},
            {"title": "Restore Backup", "desc": "Restore Your Data", "btn_text": "Restore", "color": "#DD0303",
             "command": lambda: self.switch_view_callback("restore")},
            {"title": "Settings", "desc": "Go To Settings", "btn_text": "Settings", "color": "#E05930",
             "command": lambda: self.switch_view_callback("settings")},
        ]

        for card in cards:
            frame = tk.Frame(cards_frame, bg=card["color"], width=300, height=140)
            frame.pack(side="left", expand=True, padx=20, pady=10, fill="both")
            frame.pack_propagate(False)

            tk.Label(frame, text=card["title"], bg=card["color"], fg="white", font=("Inter", 16, "bold")).pack(
                pady=(25, 2))
            tk.Label(frame, text=card["desc"], bg=card["color"], fg="white", font=("Inter", 12)).pack()
            tk.Button(frame, text=card["btn_text"], bg="white", fg="black", font=("Inter", 10, "bold"),
                      relief="flat", cursor="hand2", width=12, height=1, command=card["command"]).pack(pady=(12, 0))

        # ---------------- Stats ----------------
        self.stats_row = tk.Frame(self, bg=BACKGROUND_GRAY)
        self.stats_row.pack(pady=(10, 30), padx=40, fill="x")

        self.stat_labels = []  # store labels for refreshing
        self.create_stat_cards()

        # ---------------- Recent Activity ----------------
        activity_container = tk.Frame(self, bg="#f3f4f6")
        activity_container.pack(fill="x", expand=True, pady=(20, 40))
        recent_activity_frame = tk.Frame(activity_container, bg="#f3f4f6")
        recent_activity_frame.pack(anchor="center", fill="x", expand=True)

        tk.Label(
            recent_activity_frame,
            text="Recent Activity",
            font=("Inter", 18, "bold"),
            bg="#f3f4f6",
            fg="#111827"
        ).pack(anchor="center", pady=(0, 15))

        self.tree = self.create_activity_table(recent_activity_frame)
        self.refresh_activity()

    # ---------------- Create Stats Cards ----------------
    def create_stat_cards(self):
        stats = self.manager.get_backup_stats(self.user_id)
        stat_cards = [
            ("Total Backups Created", str(stats["total_backups"]), "#FAB12F"),
            ("Total Backups Completed", str(stats["completed"]), "#E05930"),
            ("Backups Scheduled", str(stats["scheduled"]), "#FEB21A"),
        ]

        # Clear previous cards if any
        for widget in self.stats_row.winfo_children():
            widget.destroy()
        self.stat_labels.clear()

        for title, value, color in stat_cards:
            card = tk.Frame(self.stats_row, bg=color, width=300, height=140, relief="flat", bd=0)
            card.pack(side="left", expand=True, padx=20, pady=10, fill="both")
            card.pack_propagate(False)

            tk.Label(card, text=title, bg=color, fg="white", font=("Inter", 14, "bold"),
                     wraplength=180, justify="center").pack(pady=(25, 5))

            value_label = tk.Label(card, text=value, bg=color, fg="white", font=("Inter", 20, "bold"))
            value_label.pack()
            self.stat_labels.append(value_label)

    # ---------------- Refresh Stats ----------------
    def refresh_stats(self):
        stats = self.manager.get_backup_stats(self.user_id)
        values = [stats["total_backups"], stats["completed"], stats["scheduled"]]
        for label, value in zip(self.stat_labels, values):
            label.config(text=str(value))

    # ---------------- Activity Table ----------------
    def create_activity_table(self, parent):
        table_frame = tk.Frame(parent, bg="white", highlightbackground="#D1D5DB", highlightthickness=1,
                               width=1000, height=360)
        table_frame.pack(anchor="center", pady=10)
        table_frame.pack_propagate(False)

        columns = ("activity", "last_run", "size")
        tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        tree.heading("activity", text="Activity")
        tree.heading("last_run", text="Last Run")
        tree.heading("size", text="Size")
        tree.column("activity", anchor="w")
        tree.column("last_run", width=200, anchor="center")
        tree.column("size", width=150, anchor="center")

        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True)

        style = ttk.Style()
        style.theme_use("clam")

        style.configure("Treeview",
                        font=("Inter", 12, "bold"),
                        rowheight=30,
                        background="white",
                        fieldbackground="white",
                        foreground="black"
                        )

        style.configure("Treeview.Heading",
                        font=("Inter", 12, "bold"),
                        background="#f3f4f6",
                        foreground="#111827"
                        )

        # Hover row color
        style.map("Treeview",
                  background=[("selected", "#F8F9FA")],
                  foreground=[("selected", "black")]
                  )

        # Status Accent Tags (thin left border)
        tree.tag_configure("success", background="white", foreground="#187A41")
        tree.tag_configure("failed", background="white", foreground="#E41E08")
        tree.tag_configure("warning", background="white", foreground="#FFB700")
        tree.tag_configure("info", background="white", foreground="#494949")




        return tree

    def refresh_activity(self):
        logs = get_logs(user_id=self.user_id, limit=10)
        tree = self.tree
        tree.delete(*tree.get_children())

        for log in logs:
            activity = log["action"]

            timestamp = datetime.fromisoformat(log["timestamp"])
            last_run = timestamp.strftime("%Y-%m-%d %H:%M")

            status = log["status"] or "info"

            size = ""
            if log.get("details") and log["details"].endswith((".zip", ".enc")):
                try:
                    size_bytes = os.path.getsize(log["details"])
                    if size_bytes > 1024 ** 2:
                        size = f"{size_bytes / (1024 ** 2):.1f} MB"
                    elif size_bytes > 1024:
                        size = f"{size_bytes / 1024:.1f} KB"
                    else:
                        size = f"{size_bytes} B"
                except Exception:
                    size = ""

            # Accent bar character + mapped color
            bar_icon = {
                "success": "🟩 ▍",
                "failed": "🟥 ▍",
                "warning": "🟨 ▍",
                "info": "⬜ ▍"
            }.get(status.lower(), "⬜ ▍")

            activity_display = f"{bar_icon} {activity}"

            tag = status.lower()
            if tag not in ["success", "failed", "warning", "info"]:
                tag = "info"

            tree.insert("", "end", values=(activity_display, last_run, size), tags=(tag,))

        if not logs:
            tree.insert("", "end", values=("No recent activity found", "", ""))
