#!/usr/bin/env python3
"""Atomic file writes with optional backup."""
import os, json, tempfile, hashlib
from pathlib import Path

def atomic_write(path: Path, data: str, backup: bool = True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # backup
    if backup and path.exists():
        try:
            bk = path.with_suffix(path.suffix + ".bak")
            bk.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except: pass
    # write temp then replace
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".tmp.")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(data)
            f.flush()
            try: os.fsync(f.fileno())
            except: pass
        os.replace(tmp, str(path))
    except:
        try: os.unlink(tmp)
        except: pass
        raise

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
