import tkinter as tk
from tkinter import messagebox
from src.dashboard import dashboard
from src.login import login
from src.db import auth


def start_login():
    """Start the login screen, with auto-login and modern UI"""

    try:
        session_data = login.load_session()
    except Exception as e:
        print(f"[Session Load Error] {e}")
        session_data = None

    if session_data:
        user_id, account_type = session_data
        dashboard.open_dashboard(user_id, account_type)
        return

    root = tk.Tk()
    root.title("Login")
    root.geometry("460x520")
    root.configure(bg="#0B0C10")
    root.resizable(False, False)

    frame = tk.Frame(root, bg="#1F2833", bd=0, relief="flat")
    frame.place(relx=0.5, rely=0.5, anchor="center", width=380, height=460)

    tk.Label(
        frame,
        text="Welcome Back",
        font=("Segoe UI", 18, "bold"),
        bg="#1F2833",
        fg="#66FCF1"
    ).pack(pady=20)

    def create_modern_entry(parent, placeholder, show=None):
        container = tk.Frame(parent, bg="#1F2833")
        container.pack(pady=8)
        entry = tk.Entry(container, width=30, font=("Segoe UI", 11), bd=0,
                         bg="#1F2833", fg="white", insertbackground="white")
        entry.pack()
        underline = tk.Frame(container, height=1.5, bg="#66FCF1", width=250)
        underline.pack(pady=(2, 0))
        entry.insert(0, placeholder)

        def on_focus_in(e):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                if show:
                    entry.config(show=show)

        def on_focus_out(e):
            if entry.get() == "":
                entry.insert(0, placeholder)
                entry.config(show="")

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        return entry

    username_entry = create_modern_entry(frame, "Username")
    password_entry = create_modern_entry(frame, "Password", show="*")

    remember_var = tk.IntVar()
    tk.Checkbutton(
        frame, text="Remember Me", bg="#1F2833", fg="#C5C6C7",
        selectcolor="#1F2833", variable=remember_var,
        activebackground="#1F2833", font=("Segoe UI", 9)
    ).pack(pady=10)

    def create_modern_button(parent, text, bg_color, command):
        btn = tk.Button(
            parent, text=text, width=25, height=1, font=("Segoe UI", 10, "bold"),
            bg=bg_color, fg="white", bd=0, relief="flat",
            activeforeground="#0B0C10", cursor="hand2", command=command
        )
        btn.pack(pady=6)
        btn.bind("<Enter>", lambda e: btn.config(bg="#66FCF1", fg="#0B0C10"))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color, fg="white"))
        return btn

    create_modern_button(
        frame, "Login", "#45A29E",
        lambda: login.login_action(root, username_entry, password_entry, remember_var)
    )

    create_modern_button(
        frame, "Login with Google", "#417BAE",
        lambda: login.login_with_google(root, remember_var)
    )

    create_modern_button(
        frame, "Continue as Guest", "#F5831E",
        lambda: login.guest_login(root)
    )

    tk.Button(
        frame, text="Forgot Password?", fg="#66FCF1", bg="#1F2833", bd=0,
        font=("Segoe UI", 9, "underline"), activebackground="#1F2833",
        activeforeground="#66FCF1",
        command=lambda: login.forgot_password_flow(root)
    ).pack(pady=6)

    create_modern_button(
        frame, "Sign Up", "#A83902",
        lambda: login.open_signup(root)
    )

    root.mainloop()


def open_account_settings(root, account_type, user_id):
    """Open account settings window"""
    win = tk.Toplevel(root)
    win.title("Account Settings")
    win.geometry("420x300")
    win.configure(bg="#1F2833")

    tk.Label(win, text="Account Settings", bg="#1F2833", fg="#66FCF1",
             font=("Segoe UI", 16, "bold")).pack(pady=15)

    tk.Label(win, text=f"User ID: {user_id}", bg="#1F2833", fg="white",
             font=("Segoe UI", 11)).pack(pady=4)
    tk.Label(win, text=f"Account Type: {account_type}", bg="#1F2833", fg="white",
             font=("Segoe UI", 11)).pack(pady=4)

    if account_type == "Registered":
        tk.Button(
            win, text="Change Password", bg="#45A29E", fg="white",
            font=("Segoe UI", 10, "bold"), width=20,
            command=lambda: change_password_window(root, user_id)
        ).pack(pady=10)
    else:
        tk.Label(win, text="Password change not available for this account type.",
                 bg="#1F2833", fg="#C5C6C7", font=("Segoe UI", 10)).pack(pady=10)

    tk.Button(
        win, text="Close", bg="#A83902", fg="white",
        font=("Segoe UI", 10, "bold"), width=20, command=win.destroy
    ).pack(pady=10)


def change_password_window(root, user_id):
    """Popup window to change password for local user"""
    win = tk.Toplevel(root)
    win.title("Change Password")
    win.geometry("400x320")
    win.configure(bg="#f8f8ff")

    tk.Label(win, text="Change Password", bg="#f8f8ff",
             font=("Segoe UI", 14, "bold"), fg="#333").pack(pady=10)

    tk.Label(win, text="Current Password:", bg="#f8f8ff").pack(pady=5)
    current_entry = tk.Entry(win, show="*", width=30)
    current_entry.pack(pady=5)

    tk.Label(win, text="New Password:", bg="#f8f8ff").pack(pady=5)
    new_entry = tk.Entry(win, show="*", width=30)
    new_entry.pack(pady=5)

    tk.Label(win, text="Confirm New Password:", bg="#f8f8ff").pack(pady=5)
    confirm_entry = tk.Entry(win, show="*", width=30)
    confirm_entry.pack(pady=5)

    def update_password_action():
        current = current_entry.get().strip()
        new = new_entry.get().strip()
        confirm = confirm_entry.get().strip()

        if not current or not new or not confirm:
            messagebox.showwarning("Input Error", "All fields are required.")
            return
        if new != confirm:
            messagebox.showwarning("Mismatch", "New passwords do not match.")
            return
        if len(new) < 6:
            messagebox.showwarning("Weak Password", "Password must be at least 6 characters.")
            return

        try:
            if not auth.verify_local_password(user_id, current):
               messagebox.showerror("Error", "Current password is incorrect.")
               return

            if auth.update_local_password(user_id, new):
               messagebox.showinfo("Success", "Password changed successfully.")
               win.destroy()
            else:
                messagebox.showerror("Error", "Failed to update password.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to change password:\n{e}")

    tk.Button(
        win, text="Update Password", bg="#45A29E", fg="white",
        font=("Segoe UI", 10, "bold"), width=20, command=update_password_action
    ).pack(pady=20)


def logout(root):
    """Logout user and return to login screen"""
    try:
        login.clear_session()
    except Exception as e:
        print(f"[Logout Error] {e}")
    root.destroy()
    start_login()
