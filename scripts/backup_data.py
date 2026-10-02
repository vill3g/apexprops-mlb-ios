"""
Daily backup of the Kalshi AI Trader's private data.

Creates backups/kalshi_backup_YYYY-MM-DD_HHMM.zip in the project folder containing:
  * every SQLite database in backend/data (copied with SQLite's online-backup API,
    so it is consistent even while the server and worker are running);
  * user folders, profile pictures, trade histories and config JSON in backend/data;
  * .env (holds SAAS_ENCRYPTION_KEY - without it the stored Kalshi API keys cannot be
    decrypted, so it must be backed up together with users.db).

Keeps the newest 14 backups. The backups folder is git-ignored; it contains secrets,
so copy it only to storage you trust (e.g. an encrypted drive).

Usage:  .venv\\Scripts\\python.exe scripts\\backup_data.py [--keep 14]
"""
import argparse
import glob
import os
import sqlite3
import sys
import tempfile
import zipfile
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "backend", "data")
BACKUP_DIR = os.path.join(ROOT, "backups")

SKIP_DIRS = {"__pycache__", "model_cache", "locks"}
SKIP_EXT = {".py", ".pyc", ".csv", ".db", ".db-wal", ".db-shm"}  # .db files are added via the backup API


def _sqlite_copy(src: str, dst: str) -> None:
    source = sqlite3.connect(src, timeout=30)
    try:
        dest = sqlite3.connect(dst)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()


def _skip(path: str) -> bool:
    name = os.path.basename(path)
    if name.endswith("-wal") or name.endswith("-shm"):
        return True
    return os.path.splitext(name)[1].lower() in SKIP_EXT


def make_backup(keep: int) -> str:
    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = os.path.join(BACKUP_DIR, f"kalshi_backup_{stamp}.zip")
    tmp_zip = out_path + ".partial"

    with tempfile.TemporaryDirectory() as tmp, zipfile.ZipFile(tmp_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Databases, consistently
        for db in sorted(glob.glob(os.path.join(DATA_DIR, "*.db"))):
            copy = os.path.join(tmp, os.path.basename(db))
            _sqlite_copy(db, copy)
            zf.write(copy, os.path.join("backend", "data", os.path.basename(db)))

        # 2. Everything else in backend/data that is runtime data (not code or caches)
        for dirpath, dirnames, filenames in os.walk(DATA_DIR):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                if _skip(full):
                    continue
                zf.write(full, os.path.relpath(full, ROOT))

        # 3. Secrets needed to use the data
        env_path = os.path.join(ROOT, ".env")
        if os.path.exists(env_path):
            zf.write(env_path, ".env")

    os.replace(tmp_zip, out_path)

    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "kalshi_backup_*.zip")))
    for old in backups[:-keep] if keep > 0 else []:
        try:
            os.remove(old)
        except OSError:
            pass
    return out_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", type=int, default=14, help="number of backups to keep")
    args = ap.parse_args()
    try:
        path = make_backup(args.keep)
    except Exception as e:  # noqa: BLE001 - report any failure to the scheduler log
        print(f"[backup] FAILED: {e}", file=sys.stderr)
        return 1
    size_mb = os.path.getsize(path) / 1e6
    print(f"[backup] OK: {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
