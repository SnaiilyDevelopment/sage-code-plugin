#!/usr/bin/env python3
"""Atomic file writes with optional backup."""
import os, json, tempfile, hashlib
from pathlib import Path

def atomic_write(path: Path, data: str, backup: bool = True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        try:
            bk = path.with_suffix(path.suffix + ".bak")
            bk.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except (OSError, UnicodeError): pass
    # lock file for concurrency
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_f = None
    try:
        lock_f = open(lock_path, "w")
        try:
            import msvcrt
            msvcrt.locking(lock_f.fileno(), msvcrt.LK_LOCK, 1)
        except (ImportError, OSError):
            try:
                import fcntl
                fcntl.flock(lock_f, fcntl.LOCK_EX)
            except (ImportError, OSError): pass
    except (OSError, IOError): pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".tmp.")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(data)
            f.flush()
            try: os.fsync(f.fileno())
            except (OSError, AttributeError): pass
        os.replace(tmp, str(path))
    except (OSError, IOError):
        try: os.unlink(tmp)
        except (OSError, FileNotFoundError): pass
        raise
    finally:
        if lock_f:
            try:
                try:
                    import msvcrt
                    msvcrt.locking(lock_f.fileno(), msvcrt.LK_UNLCK, 1)
                except (ImportError, OSError):
                    try:
                        import fcntl
                        fcntl.flock(lock_f, fcntl.LOCK_UN)
                    except (ImportError, OSError): pass
                lock_f.close()
            except (OSError, IOError): pass

def atomic_write_json(path: Path, obj: dict, backup: bool = True):
    atomic_write(path, json.dumps(obj, indent=2), backup=backup)

def load_json_with_status(path: Path):
    """Returns (data, status) where status in OK, MISSING, CORRUPTED"""
    if not path.exists():
        return None, "MISSING"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "OK"
    except Exception as e:
        return None, "CORRUPTED"
