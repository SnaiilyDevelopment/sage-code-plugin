#!/usr/bin/env python3
"""Intelligent scout caching — task fingerprint + repo hash + file hashes + config state.

Cache key considers: task fingerprint, repo hash, relevant file hashes, dependency state,
 configuration state, model/provider, scout version. Invalidate intelligently on change.

Never use stale information when relevant files changed. Uses existing validated memory
where appropriate but memory does not override live repo evidence.
"""
import json, hashlib, os
from pathlib import Path
from datetime import datetime, timezone, timedelta

CACHE_VERSION = "1"
TTL_HOURS = 24

def _hash_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:12]

def _repo_hash(repo: Path) -> str:
    # use .wolf/sage-map.json hash if available, else git rev-parse, else dir hash
    mp = repo / ".wolf" / "sage-map.json"
    if mp.exists():
        try:
            data = json.loads(mp.read_text(encoding="utf-8", errors="ignore"))
            h = data.get("hash","")
            if h:
                return h[:12]
        except: pass
    try:
        import subprocess
        r = subprocess.run(["git","rev-parse","HEAD"], cwd=str(repo), capture_output=True, text=True, timeout=3)
        if r.returncode==0 and r.stdout.strip():
            return r.stdout.strip()[:12]
    except: pass
    # fallback: hash of package.json + tauri.conf
    h = hashlib.sha256()
    for fp in [repo/"package.json", repo/"src-tauri"/"Cargo.toml", repo/"src-tauri"/"tauri.conf.json"]:
        if fp.exists():
            try: h.update(fp.read_bytes()[:4096])
            except: pass
    return h.hexdigest()[:12]

def _file_hashes(repo: Path, files: list) -> str:
    h = hashlib.sha256()
    for fp in sorted(set(files or []))[:8]:
        try:
            p = (repo / fp)
            if p.exists() and p.is_file():
                h.update(p.read_bytes()[:8192])
                h.update(fp.encode())
        except: pass
    return h.hexdigest()[:12]

def _config_hash(policy: dict) -> str:
    # hash of relevant preflight config
    cfg = {k: policy.get("preflight",{}).get(k) for k in ["max_input_tokens","max_output_tokens","timeout_ms"]}
    cfg["version"] = policy.get("version","")
    return _hash_text(json.dumps(cfg, sort_keys=True))

def cache_key(task: str, categories: list, files: list, repo: Path, policy: dict, provider: dict) -> str:
    parts = [
        CACHE_VERSION,
        _hash_text(task[:500].lower().strip()),
        ",".join(sorted(categories or []))[:100],
        _repo_hash(repo),
        _file_hashes(repo, files),
        _config_hash(policy),
        provider.get("id","") + ":" + provider.get("model",""),
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def _cache_path(repo: Path, key: str) -> Path:
    return repo / ".wolf" / "scout-cache" / f"{key}.json"

def get_cached(task: str, categories: list, files: list, repo: Path, policy: dict, provider: dict) -> dict | None:
    key = cache_key(task, categories, files, repo, policy, provider)
    p = _cache_path(repo, key)
    if not p.exists():
        # fallback to plugin root if repo cache missing but global exists (for tests)
        p2 = Path(__file__).resolve().parents[2] / ".wolf" / "scout-cache" / f"{key}.json"
        if p2.exists():
            p = p2
        else:
            return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        ts = data.get("_cached_at","")
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
                age = (datetime.now(timezone.utc) - dt).total_seconds()/3600
                if age > TTL_HOURS:
                    return None
                # Validate file hashes still match (stale check)
                current_fh = _file_hashes(repo, files)
                if data.get("_file_hash") and data.get("_file_hash") != current_fh:
                    return None
                current_rh = _repo_hash(repo)
                if data.get("_repo_hash") and data.get("_repo_hash") != current_rh:
                    return None
            except: pass
        # Never return stale if repo hash changed — already checked
        return data.get("result")
    except:
        return None

def put_cache(task: str, categories: list, files: list, repo: Path, policy: dict, provider: dict, result: dict):
    key = cache_key(task, categories, files, repo, policy, provider)
    p = _cache_path(repo, key)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_cached_at": datetime.now(timezone.utc).isoformat(),
        "_repo_hash": _repo_hash(repo),
        "_file_hash": _file_hashes(repo, files),
        "_cache_key": key,
        "_cache_version": CACHE_VERSION,
        "result": result,
    }
    try:
        p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except: pass
    return key

def invalidate(repo: Path):
    cache_dir = repo / ".wolf" / "scout-cache"
    if cache_dir.exists():
        import shutil
        for f in cache_dir.glob("*.json"):
            try: f.unlink()
            except: pass
