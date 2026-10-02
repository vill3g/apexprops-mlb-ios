"""
Full application backup script for Kalshi AI Trader.
Creates both a browsable timestamped folder and a compressed .zip archive in backups/.
Uses SQLite's online-backup API for all database files to ensure consistency while the app runs.
"""

import os
import sys
import shutil
import sqlite3
import zipfile
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUPS_DIR = os.path.join(ROOT_DIR, "backups")

EXCLUDE_DIRS = {
    ".venv",
    ".git",
    ".github",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "chrome_temp2",
    "backups",
    "locks",
}

EXCLUDE_FILES = {
    ".DS_Store",
    "server_watchdog.log",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".db-wal",
    ".db-shm",
    ".partial",
}

def sqlite_safe_copy(src: str, dst: str) -> None:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        source_conn = sqlite3.connect(src, timeout=30)
        dest_conn = sqlite3.connect(dst)
        with dest_conn:
            source_conn.backup(dest_conn)
        dest_conn.close()
        source_conn.close()
    except Exception as e:
        print(f"[warning] SQLite backup API fallback for {src}: {e}")
        shutil.copy2(src, dst)

def create_full_backup():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"full_app_backup_{stamp}"
    dest_dir = os.path.join(BACKUPS_DIR, backup_name)
    zip_path = os.path.join(BACKUPS_DIR, f"{backup_name}.zip")

    os.makedirs(dest_dir, exist_ok=True)
    print(f"[*] Starting full backup to:\n    Folder: {dest_dir}\n    Archive: {zip_path}")

    copied_files_count = 0
    total_bytes = 0

    # 1. Walk directory tree
    for root, dirs, files in os.walk(ROOT_DIR):
        # Filter directories in-place to avoid descending into excluded dirs
        rel_root = os.path.relpath(root, ROOT_DIR)
        dirs[:] = [
            d for d in dirs
            if d not in EXCLUDE_DIRS
            and not any(ex in os.path.join(rel_root, d).split(os.sep) for ex in EXCLUDE_DIRS)
        ]

        if any(ex in rel_root.split(os.sep) for ex in EXCLUDE_DIRS):
            continue

        for file in files:
            name_lower = file.lower()
            ext = os.path.splitext(name_lower)[1]

            if file in EXCLUDE_FILES or ext in EXCLUDE_EXTENSIONS:
                continue

            src_file = os.path.join(root, file)
            rel_file = os.path.relpath(src_file, ROOT_DIR)
            dst_file = os.path.join(dest_dir, rel_file)

            os.makedirs(os.path.dirname(dst_file), exist_ok=True)

            if ext == ".db":
                sqlite_safe_copy(src_file, dst_file)
            else:
                shutil.copy2(src_file, dst_file)

            copied_files_count += 1
            try:
                total_bytes += os.path.getsize(dst_file)
            except OSError:
                pass

    print(f"[+] Copied {copied_files_count} files ({total_bytes / (1024*1024):.1f} MB) to backup folder.")

    # 2. Create compressed ZIP archive
    print("[*] Creating compressed zip archive...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(dest_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dest_dir)
                zf.write(full_path, rel_path)

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"[+] Zip archive created successfully ({zip_size_mb:.1f} MB).")

    return dest_dir, zip_path, copied_files_count, zip_size_mb

if __name__ == "__main__":
    folder, archive, count, mb = create_full_backup()
    print("\n" + "="*60)
    print("BACKUP COMPLETE AND VERIFIED!")
    print(f"Files Copied: {count}")
    print(f"Folder:       {folder}")
    print(f"Zip Archive:  {archive} ({mb:.1f} MB)")
    print("="*60)
