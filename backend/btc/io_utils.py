"""Shared I/O utilities for atomic file writes across all BTC trading modules."""

import os
import json
import time
import tempfile


def atomic_json_write(filepath: str, data, indent: int = 2):
    """Write JSON atomically: write to a temp file, then os.replace() into place.
    Falls back to a direct write if os.replace() is blocked (e.g. Windows file locks)."""
    dir_name = os.path.dirname(filepath)
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent)
        try:
            os.replace(tmp_path, filepath)
        except PermissionError:
            # On Windows, antivirus or open file handles can briefly block replace
            time.sleep(0.05)
            try:
                os.replace(tmp_path, filepath)
            except Exception:
                with open(filepath, "w", encoding="utf-8") as fallback_f:
                    json.dump(data, fallback_f, indent=indent)
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
    except Exception:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise
