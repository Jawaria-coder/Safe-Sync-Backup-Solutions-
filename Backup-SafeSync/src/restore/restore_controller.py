import os
import json
from getpass import getpass
from src.backup.encryption import decrypt_file
from src.restore.restore_service import restore_backup


def restore_controller(backup_metadata_path: str, restore_destination: str):
    """
    Controls the restore process:
    - Reads backup metadata (contains salt, iv, encrypted file path)
    - Restores and decrypts files to destination folder
    """

    if not os.path.exists(backup_metadata_path):
        print("[ERROR] Backup metadata file not found:", backup_metadata_path)
        return

    # Load backup metadata (usually stored in a .json)
    with open(backup_metadata_path, "r") as meta_file:
        metadata = json.load(meta_file)

    # Metadata should contain info like:
    # {
    #   "encrypted_files": [
    #       {"path": "backup/encrypted/data.txt.enc", "salt": "...", "iv": "..."}
    #   ]
    # }
    encrypted_files = metadata.get("encrypted_files", [])

    if not encrypted_files:
        print("[INFO] No encrypted files found in metadata.")
        return

    for file_info in encrypted_files:
        enc_path = file_info["path"]
        salt = bytes.fromhex(file_info["salt"])
        iv = bytes.fromhex(file_info["iv"])

        print(f"\n[INFO] Restoring file: {enc_path}")

        # Step 1: Restore file from backup to tmp location
        restored_path = restore_backup(enc_path, restore_destination)

        # Step 2: Ask password for decryption
        password_attempt = getpass("Enter password for decryption: ")

        try:
            # Decrypt restored file using provided password
            key_check_path = decrypt_file(restored_path, salt, iv)
            print(f"[SUCCESS] File restored and decrypted to: {key_check_path}")
        except ValueError:
            print("[ERROR] Incorrect password or corrupted file. Skipping this file.")
        except Exception as e:
            print(f"[ERROR] Failed to decrypt file {enc_path}: {e}")
