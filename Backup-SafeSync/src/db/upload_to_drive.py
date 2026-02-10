import os
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from src.db.drive_auth import get_drive_credentials

def upload_file_to_drive(file_path,user_email, parent_folder_id=None):
    """
    Uploads a single file to Google Drive with error handling.
    """
    from googleapiclient.errors import HttpError
    from google.auth.exceptions import RefreshError
    import traceback

    creds = get_drive_credentials(user_email)

    try:
        service = build('drive', 'v3', credentials=creds)

        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [parent_folder_id] if parent_folder_id else []
        }

        media = MediaFileUpload(file_path, resumable=True)
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name'
        ).execute()

        print(f" Uploaded file: {uploaded_file.get('name')} (ID: {uploaded_file.get('id')})")
        return uploaded_file.get('id')

    except HttpError as e:
        print(" Google Drive API error:")
        print(f"   Status code: {e.status_code}")
        print(f"   Reason: {e.error_details if hasattr(e, 'error_details') else e}")
        print("   This usually means your credentials or permissions are incorrect.")

    except RefreshError:
        print(" Token refresh failed. Your credentials might be expired or invalid.")
        print("   Try deleting 'user_data/token.json' and re-running to reauthenticate.")

    except Exception as e:
        print(" Unexpected error during upload:")
        print(traceback.format_exc())

    return None
def upload_folder_to_drive(folder_path,user_email, parent_folder_id=None):
    """
    Uploads a folder recursively to Google Drive with error handling.
    Continues uploading even if some files fail.
    """
    from googleapiclient.errors import HttpError
    import traceback

    creds = get_drive_credentials(user_email)

    try:
        service = build('drive', 'v3', credentials=creds)

        folder_metadata = {
            'name': os.path.basename(folder_path),
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id] if parent_folder_id else []
        }
        folder = service.files().create(
            body=folder_metadata,
            fields='id, name'
        ).execute()

        folder_id = folder.get('id')
        print(f" Created folder on Drive: {folder.get('name')} (ID: {folder_id})")

        for item in os.listdir(folder_path):
            item_path = os.path.join(folder_path, item)

            try:
                if os.path.isfile(item_path):
                    print(f"⬆ Uploading file: {item}")
                    upload_file_to_drive(item_path, parent_folder_id=folder_id)
                elif os.path.isdir(item_path):
                    print(f" Entering subfolder: {item}")
                    upload_folder_to_drive(item_path, parent_folder_id=folder_id)

            except HttpError as e:
                print(f" Failed to upload {item}: {e}")
            except Exception as e:
                print(f" Unexpected error with {item}: {traceback.format_exc()}")

        return folder_id

    except HttpError as e:
        print(" Error creating main folder on Drive:")
        print(e)
    except Exception as e:
        print(" Unexpected error creating folder:")
        print(traceback.format_exc())

    return None



def upload_to_drive(file_path, user_email,parent_folder_id=None):
    """
    Uploads a single file to Google Drive.
    """
    creds = get_drive_credentials(user_email)
    service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': os.path.basename(file_path)}
    if parent_folder_id:
        file_metadata['parents'] = [parent_folder_id]

    media = MediaFileUpload(file_path, resumable=True)
    uploaded_file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"Uploaded file ID: {uploaded_file.get('id')}")
    return uploaded_file.get('id')

def authenticate_drive():
    """Force user login to Google Drive"""
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    import os

    SCOPES = ['https://www.googleapis.com/auth/drive']

    base_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.path.normpath(os.path.join(base_dir, "../../user_data/credentials.json"))
    token_path = os.path.normpath(os.path.join(base_dir, "../../user_data/token.json"))

    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(token_path, 'w') as token:
        token.write(creds.to_json())

    service = build('drive', 'v3', credentials=creds)
    return service

def delete_drive_file(file_id, creds):
    try:
        service = build("drive", "v3", credentials=creds)
        service.files().delete(fileId=file_id).execute()
        print(f"[Drive] Deleted file from Google Drive: {file_id}")
        return True
    except Exception as e:
        print(f"[Drive] Error deleting file: {e}")
        return False