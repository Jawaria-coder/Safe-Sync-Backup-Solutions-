# SafeSync – Secure Backup & Restore Tool

SafeSync App

**Live Demo / Landing Page:** [SafeSync Landing Page](https://safe-sync-backup-solutions.vercel.app/)  
**Download for Windows:** [SafeSync v1.0](https://github.com/Jawaria-coder/Safe-Sync-Backup-Solutions-/releases/download/v1.0/SafeSync.zip)

---

## Overview

SafeSync is a secure desktop application for **Windows** that helps users **backup, restore, and sync their files effortlessly**. It uses **AES encryption** to protect your data and supports **cloud/drive backup and scheduled restores**, ensuring your files are always safe and accessible.

---

## Features

**Backup & Restore**
- Automatic backup of important files
- One-click restore of deleted or lost files
- Schedule your backups to run automatically at set times
- Support for local and cloud/drive backups

**Sync Across Devices**
- Keep files synchronized across multiple Windows machines
- Seamless transitions between home and work PCs

**Security**
- AES encryption for all backed-up files
- Only you can access your backups
- No unencrypted cloud storage

**User-Friendly**
- Clean and intuitive interface
- Notifications for backup and restore status
- Minimal system resource usage

---

## Installation

**Option 1: Install Executable (Windows Only)**
1. Download the latest `SafeSync.zip` from [GitHub Releases](https://github.com/Jawaria-coder/Safe-Sync-Backup-Solutions-/releases/download/v1.0/SafeSync.zip)
2. Extract the contents to a folder
3. Run `SafeSync.exe`
4. Follow the instructions in the app to set up backup locations, cloud drives, and schedules

> ⚠️ Windows may show a security warning for unsigned apps. Click **More Info → Run Anyway**.

**Option 2: Run from Source**
1. Clone the repository:
   `git clone https://github.com/Backup-solution/BackUp-Solution.git`
3. Navigate to the project folder:
   `cd Backup-Solution`
5. Install dependencies (if using Python):
   `pip install -r requirements.txt`
7. Run the app:
   `python main.py`

---

## Project Structure

- `dist/` – PyInstaller output (ignored in Git)  
- `build/` – PyInstaller build files (ignored)  
- `database/` – Database files  
- `src/` – Source code  
- `scripts/` – Helper scripts  
- `user_data/` – User-specific data  
- `tmp_restored/` – Temporary restored files  
- `drive/` – Drive/cloud sync logic  
- `SafeSync.spec` – PyInstaller spec file  
- `SafeSync-UserGuide.pdf` – User guide  
- `README.md` – This file

---

## Technologies Used

- Python  
- PyInstaller (for building Windows executable)  
- Plyer (notifications)  
- Tkinter / Custom GUI  
- AES Encryption  
- Google Drive / Cloud APIs

---

## License

Open-source and free to use for personal or educational purposes.
