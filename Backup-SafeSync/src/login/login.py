import tkinter as tk
from tkinter import messagebox, ttk
import re
import os
import json
from datetime import datetime
import tkinter.simpledialog as simpledialog

from src.db import auth, db_utils
from src.login import google_auth

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SESSION_FILE = os.path.join(PROJECT_ROOT, "session.dat")

ACCENT_ORANGE_RED = '#FF5722' 
ACCENT_GREEN = '#059669'      

WINDOW_BG = "#F0F0F0"     
BG1 = WINDOW_BG          
CARD = "#FFFFFF"        
MUTED_FG = "#4A4A4A"     
HEADING_FG = ACCENT_GREEN 

ACCENT_HOVER = '#047857'   
ORANGE_HOVER = '#E64A19'   
ENTRY_BORDER = '#CCCCCC'  


def save_session(user_id: int, account_type: str, email: str = None):
    payload = {
        "user_id": int(user_id),
        "account_type": str(account_type),
        "email": email,
        "saved_at": datetime.utcnow().isoformat()
    }
    try:
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        print(f"[DEBUG] Session saved for user_id={user_id}, email={email}")
    except Exception as e:
        print(f"[WARN] Failed to save session: {e}")



def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return (
            int(payload.get("user_id")),
            str(payload.get("account_type")),
            payload.get("email")
        )
    except Exception as e:
        print(f"[WARN] Failed to read session file: {e}")
        try: os.remove(SESSION_FILE)
        except Exception: pass
        return None

def clear_session():
    try:
        if os.path.exists(SESSION_FILE):
            os.remove(SESSION_FILE)
    except Exception as e:
        print(f"[WARN] Failed to clear session file: {e}")


def open_signup(root):
    signup_window = tk.Toplevel(root)
    signup_window.title("Sign Up")
    signup_window.geometry("420x520")
    
    signup_window.configure(bg=BG1) 
    signup_window.resizable(False, False)

    frame = tk.Frame(signup_window, bg=CARD, bd=1, relief="solid")
    frame.place(relx=0.5, rely=0.5, anchor="center", width=380, height=460)

    tk.Label(frame, text="Create Account", font=("Segoe UI", 16, "bold"),
             bg=CARD, fg=ACCENT_GREEN).pack(pady=14)

    tk.Label(frame, text="Username", bg=CARD, fg=MUTED_FG).pack(pady=(8,0), anchor='w', padx=20)
    su_username_entry = tk.Entry(frame, width=34, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN, highlightthickness=0)
    su_username_entry.pack(pady=(4,8), padx=20, ipady=3) 

    tk.Label(frame, text="Email", bg=CARD, fg=MUTED_FG).pack(pady=(4,0), anchor='w', padx=20)
    su_email_entry = tk.Entry(frame, width=34, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN, highlightthickness=0)
    su_email_entry.pack(pady=(4,8), padx=20, ipady=3)

    tk.Label(frame, text="Password", bg=CARD, fg=MUTED_FG).pack(pady=(4,0), anchor='w', padx=20)
    su_password_entry = tk.Entry(frame, show="*", width=34, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN, highlightthickness=0)
    su_password_entry.pack(pady=(4,10), padx=20, ipady=3)

    def validate_email(email):
        return re.match(r"^[\w\.-]+@[\w\.-]+\.\w+$", email)

    def validate_password(password):
        return len(password) >= 8 and any(c.isdigit() for c in password) and any(c.isalpha() for c in password)

    def signup_action():
        username = su_username_entry.get().strip()
        email = su_email_entry.get().strip()
        password = su_password_entry.get().strip()

        if not username or not email or not password:
            messagebox.showerror("Error", "All fields are required!")
            return
        if not validate_email(email):
            messagebox.showerror("Error", "Invalid email format!")
            return
        if not validate_password(password):
            messagebox.showerror("Error", "Password must be 8+ chars with letters & numbers!")
            return

        try:
            auth.create_user(username, email, password)
            messagebox.showinfo("Success", "Account created successfully!")
            signup_window.destroy()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def create_signup_button(parent, text, bg_color, command):
        btn = tk.Button(parent, text=text, width=26, height=1, bd=0, relief='flat', font=('Segoe UI', 10, 'bold'), bg=bg_color, fg="white", cursor="hand2", command=command)
        hover_bg = ACCENT_HOVER if bg_color == ACCENT_GREEN else ORANGE_HOVER
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
        return btn

    create_signup_button(frame, "Create Account", ACCENT_GREEN, signup_action).pack(pady=(12,6))    
    create_signup_button(frame, "Cancel", ACCENT_ORANGE_RED, signup_window.destroy).pack(pady=(4,10))


