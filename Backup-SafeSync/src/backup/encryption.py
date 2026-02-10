from cryptography.fernet import Fernet
import os
import sys
import uuid
import hashlib
import base64
import platform

# -------------------------
# Helper to get correct path in dev and PyInstaller exe
# -------------------------
def resource_path(relative_path):
    """Get absolute path to resource, works in dev and PyInstaller exe."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# -------------------------
# Writable folder to store key and other files
# -------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WRITABLE_FOLDER = os.path.join(PROJECT_ROOT, "database")
os.makedirs(WRITABLE_FOLDER, exist_ok=True)
KEY_FILE = os.path.join(WRITABLE_FOLDER, "encryption.key")

# -------------------------
# Machine identifier (improved stability)
# -------------------------
def get_machine_identifier():
    # MAC address
    mac = uuid.getnode()
    mac_bytes = mac.to_bytes(8, byteorder="big", signed=False)

    # CPU/Chip info
    cpu_info = platform.processor() or "defaultcpu"
    cpu_bytes = cpu_info.encode("utf-8")

    # Include OS name
    system_info = platform.system().encode("utf-8")

    # Combine all
    raw = mac_bytes + cpu_bytes + system_info

    # Hash to 32 bytes
    digest = hashlib.sha256(raw).digest()

    # URL-safe for Fernet
    return base64.urlsafe_b64encode(digest)

def get_machine_fernet():
    return Fernet(get_machine_identifier())

# -------------------------
# Generate key (run once)
# -------------------------
def generate_key():
    if os.path.exists(KEY_FILE):
        return  # Key already exists

    # Generate master Fernet key
    master_key = Fernet.generate_key()

    # Encrypt master key with machine Fernet
    machine_fernet = get_machine_fernet()
    encrypted_master = machine_fernet.encrypt(master_key)

    # Save encrypted key
    with open(KEY_FILE, "wb") as f:
        f.write(encrypted_master)

    print("Machine-bound encryption key generated and saved.")

# -------------------------
# Load existing key (auto-generate if missing)
# -------------------------
def load_key():
    if not os.path.exists(KEY_FILE):
        # Automatically generate key on first run
        generate_key()

    with open(KEY_FILE, "rb") as f:
        encrypted_master = f.read()

    machine_fernet = get_machine_fernet()
    try:
        master_key = machine_fernet.decrypt(encrypted_master)
    except Exception as e:
        raise ValueError(
            "Failed to decrypt key: machine mismatch or key corrupted."
        ) from e

    return master_key

# -------------------------
# Encrypt a file
# -------------------------
def encrypt_file(file_path):
    key = load_key()
    fernet = Fernet(key)
    with open(file_path, "rb") as f:
        original = f.read()
    encrypted = fernet.encrypt(original)
    enc_file_path = file_path + ".enc"
    with open(enc_file_path, "wb") as f:
        f.write(encrypted)
    return enc_file_path

# -------------------------
# Decrypt a file
# -------------------------
def decrypt_file(enc_file_path):
    key = load_key()
    fernet = Fernet(key)
    with open(enc_file_path, "rb") as f:
        encrypted = f.read()
    decrypted = fernet.decrypt(encrypted)
    if enc_file_path.endswith(".enc"):
        new_file_path = enc_file_path[:-4]
    else:
        new_file_path = enc_file_path + "_decrypted"
    with open(new_file_path, "wb") as f:
        f.write(decrypted)
    return new_file_path

# -------------------------
# Test run
# -------------------------
if __name__ == "__main__":
    # Generates key automatically if missing
    master_key = load_key()
    print("Decrypted master key (Fernet):", master_key.decode())

    test_file = "test.txt"
    if os.path.exists(test_file):
        enc_path = encrypt_file(test_file)
        print("Encrypted file:", enc_path)
        dec_path = decrypt_file(enc_path)
        print("Decrypted file:", dec_path)
    else:
        print("Create a 'test.txt' file in this folder to test encryption/decryption.")
