"""
Simple backup utilities for the central SQLite DB.

Provides minimal functions used by the app UI:
- `quick_backup()`: copy the active SQLite DB to backups/ and return path
- `list_backups()`: list files in backups/ with metadata
- `delete_backup(path)`: delete a backup file
- `import_db_file(path)`: replace current DB with provided .db (creates pre-restore copy)

This module is intentionally small and avoids earlier complex/duplicated logic.
"""

import os
import shutil
from datetime import datetime
from typing import List, Dict
from db import SQLITE_PATH

BACKUP_FOLDER = os.path.join(os.path.dirname(__file__), 'backups')
os.makedirs(BACKUP_FOLDER, exist_ok=True)


def get_backup_folder() -> str:
    return BACKUP_FOLDER


def quick_backup() -> str:
    """Copy the active SQLite DB to backups/ and return the new path."""
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        raise FileNotFoundError(f"Database file not found: {SQLITE_PATH}")

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    dest = os.path.join(BACKUP_FOLDER, f'caloria_backup_{timestamp}.db')
    shutil.copy2(SQLITE_PATH, dest)
    return dest


def list_backups() -> List[Dict]:
    out: List[Dict] = []
    for fname in sorted(os.listdir(BACKUP_FOLDER), reverse=True):
        path = os.path.join(BACKUP_FOLDER, fname)
        try:
            stat = os.stat(path)
            out.append({
                'filename': fname,
                'filepath': path,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'created': datetime.fromtimestamp(stat.st_ctime)
            })
        except Exception:
            continue
    return out


def delete_backup(filepath: str) -> bool:
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
    except Exception:
        pass
    return False


def import_db_file(db_path: str, make_prebackup: bool = True) -> Dict[str, str]:
    """Replace the active DB with `db_path`. Creates a pre-restore backup if requested."""
    if not db_path or not os.path.exists(db_path):
        raise FileNotFoundError(f"Provided DB path not found: {db_path}")

    pre = None
    if make_prebackup and os.path.exists(SQLITE_PATH):
        pre = os.path.join(BACKUP_FOLDER, f'pre_restore_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        shutil.copy2(SQLITE_PATH, pre)

    shutil.copy2(db_path, SQLITE_PATH)
    return {'restored': True, 'backup_before_restore': pre or '', 'restored_to': SQLITE_PATH}
