import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from src.restore.restore_manager import list_user_backups, restore_job

class RestoreDataScreen(tk.Frame):
    def __init__(self, parent, switch_view_callback=None, current_user_id: int = None):
        super().__init__(parent)
        self.switch_view_callback = switch_view_callback
        self.user_id = current_user_id
        self.configure(bg="#F9FAFB")

        # 🎨 Theme colors
        self.primary_orange = "#F97316"
        self.hover_orange = "#EA580C"
        self.text_dark = "#0F172A"
        self.progress_bg = "#FFE7D4"

        # Title bar
        title_frame = tk.Frame(self, bg="#F9FAFB")
        title_frame.pack(fill="x", pady=(30, 10), padx=40)

        tk.Label(
            title_frame,
            text="🗂️ Restore Backups",
            font=("Inter", 24, "bold"),
            bg="#F9FAFB",
            fg=self.text_dark
        ).pack(side="left")

        ttk.Button(
            title_frame,
            text="⟳ Refresh",
            style="Accent.TButton",
            command=self.load_backups
        ).pack(side="right", padx=10)

        # Button area
        button_frame = tk.Frame(self, bg="#F9FAFB")
        button_frame.pack(fill="x", pady=25)

        ttk.Button(
            button_frame,
            text="Restore Selected Backup",
            command=self.restore_selected,
            style="Accent.TButton"
        ).pack(pady=10)

        # Button and Progress Styles
        style = ttk.Style()
        style.configure("Accent.TButton", background=self.primary_orange, foreground="white",
                        font=("Inter", 11, "bold"), padding=(18, 10), borderwidth=0)
        style.map("Accent.TButton", background=[("active", self.hover_orange), ("disabled", "#FDBA74")])
        style.configure("Orange.Horizontal.TProgressbar", troughcolor="white", background=self.primary_orange,
                        bordercolor="white", lightcolor=self.primary_orange, darkcolor=self.primary_orange, thickness=15)

        # Table container
        tree_frame = tk.Frame(self, bg="#F9FAFB")
        tree_frame.pack(fill="both", expand=True, padx=40, pady=10)

        style.theme_use("clam")
        style.configure("Treeview", background="white", foreground=self.text_dark,
                        rowheight=34, fieldbackground="white", font=("Inter", 10), borderwidth=0)
        style.configure("Treeview.Heading", background="#F1F5F9", foreground=self.text_dark,
                        font=("Inter", 11, "bold"))
        style.map("Treeview", background=[("selected", "#FFE7D4")])

        columns = ("Name", "Status", "Storage")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=15)
        self.tree.heading("Name", text="Backup Name")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Storage", text="Storage Type")

        self.tree.column("Name", width=320)
        self.tree.column("Status", width=120, anchor="center")
        self.tree.column("Storage", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=5, pady=10)

        self.load_backups()

    def load_backups(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            backups = list_user_backups(self.user_id)
            for job in backups:
                storage = job.get("storage_type", "Local").capitalize()
                status = job.get("status", "unknown").capitalize()
                self.tree.insert("", "end", values=(job["name"], status, storage),
                                 tags=(str(job["id"]),))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load backups:\n{e}")

    def show_progress(self, message="Restoring..."):
        progress_win = tk.Toplevel(self)
        progress_win.title("")
        progress_win.configure(bg="white")
        progress_win.geometry("400x180")
        progress_win.resizable(False, False)
        progress_win.grab_set()

        # Center modal on parent
        self.update_idletasks()
        x = self.winfo_rootx() + self.winfo_width() // 2 - 200
        y = self.winfo_rooty() + self.winfo_height() // 2 - 90
        progress_win.geometry(f"+{x}+{y}")

        container = tk.Frame(progress_win, bg="white")
        container.pack(expand=True, fill="both", padx=20, pady=20)

        tk.Label(container, text=message, font=("Inter", 13, "bold"),
                 bg="white", fg=self.text_dark, pady=10).pack()

        pb = ttk.Progressbar(container, style="Orange.Horizontal.TProgressbar",
                             mode="indeterminate", length=260)
        pb.pack(pady=15)
        pb.start(15)

        return progress_win, pb

    def restore_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("No Selection", "Please select a backup to restore.")
            return

        job_id = int(self.tree.item(selected[0], "tags")[0])

        from src.db.backup import get_job_by_id
        job = get_job_by_id(job_id)
        if not job:
            messagebox.showerror("Error", f"Job {job_id} not found in database.")
            return

        storage_type = (job.get("storage_type") or "").lower()
        restore_dest = filedialog.askdirectory(title="Select Folder to Restore Backup")
        if not restore_dest:
            messagebox.showinfo("Cancelled", "Restore cancelled.")
            return

        password = None
        progress_win, pb = self.show_progress("Restoring your files...")

        def finish_progress(callback):
            self.after(800, callback)

        def do_restore():
            try:
                if storage_type == "drive" or job.get("drive_file_id"):
                    from src.restore.drive_restore import restore_drive_job
                    result = restore_drive_job(job_id=job_id, drive_service=None,
                                               password=password, custom_local_dest=restore_dest, overwrite=True)

                    def close_and_notify():
                        pb.stop()
                        progress_win.destroy()
                        if result and result.get("status") == "ok":
                            messagebox.showinfo("Restore Complete", f"Drive backup restored to:\n{restore_dest}")
                        else:
                            err = result.get("error") if isinstance(result, dict) else str(result)
                            messagebox.showerror("Restore Failed", f"Drive restore failed:\n{err}")
                        # 🔄 Refresh table after restore
                        self.load_backups()

                    finish_progress(close_and_notify)
                else:
                    restored_path = restore_job(job_id, custom_dest=restore_dest)

                    def close_and_notify():
                        pb.stop()
                        progress_win.destroy()
                        messagebox.showinfo("Restore Complete", f"Files restored to:\n{restored_path}")
                        # 🔄 Refresh table after restore
                        self.load_backups()

                    finish_progress(close_and_notify)
            except Exception as e:
                pb.stop()
                progress_win.destroy()
                messagebox.showerror("Restore Failed", str(e))

        self.after(100, do_restore)