def login_action(root, username_entry, password_entry, remember_var):
    from main import run_main_app
    username = username_entry.get().strip()
    password = password_entry.get().strip()

    if not username or not password:
        messagebox.showerror("Error", "Both fields are required!")
        return

    success, user_id, account_type = auth.verify_user(username, password)
    if not success:
        messagebox.showerror("Login failed", "Invalid username/email or password.")
        return

    save_session(user_id, account_type, email=username)
    print(f"[DEBUG] Login successful: user_id={user_id}, email={username}")

    try:
        root.destroy()
    except Exception:
        pass

    run_main_app() 


def guest_login(root):
    from main import run_main_app
    user_id, account_type = auth.create_or_get_guest()
    save_session(user_id, "Guest")
    try: root.destroy()
    except Exception: pass
    run_main_app() 


def login_with_google(root, remember_var):
    from main import run_main_app
    try:
        idinfo = google_auth.google_login()
        email = idinfo["email"]
        sub = idinfo["sub"]
        name = idinfo.get("name")

        user_id = google_auth.upsert_oauth_user("google", sub, email, name)
        save_session(user_id, "Google", email=email)
        print(f"[DEBUG] Google login successful: user_id={user_id}, email={email}")

        try: root.destroy()
        except Exception: pass
        run_main_app()  

    except Exception as e:
        messagebox.showerror("Error", f"Google login failed: {e}")


def forgot_password_flow(root):
    from src.db import email_utils, tokens
    import secrets
    from datetime import datetime, timedelta

    email = simpledialog.askstring("Forgot Password", "Enter your email:", parent=root)
    if not email:
        return

    user = auth.get_user_by_email(email)
    if not user:
        messagebox.showerror("Error", "User not found.")
        return

    token = secrets.token_urlsafe(12)
    expires_at = datetime.utcnow() + timedelta(minutes=15)
    try:
        tokens.create_password_reset_token(user["id"], token, expires_at)
    except Exception as e:
        print(f"[WARN] Failed to store password token: {e}")

    try:
        email_utils.send_plain_email(
            to_email=email,
            subject="Password reset code",
            body=f"Your password reset code is:\n\n{token}\n\nThis code will expire in 15 minutes."
        )
    except Exception as e:
        print(f"[WARN] send_plain_email failed: {e}")
        print(f"[DEBUG] Token for {email}: {token}")
        messagebox.showinfo("Info", "Could not send email. Check console for token (debug).")

    reset_win = tk.Toplevel(root)
    ResetCodeWindow(reset_win, email, user["id"])


