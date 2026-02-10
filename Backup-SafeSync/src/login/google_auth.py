import os
import tkinter as tk
from tkinter import messagebox
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2 import id_token
from google.auth.transport import requests
from src.db.db_utils import query_one, execute

# Location of client_secret.json (each dev creates their own copy)
CLIENT_SECRET_FILE = os.path.expanduser("~/secrets/client_secret.json")

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

def google_login():
    """Run Google OAuth flow, return idinfo dict with Google account details."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    idinfo = id_token.verify_oauth2_token(creds.id_token, requests.Request(), creds.client_id)
    return idinfo

def log_auth_event(user_id, event_type, detail):
    """Log authentication events in the auth_logs table."""
    execute(
        """INSERT INTO auth_logs (user_id, event_type, event_detail, created_at)
           VALUES (?, ?, ?, datetime('now'))""",
        (user_id, event_type, detail),
    )

def upsert_oauth_user(provider: str, sub: str, email: str, name: str = None):
    """Insert user if not exists, otherwise return existing user_id."""
    row = query_one("SELECT id FROM users WHERE oauth_provider=? AND oauth_sub=?", (provider, sub))
    if row:
        user_id = row[0]
        log_auth_event(user_id, f"{provider}_login", f"Signed in with {email}")
        return user_id

    username = email.split("@")[0]
    execute(
        """INSERT INTO users (username, email, oauth_provider, oauth_sub, email_verified, created_at)
           VALUES (?, ?, ?, ?, 1, datetime('now'))""",
        (username, email, provider, sub),
    )
    row = query_one("SELECT id FROM users WHERE oauth_provider=? AND oauth_sub=?", (provider, sub))
    user_id = row[0]
    log_auth_event(user_id, f"{provider}_signup", f"New {provider} account created for {email}")
    return user_id

def google_login_action(root):
    try:
        idinfo = google_login()
        email = idinfo["email"]
        sub = idinfo["sub"]
        name = idinfo.get("name")

        user_id = upsert_oauth_user("google", sub, email, name)
        print(f"✅ Signed in as {email}, user_id={user_id}")

        root.destroy()

        print("Launching main app...")
        from main import run_main_app
        run_main_app()

    except Exception as e:
        print(f"❌ Google login failed: {e}")
        messagebox.showerror("Login Error", f"Google login failed:\n{e}")
        
if __name__ == "__main__":
    try:
        idinfo = google_login()
        email = idinfo["email"]
        sub = idinfo["sub"]
        name = idinfo.get("name")

        user_id = upsert_oauth_user("google", sub, email, name)
        print(f"Signed in as {email}, user_id={user_id}")

        from main import run_main_app
        run_main_app()

    except Exception as e:
        print(f"Google login failed: {e}")