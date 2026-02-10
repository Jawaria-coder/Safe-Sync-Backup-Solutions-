import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Google Drive API scopes
SCOPES = ['https://www.googleapis.com/auth/drive']

def get_drive_credentials(user_email):
    """
    Returns credentials for the given user.
    Each user gets their own token file to avoid conflicts.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    base_dir = os.path.dirname(os.path.abspath(__file__))
    cred_path = os.path.normpath(os.path.join(base_dir, "../../user_data/credentials.json"))
    token_path = os.path.normpath(os.path.join(base_dir, f"../../user_data/token_{user_email}.json"))

    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(cred_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token_file:
            token_file.write(creds.to_json())

    return creds