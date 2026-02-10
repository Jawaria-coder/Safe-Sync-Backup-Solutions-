import sys
import os

def resource_path(relative_path):
    """Get absolute path to resource for PyInstaller and development."""
    try:
        base_path = sys._MEIPASS  # PyInstaller temporary folder
    except AttributeError:
        base_path = os.path.abspath(".")  # project root (main.py working directory)

    return os.path.join(base_path, relative_path)


def get_db_path():
    """Return correct path to backup.db"""
    return resource_path("database/backup.db")