class ResetCodeWindow:
    def __init__(self, master, email, user_id):
        self.master = master
        self.email = email
        self.user_id = user_id
        master.title("Enter Reset Code")
        master.geometry("380x320")
        master.configure(bg=BG1) 

        frame = tk.Frame(master, bg=CARD, bd=1, relief="solid")
        frame.place(relx=0.5, rely=0.5, anchor="center", width=340, height=280)

        tk.Label(frame, text="Enter the reset code:", bg=CARD, fg=MUTED_FG).pack(pady=(12,6))
        self.code_entry = tk.Entry(frame, width=30, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN)
        self.code_entry.pack(pady=6, ipady=3)

        tk.Label(frame, text="New Password:", bg=CARD, fg=MUTED_FG).pack(pady=(8,4))
        self.new_pass_entry = tk.Entry(frame, show="*", width=30, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN)
        self.new_pass_entry.pack(pady=6, ipady=3)

        tk.Label(frame, text="Confirm Password:", bg=CARD, fg=MUTED_FG).pack(pady=(8,4))
        self.conf_pass_entry = tk.Entry(frame, show="*", width=30, bd=1, relief="solid", bg=BG1, fg="#000000", insertbackground=ACCENT_GREEN)
        self.conf_pass_entry.pack(pady=6, ipady=3)

        btn = tk.Button(frame, text="Submit", width=20, bg=ACCENT_GREEN, fg="white", command=self.submit, bd=0, cursor="hand2")
        btn.pack(pady=12)
        btn.bind("<Enter>", lambda e: btn.config(bg=ACCENT_HOVER))
        btn.bind("<Leave>", lambda e: btn.config(bg=ACCENT_GREEN))

        master.update_idletasks()
        sw = master.winfo_screenwidth()
        sh = master.winfo_screenheight()
        mx = (sw // 2) - (380 // 2)
        my = (sh // 2) - (320 // 2)
        master.geometry(f"+{mx}+{my}")

    def submit(self):
        from src.db import tokens, auth as auth_module

        code = self.code_entry.get().strip()
        new_pass = self.new_pass_entry.get().strip()
        conf_pass = self.conf_pass_entry.get().strip()

        if not code or not new_pass or not conf_pass:
            messagebox.showerror("Error", "All fields are required!")
            return

        if new_pass != conf_pass:
            messagebox.showerror("Error", "Passwords do not match!")
            return

        if len(new_pass) < 8 or not any(c.isdigit() for c in new_pass) or not any(c.isalpha() for c in new_pass):
            messagebox.showerror("Error", "Password must be at least 8 characters long with letters & numbers.")
            return

        ok = tokens.verify_and_consume_password_token(self.user_id, code)
        if not ok:
            messagebox.showerror("Error", "Invalid or expired code.")
            return

        updated = auth_module.reset_password(self.user_id, new_pass)
        if updated:
            messagebox.showinfo("Success", "Password updated successfully. Please login again.")
            try: self.master.destroy()
            except Exception: pass
        else:
            messagebox.showerror("Error", "Failed to update password. Try again later.")


def start_login():
    session_data = load_session()
    if session_data:
        from main import run_main_app
        run_main_app()
        return

    root = tk.Tk()
    root.title("Login")
    root.geometry("460x520")
    root.configure(bg=BG1) 
    root.resizable(False, False)

    frame = tk.Frame(root, bg=CARD, bd=1, relief="solid") 
    frame.place(relx=0.5, rely=0.5, anchor="center", width=380, height=460)

    tk.Label(frame, text="Welcome Back", font=("Segoe UI", 18, "bold"), bg=CARD, fg=ACCENT_GREEN).pack(pady=20)

    def create_modern_entry(parent, text_label, placeholder, show=None):
        
        tk.Label(parent, text=text_label, bg=CARD, fg=MUTED_FG).pack(pady=(8, 0), anchor='w', padx=65)

        container = tk.Frame(parent, bg=CARD)
        container.pack(pady=2)

        entry = tk.Entry(container, width=30, font=("Segoe UI", 11), bd=1, relief="solid", bg=CARD, fg="#000000", insertbackground=ACCENT_GREEN, show=show)
        entry.pack(ipady=4) 
        
        if placeholder:
             entry.insert(0, placeholder)

        return entry

    username_entry = create_modern_entry(frame, "Username / Email", None)
    password_entry = create_modern_entry(frame, "Password", None, show="*")

    remember_var = tk.IntVar()
    
    #tk.Checkbutton(frame, text="Remember Me", bg=CARD, fg=MUTED_FG, selectcolor=CARD, variable=remember_var, font=("Segoe UI", 9), bd=1, relief="flat").pack(pady=10, anchor='w', padx=65)

    def create_modern_button(parent, text, bg_color, command):
        btn = tk.Button(parent, text=text, width=25, height=1, font=("Segoe UI", 10, "bold"), bg=bg_color, fg="white", bd=0, relief="flat", activebackground=bg_color, activeforeground="white", cursor="hand2", command=command)
        btn.pack(pady=6)
        
        hover_bg = ACCENT_HOVER if bg_color == ACCENT_GREEN else ORANGE_HOVER
        
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg_color))
        return btn

    create_modern_button(frame, "Login", ACCENT_GREEN, lambda: login_action(root, username_entry, password_entry, remember_var))
    create_modern_button(frame, "Login with Google", ACCENT_GREEN, lambda: login_with_google(root, remember_var))
    tk.Button(frame, text="Forgot Password?", fg=ACCENT_GREEN, bg=CARD, bd=0, font=("Segoe UI", 9, "underline"), activeforeground=ACCENT_HOVER, activebackground=CARD, command=lambda: forgot_password_flow(root)).pack(pady=6)    
    create_modern_button(frame, "Sign Up", ACCENT_ORANGE_RED, lambda: open_signup(root))

    root.mainloop()