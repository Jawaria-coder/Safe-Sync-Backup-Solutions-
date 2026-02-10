# src/settings/settings_screen.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from src.ui.theme import BACKGROUND_GRAY, PRIMARY_BLUE, ACCENT_GREEN
from src.db import auth
import os
import json
import re
from src.login.login import load_session, save_session
from src.db import upload_to_drive

USER_DATA_DIR = "user_data"

class SettingsScreen(tk.Frame):
    def __init__(self, master, switch_view=None, account_type="Registered",
                 user_id=None, google_account=None, email=None):
        super().__init__(master)
        self.config(bg=BACKGROUND_GRAY)
        auth.add_google_account_column_if_missing()

        self.switch_view = switch_view
        self.account_type = account_type
        self.user_id = user_id
        self.google_account = google_account
        self.email = email

        os.makedirs(USER_DATA_DIR, exist_ok=True)

        if self.account_type.lower() == "guest":
            self.config_file = os.path.join(USER_DATA_DIR, "guest_session.json")
        else:
            self.config_file = os.path.join(USER_DATA_DIR, f"user_{self.user_id or 'unknown'}.json")

        self.settings = self.load_settings()

        self.temp_backup_path = self.settings.get("backup_path")
        self.temp_notify_enabled = self.settings.get("desktop_notifications_enabled", True)
        self.temp_notify_success = self.settings.get("notify_success", True)
        self.temp_notify_failure = self.settings.get("notify_failure", True)

        db_google_account = None
        if self.user_id:
             db_google_account = auth.get_google_email(self.user_id)
        self.temp_google_account = (
            db_google_account
            or self.settings.get("connected_google_account")
            or self.google_account
            or self.email
            or self._fetch_user_email()
            or "Not connected"
        )
        


        self.build_ui()

    def _fetch_user_email(self):
        if not self.user_id:
            return ""
        try:
            user = auth.get_user_by_email(self.user_id)
            return user.get("email", "")
        except Exception:
            return ""

    def build_ui(self):
        tk.Label(self, text="Application Settings", font=('Inter', 20, 'bold'),
                 bg=BACKGROUND_GRAY, anchor='w').pack(fill='x', pady=(15, 10), padx=20)

        container = tk.Frame(self, bg=BACKGROUND_GRAY)
        container.pack(fill='both', expand=True)
        canvas = tk.Canvas(container, bg="white", highlightthickness=0)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scrollbar.set)

        settings_area = tk.Frame(canvas, bg="white", padx=20, pady=20)
        canvas.create_window((0, 0), window=settings_area, anchor='nw')

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        settings_area.bind("<Configure>", on_configure)
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"))

        self.account_name_var = tk.StringVar(value=self.temp_google_account)
        self.connected_label = tk.Label(
            settings_area,
            text=f"Connected as: {self.account_name_var.get()}",
            bg="white",
            fg="#080606",
            font=('Inter', 11, 'bold')
        )
        self.connected_label.pack(anchor='w', pady=(3, 12), padx=(2, 0))

        account_btn_frame = tk.Frame(settings_area, bg="white")
        account_btn_frame.pack(anchor='w', pady=(0, 10))

        google_btn = tk.Button(
            account_btn_frame,
            text="Google Account",
            bg=PRIMARY_BLUE,
            fg='white',
            font=('Inter', 10, 'bold'),
            bd=0,
            padx=10, pady=5,
            cursor='hand2',
            relief='flat',
            command=self.open_google_account_popup
        )
        google_btn.pack(side='left', padx=(0, 8))

        self.change_drive_btn = tk.Button(
            account_btn_frame,
            text="Change Drive Account",
            command=self.change_drive_account,
            bg="#34A853",  
            fg="white",
            font=('Inter', 10, 'bold'),
            bd=0,
            padx=10, pady=5,
            cursor='hand2',
            relief='flat'
        )
        self.change_drive_btn.pack(side='left')



        if self.account_type.lower() == "registered":
            tk.Button(settings_area, text="Change Password", bg=PRIMARY_BLUE, fg="white",
                      font=('Inter', 10, 'bold'), bd=0, padx=10, pady=5,
                      cursor='hand2', command=self.open_change_password_popup).pack(anchor='w', pady=(10, 15))

        tk.Label(settings_area, text="Notifications", font=('Inter', 14, 'bold'),
                 bg="white", anchor='w').pack(fill='x', pady=(20, 8), padx=(5, 0))

        notif_frame = tk.Frame(settings_area, bg="white", highlightbackground="#d1d1d1",
                               highlightthickness=1, padx=20, pady=15)
        notif_frame.pack(fill='x', pady=(0, 20), padx=10)

        enable_frame = tk.Frame(notif_frame, bg="white")
        enable_frame.pack(fill='x', pady=(0, 12))
        self.enable_notifications = tk.BooleanVar(value=self.temp_notify_enabled)
        tk.Label(enable_frame, text="Enable Desktop Notifications", bg="white",
                 font=('Inter', 11, 'bold')).pack(side='left')
        tk.Checkbutton(enable_frame, variable=self.enable_notifications, bg="white",
                       onvalue=True, offvalue=False, relief='flat').pack(side='right')

        tk.Frame(notif_frame, height=1, bg="#e0e0e0").pack(fill='x', pady=(0, 12))

        self.notify_success = tk.BooleanVar(value=self.temp_notify_success)
        self.notify_failure = tk.BooleanVar(value=self.temp_notify_failure)
        tk.Checkbutton(notif_frame, text="Notify on Job Success",
                       variable=self.notify_success, bg="white", font=('Inter', 10)).pack(anchor='w', pady=2)
        tk.Checkbutton(notif_frame, text="Notify on Job Failure",
                       variable=self.notify_failure, bg="white", font=('Inter', 10)).pack(anchor='w', pady=2)

        bottom_frame = tk.Frame(settings_area, bg="white")
        bottom_frame.pack(fill='x', pady=(10, 0))
        tk.Button(bottom_frame, text="Default Backup Location", bg=PRIMARY_BLUE, fg="white",
                  font=('Inter', 10, 'bold'), bd=0, padx=10, pady=5,
                  cursor='hand2', command=self.open_backup_settings_popup).pack(anchor='w', pady=5)
        tk.Button(bottom_frame, text="Save Settings", bg=ACCENT_GREEN, fg="white",
                  font=('Inter', 10, 'bold'), bd=0, padx=15, pady=5,
                  cursor='hand2', command=self.save_all_settings).pack(anchor='w', pady=5)

        self.connected_label.config(text=f"Connected as: {self.account_name_var.get()}")

    def open_google_account_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Google Account")
        popup.configure(bg="white")
        popup.resizable(False, False)
        popup.geometry("420x260+500+200")

        tk.Label(popup, text="Google Account Settings", bg="white",
                 fg="black", font=('Inter', 14, 'bold')).pack(pady=(12, 18))

        tk.Label(popup, text="Connected Gmail Account:", bg="white", font=('Inter', 11)).pack()

        email_var = tk.StringVar(value=self.account_name_var.get() or "Not connected")
        email_entry = tk.Entry(popup, textvariable=email_var, font=('Inter', 11),
                               width=38, state='readonly', relief='solid', justify='center', bg="white")
        email_entry.pack(pady=(8, 15))

        def change_account():
            email_entry.config(state='normal', bg="#FFF9C4")
            email_entry.focus()

        def remove_account():
            confirm = messagebox.askyesno("Remove Account", "Are you sure you want to disconnect your Google account?")
            if confirm:
                self.account_name_var.set("Not connected")
                self.settings["connected_google_account"] = ""
                self._persist_settings()
                if self.user_id:
                    from src.db import auth
                    auth.update_google_email(self.user_id, "")
                self.connected_label.config(text="Connected as: Not connected")
                messagebox.showinfo("Removed", "Google account disconnected.")
                popup.destroy()

        def save_account():
            new_email = email_var.get().strip().lower()
            if "@" not in new_email:
                new_email += "@gmail.com"

            if not re.match(r"^[a-zA-Z0-9._%+-]+@gmail\.com$", new_email):
                messagebox.showerror("Invalid Email", "Please enter a valid Gmail address (e.g. yourname@gmail.com)")
                return

            self.account_name_var.set(new_email)
            self.settings["connected_google_account"] = new_email
            self._persist_settings()

            if self.user_id:
                from src.db import auth
                auth.update_google_email(self.user_id, new_email)

            self.connected_label.config(text=f"Connected as: {new_email}")
            email_entry.config(state='readonly', bg="white")
            messagebox.showinfo("Success", f"Connected to {new_email}")
            popup.destroy()

        def cancel_popup():
            popup.destroy()

        button_frame = tk.Frame(popup, bg="white")
        button_frame.pack(pady=(0, 15))

        btn_style = {"width": 16, "font": ('Inter', 10, 'bold'), "padx": 8, "pady": 6,
                     "bd": 0, "cursor": "hand2", "relief": "flat"}

        row1 = tk.Frame(button_frame, bg="white")
        row1.pack(pady=(0, 10))
        tk.Button(row1, text="Change Account", bg=PRIMARY_BLUE, fg="white",
                  command=change_account, **btn_style).grid(row=0, column=0, padx=15)
        tk.Button(row1, text="Remove Account", bg=PRIMARY_BLUE, fg="white",
                  command=remove_account, **btn_style).grid(row=0, column=1, padx=15)

        row2 = tk.Frame(button_frame, bg="white")
        row2.pack()
        tk.Button(row2, text="Save", bg=ACCENT_GREEN, fg="white",
                  command=save_account, **btn_style).grid(row=0, column=0, padx=15)
        tk.Button(row2, text="Cancel", bg="#BDC3C7", fg="black",
                  command=cancel_popup, **btn_style).grid(row=0, column=1, padx=15)

   
    def change_drive_account(self):
        """Allow user to switch their Google Drive account."""
        token_path = os.path.join("user_data", "token.json")

        if os.path.exists(token_path):
            os.remove(token_path)
            print("🗑️ Old Drive token deleted.")

        try:
            upload_to_drive.authenticate_drive()
            messagebox.showinfo("Drive Account", " Google Drive account changed successfully!")
            print(" Drive re-authentication successful.")
        except Exception as e:
            messagebox.showerror("Drive Error", f" Failed to change Drive account: {e}")
            print(f" Error changing Drive account: {e}")

    def open_backup_settings_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Backup Settings")
        popup.geometry("400x220")
        popup.config(bg="white")

        tk.Label(popup, text="Default Backup Settings", font=('Inter', 14, 'bold'),
                 bg="white").pack(fill='x', pady=(10, 15), padx=20)

        path_frame = tk.Frame(popup, bg="white")
        path_frame.pack(fill='x', pady=(0, 10), padx=20)

        tk.Label(path_frame, text="Current Location:", bg="white", font=('Inter', 10)).pack(anchor='w')
        self.path_var = tk.StringVar(value=self.temp_backup_path or "Not set")
        tk.Label(path_frame, textvariable=self.path_var, bg="white",
                 font=('Inter', 10, 'italic'), fg="gray").pack(anchor='w', pady=(3, 0))

        btn_frame = tk.Frame(popup, bg='white')
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Choose Folder", bg=PRIMARY_BLUE, fg="white",
                  font=('Inter', 10, 'bold'), bd=0, padx=12, pady=6,
                  cursor='hand2', command=lambda: self.select_backup_location(popup)).grid(row=0, column=0, padx=(0, 10))

        tk.Button(btn_frame, text="Remove Default", bg=PRIMARY_BLUE, fg="white",
                  font=('Inter', 10, 'bold'), bd=0, padx=12, pady=6,
                  cursor='hand2', command=lambda: self.remove_default_location(popup)).grid(row=0, column=1)

        tk.Button(popup, text="Close", bg="#bdc3c7", fg="black",
                  font=('Inter', 10, 'bold'), bd=0, padx=12, pady=6,
                  cursor='hand2', command=popup.destroy).pack(pady=(15, 5))

    def select_backup_location(self, popup=None):
        path = filedialog.askdirectory(title="Select Default Backup Folder")
        if path:
            self.temp_backup_path = path
            if hasattr(self, "path_var"):
                self.path_var.set(path)

    def remove_default_location(self, popup=None):
        self.temp_backup_path = None
        if hasattr(self, "path_var"):
            self.path_var.set("Not set")

    def open_change_password_popup(self):
        if not self.user_id:
            messagebox.showerror("Error", "User ID missing. Cannot change password.")
            return

        popup = tk.Toplevel(self)
        popup.title("Change Password")
        popup.geometry("400x300")
        popup.config(bg="white")

        tk.Label(popup, text="Change Your Password", font=('Inter', 14, 'bold'),
                 bg="white").pack(pady=(15, 10))

        form_frame = tk.Frame(popup, bg="white")
        form_frame.pack(pady=10, padx=20, fill='x')

        tk.Label(form_frame, text="Current Password:", bg="white").pack(anchor='w')
        current_entry = tk.Entry(form_frame, show="*")
        current_entry.pack(fill='x', pady=(0, 10))

        tk.Label(form_frame, text="New Password:", bg="white").pack(anchor='w')
        new_entry = tk.Entry(form_frame, show="*")
        new_entry.pack(fill='x', pady=(0, 10))

        tk.Label(form_frame, text="Confirm Password:", bg="white").pack(anchor='w')
        confirm_entry = tk.Entry(form_frame, show="*")
        confirm_entry.pack(fill='x', pady=(0, 10))

        def update_password():
            current = current_entry.get().strip()
            new = new_entry.get().strip()
            confirm = confirm_entry.get().strip()

            if not current or not new or not confirm:
                messagebox.showwarning("Warning", "Please fill all fields.")
                return
            if new != confirm:
                messagebox.showerror("Error", "New passwords do not match.")
                return
            if len(new) < 6:
                messagebox.showwarning("Warning", "Password must be at least 6 characters.")
                return
            try:
                if not auth.verify_local_password(self.user_id, current):
                    messagebox.showerror("Error", "Current password is incorrect.")
                    return
                if auth.update_local_password(self.user_id, new):
                    self.settings["password_changed"] = True
                    self._persist_settings()
                    messagebox.showinfo("Success", "Password updated successfully!")
                    popup.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to change password:\n{e}")

        tk.Button(popup, text="Update Password", bg=PRIMARY_BLUE, fg="white",
                  font=('Inter', 10, 'bold'), bd=0, padx=12, pady=6,
                  cursor='hand2', command=update_password).pack(pady=(10, 5))

        tk.Button(popup, text="Cancel", bg="#bdc3c7", fg="black",
                  font=('Inter', 10, 'bold'), bd=0, padx=12, pady=6,
                  cursor='hand2', command=popup.destroy).pack(pady=(0, 10))

    def save_all_settings(self):
        """Save all user settings locally (JSON only)."""
        self.settings.update({
            "backup_path": self.temp_backup_path,
            "connected_google_account": self.account_name_var.get(),
            "desktop_notifications_enabled": self.enable_notifications.get(),
            "notify_success": self.notify_success.get(),
            "notify_failure": self.notify_failure.get(),
        })

        if self._persist_settings():
            messagebox.showinfo("Success", "All settings saved successfully!")
            self.connected_label.config(text=f"Connected as: {self.account_name_var.get()}")

    def _persist_settings(self):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception:
            return False

    def load_settings(self):
        if os.path.exists(getattr(self, "config_file", "")):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}
    
