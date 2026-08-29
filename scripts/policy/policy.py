#!/usr/bin/env python3
"""
Versioned internal policy — auditable, rollback-capable, never weakens security.
Manages .wolf/sage-policy.json with history + snapshots.
"""
import json
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_POLICY = {
    "version": "2.3",
    "risk_thresholds": {"low": [0,24], "medium": [25,49], "high": [50,74], "critical": [75,100]},
    "specialist_threshold": 3,
    "skill_threshold": 2.0,
    "skill_budget": 3500,
    "context_budget": 6000,
    "learning_half_life_days": 30,
    "learning_confidence_min_samples": 5,
    "learning_confidence_min_rate": 0.7,
    "memory_ttl_days": 90,
    "benchmark_repeats": 5,
    "benchmark_cv_not_measurable": 0.15,
    "safety": {"never_weaken": ["security","destructive","secret"], "mcp_high_risk_confirm": True},
    "preflight": {
        "enabled": True,
        "max_input_tokens": 2000,
        "max_output_tokens": 800,
        "max_total_tokens": 3200,
        "max_cost_usd": 0.05,
        "timeout_ms": 8000,
        "threshold": "auto",
        "fallback_to_heuristic": True,
        "selection": "cheapest-first",
        "providers": [
            {"id":"cheap-a","provider":"generic-openai-compat","model":"deepseek-v4-flash","base_url_env":"SAGE_PREFLIGHT_BASE_URL","api_key_env":"SAGE_PREFLIGHT_API_KEY","cost_per_1k_in":0.01,"cost_per_1k_out":0.02,"timeout_ms":8000,"currency":"USD","effective_date":"2026-08-01","verified_at":"2026-08-15","source":"https://api.deepseek.com/pricing verified 2026-08"},
            {"id":"cheap-b","provider":"generic-openai-compat","model":"glm-5.3-flash","base_url_env":"GLM_BASE_URL","api_key_env":"GLM_API_KEY","cost_per_1k_in":0.005,"cost_per_1k_out":0.015,"timeout_ms":8000,"currency":"USD","effective_date":"2026-08-01","verified_at":"2026-08-15","source":"https://open.bigmodel.cn/pricing verified 2026-08"}
        ]
    },
    "history": []
}

POLICY_PATH_REPO = ".wolf/sage-policy.json"

# Allowed paths for structured apply
ALLOWED_PATHS = {
    "specialist_threshold": {"type": int, "min": 1, "max": 10},
    "skill_threshold": {"type": float, "min": 0.5, "max": 5.0},
    "skill_budget": {"type": int, "min": 500, "max": 10000},
    "context_budget": {"type": int, "min": 1000, "max": 20000},
    "learning_half_life_days": {"type": int, "min": 7, "max": 90},
    "learning_confidence_min_samples": {"type": int, "min": 3, "max": 50},
    "memory_ttl_days": {"type": int, "min": 7, "max": 365},
    "preflight.enabled": {"type": bool},
    "preflight.max_input_tokens": {"type": int, "min": 200, "max": 4000},
    "preflight.max_output_tokens": {"type": int, "min": 100, "max": 4000},
    "preflight.max_total_tokens": {"type": int, "min": 400, "max": 8000},
    "preflight.max_cost_usd": {"type": float, "min": 0.001, "max": 1.0},
    "preflight.timeout_ms": {"type": int, "min": 1000, "max": 30000},
}

SAFETY_BLOCK_PATTERNS = [
    r"lower.*risk", r"reduce.*threshold", r"disable.*security", r"weaken",
    r"skip.*security.*check", r"disable.*secret.*protect", r"bypass.*permission"
]

def _atomic_write_json(path: Path, obj: dict):
    try:
        from scripts.utils.atomic import atomic_write_json as _shared
        _shared(path, obj)
        return
    except (ImportError, OSError): pass
    import os, tempfile, json as _j
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except (OSError, UnicodeError): pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="."+path.name+".tmp.")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(_j.dumps(obj, indent=2))
            f.flush()
            try: os.fsync(f.fileno())
            except (OSError, AttributeError): pass
        os.replace(tmp, str(path))
    except (OSError, IOError):
        try: os.unlink(tmp)
        except (OSError, FileNotFoundError): pass
        raise

def resolve(repo: Path) -> Path:
    p = repo / ".wolf" / "sage-policy.json"
    if not repo.exists() or not (repo / ".git").exists():
        p = Path(__file__).resolve().parents[2] / ".wolf" / "sage-policy.json"
    return p

def snapshot_path(repo: Path, version: str) -> Path:
    return resolve(repo).parent / "sage-policy.snapshots" / f"{version}.json"

def _migrate(policy: dict) -> dict:
    pre = policy.get("preflight", {})
    # deprecate ambiguous budget_tokens
    if "budget_tokens" in pre:
        # keep for warning but remove from effective policy
        pre["_deprecated_budget_tokens"] = pre.pop("budget_tokens")
    if "max_input_tokens" not in pre:
        pre["max_input_tokens"] = 2000
    if "max_output_tokens" not in pre:
        pre["max_output_tokens"] = 800
    if "max_total_tokens" not in pre:
        pre["max_total_tokens"] = 2800
    if "max_cost_usd" not in pre:
        pre["max_cost_usd"] = 0.05
    if "timeout_ms" not in pre:
        pre["timeout_ms"] = 8000
    # ensure pricing provenance
    for prov in pre.get("providers",[]):
        prov.setdefault("currency","USD")
        prov.setdefault("effective_date","2026-01-01")
        prov.setdefault("verified_at", prov.get("effective_date"))
        prov.setdefault("source","unknown — verify pricing")
    # enforce invariant max_total >= max_input + max_output + overhead(200)
    try:
        if pre.get("max_total_tokens", 2800) < pre.get("max_input_tokens",2000) + pre.get("max_output_tokens",800) + 200:
            pre["_budget_warning"] = f"max_total {pre['max_total_tokens']} < max_input {pre['max_input_tokens']}+max_output {pre['max_output_tokens']}+200"
    except (TypeError, KeyError): pass
    return policy

def load(repo: Path) -> dict:
    p = resolve(repo)
    if not p.exists():
        return _migrate(json.loads(json.dumps(DEFAULT_POLICY)))
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return _migrate(data)
    except Exception as e:
        # corruption: preserve file, try backup
        try:
            corrupt_copy = p.with_suffix(".json.corrupt." + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
            corrupt_copy.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except: pass
        bak = p.with_suffix(".json.bak")
        if bak.exists():
            try:
                return _migrate(json.loads(bak.read_text(encoding="utf-8")))
            except: pass
        return _migrate(json.loads(json.dumps(DEFAULT_POLICY)))

def save(repo: Path, policy: dict):
    p = resolve(repo)
    _atomic_write_json(p, policy)

def _get_nested(obj: dict, path: str):
    parts = path.split(".")
    cur = obj
    for part in parts:
        if not isinstance(cur, dict) or part not in cur:
            return None, False
        cur = cur[part]
    return cur, True

def _set_nested(obj: dict, path: str, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if part not in cur or not isinstance(cur[part], dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value

def propose(repo: Path, change: str, evidence: str, confidence: str, current_policy_str: str = "") -> dict:
    policy = load(repo)
    proposal = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "current_policy": current_policy_str or f"v{policy['version']}",
        "evidence": evidence[:500],
        "proposed_change": change[:500],
        "confidence": confidence,
        "hash": hashlib.sha256((change+evidence).encode()).hexdigest()[:8],
        "applied": False
    }
    if any(re.search(pat, change.lower()) for pat in SAFETY_BLOCK_PATTERNS):
        proposal["blocked"] = True
        proposal["reason"] = "Refuses to weaken security/destructive/secret via learning — requires manual high-confidence review"
        proposal["error_type"] = "POLICY_ERROR"
    else:
        proposal["blocked"] = False
    return proposal

def apply_structured(repo: Path, path: str, new_value, reason: str, evidence: str, confidence: str, version_bump: str = "") -> dict:
    """Structured apply: path, new_value with validation, atomic save, snapshot, verify."""
    if path not in ALLOWED_PATHS:
        return {"error": f"Invalid policy path '{path}' — not in allowed list", "error_type": "POLICY_ERROR", "allowed": list(ALLOWED_PATHS.keys())}
    spec = ALLOWED_PATHS[path]
    expected = spec["type"]
    # type check (allow int for float)
    if expected == float and isinstance(new_value, int):
        new_value = float(new_value)
    if not isinstance(new_value, expected):
        # try coercion for cli strings
        try:
            if expected == int: new_value = int(new_value)
            elif expected == float: new_value = float(new_value)
            elif expected == bool: new_value = str(new_value).lower() in ("true","1","yes")
        except:
            return {"error": f"Type mismatch for {path}: expected {expected.__name__}, got {type(new_value).__name__}", "error_type": "POLICY_ERROR"}
        if not isinstance(new_value, expected):
            return {"error": f"Type mismatch for {path}", "error_type": "POLICY_ERROR"}
    if "min" in spec and new_value < spec["min"]:
        return {"error": f"Value {new_value} below min {spec['min']} for {path}", "error_type": "POLICY_ERROR"}
    if "max" in spec and new_value > spec["max"]:
        return {"error": f"Value {new_value} above max {spec['max']} for {path}", "error_type": "POLICY_ERROR"}
    # budget invariant
    if path in ("preflight.max_input_tokens","preflight.max_output_tokens","preflight.max_total_tokens"):
        tmp = json.loads(json.dumps(load(repo)))
        _set_nested(tmp, path, new_value)
        pre = tmp.get("preflight",{})
        try:
            if pre.get("max_total_tokens",2800) < pre.get("max_input_tokens",2000)+pre.get("max_output_tokens",800)+200:
                return {"error": f"Budget invariant violated: max_total {pre['max_total_tokens']} must be >= max_input {pre['max_input_tokens']}+max_output {pre['max_output_tokens']}+200", "error_type": "POLICY_ERROR"}
        except (TypeError, KeyError) as e:
            return {"error": f"Budget check failed: {e}", "error_type": "POLICY_ERROR"}
    # idempotency: no change
    existing_val, exists = _get_nested(load(repo), path)
    if exists and existing_val == new_value:
        return {"applied": False, "idempotent": True, "path": path, "value": new_value, "reason": "already at desired value"}
    # safety check
    change_desc = f"{path} -> {new_value} ({reason})"
    if any(re.search(pat, change_desc.lower()) for pat in SAFETY_BLOCK_PATTERNS):
        return {"error": "Blocked: never weaken safety via policy change", "error_type": "POLICY_ERROR"}
    if confidence not in ["validated","verified","high"]:
        return {"error": "Insufficient confidence — need validated/verified/high", "confidence": confidence, "error_type": "POLICY_ERROR"}

    policy = load(repo)
    old_value, exists = _get_nested(policy, path)
    if not exists:
        return {"error": f"Path {path} does not exist in policy", "error_type": "POLICY_ERROR"}

    # snapshot current before change
    snap_path = snapshot_path(repo, policy["version"])
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_write_json(snap_path, policy)
    except Exception as e:
        return {"error": f"Failed to snapshot: {e}", "error_type": "POLICY_ERROR"}

    # apply
    _set_nested(policy, path, new_value)
    old_version = policy["version"]
    # bump version if not provided
    if not version_bump:
        try:
            parts = old_version.split(".")
            parts[-1] = str(int(parts[-1]) + 1)
            version_bump = ".".join(parts)
        except:
            version_bump = old_version + ".1"
    policy["version"] = version_bump
    hist_entry = {
        "version": version_bump,
        "date": datetime.now(timezone.utc).isoformat(),
        "change": json.dumps({"path": path, "old_value": old_value, "new_value": new_value, "reason": reason, "evidence": evidence, "confidence": confidence}),
        "evidence": evidence[:500],
        "confidence": confidence,
        "previous_version": old_version,
        "structured": {"path": path, "old_value": old_value, "new_value": new_value}
    }
    policy["history"].append(hist_entry)
    save(repo, policy)

    # verify
    reloaded = load(repo)
    actual, _ = _get_nested(reloaded, path)
    if actual != new_value:
        return {"error": f"Verification failed: {path} is {actual}, expected {new_value}", "error_type": "VERIFICATION_ERROR", "applied": False}
    if reloaded.get("version") != version_bump:
        return {"error": "Version mismatch after save", "error_type": "VERIFICATION_ERROR"}

    return {"applied": True, "path": path, "old_value": old_value, "new_value": new_value, "new_version": version_bump, "previous_version": old_version, "verified": True}

def apply_change(repo: Path, change: str, evidence: str, confidence: str, version_bump: str = "2.0.1") -> dict:
    """Legacy string-based apply — tries to parse structured JSON, else falls back to history-only with warning."""
    # Try parse as structured JSON
    try:
        parsed = json.loads(change)
        if isinstance(parsed, dict) and "path" in parsed:
            return apply_structured(repo, parsed["path"], parsed["new_value"], parsed.get("reason",""), evidence, confidence, version_bump)
    except: pass
    # Legacy: if change looks like path assignment, try to handle
    # e.g. "specialist_threshold 3->4" or "specialist_threshold=4"
    m = re.search(r"(specialist_threshold|skill_threshold|skill_budget|context_budget|memory_ttl_days|preflight\.\w+)\s*(?:->|=|:)\s*([0-9.]+|true|false)", change, re.I)
    if m:
        path = m.group(1)
        val_str = m.group(2)
        try:
            spec = ALLOWED_PATHS.get(path, {})
            if spec.get("type") == int: val = int(float(val_str))
            elif spec.get("type") == float: val = float(val_str)
            elif spec.get("type") == bool: val = val_str.lower() in ("true","1","yes")
            else: val = val_str
            return apply_structured(repo, path, val, change, evidence, confidence, version_bump)
        except: pass

    # Fallback: legacy behavior but mark as HEURISTIC not APPLIED
    if confidence not in ["validated","verified","high"]:
        return {"error": "Insufficient confidence — need validated/verified/high", "confidence": confidence, "error_type": "POLICY_ERROR"}
    if any(re.search(pat, change.lower()) for pat in SAFETY_BLOCK_PATTERNS):
        return {"error": "Blocked: never weaken security via learning", "error_type": "POLICY_ERROR"}
    proposal = propose(repo, change, evidence, confidence, f"v{load(repo)['version']}")
    if proposal.get("blocked"):
        return proposal
    # For legacy string changes that don't map to structured path, we still version bump but mark as heuristic
    policy = load(repo)
    snap_path = snapshot_path(repo, policy["version"])
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        _atomic_write_json(snap_path, policy)
    except: pass
    hist_entry = {
        "version": version_bump,
        "date": proposal["ts"],
        "change": change,
        "evidence": evidence,
        "confidence": confidence,
        "previous_version": policy["version"],
        "heuristic": True
    }
    policy["history"].append(hist_entry)
    policy["version"] = version_bump
    save(repo, policy)
    # verify version
    reloaded = load(repo)
    if reloaded.get("version") != version_bump:
        return {"error": "Verification failed after save", "error_type": "VERIFICATION_ERROR"}
    proposal["applied"] = True
    proposal["new_version"] = version_bump
    proposal["heuristic"] = True
    proposal["warning"] = "Legacy string change — no structured field mutation verified; use structured {path,new_value} for real mutation"
    return proposal

def rollback(repo: Path, target_version: str) -> dict:
    pol = load(repo)
    # try snapshot file first
    snap = snapshot_path(repo, target_version)
    if snap.exists():
        try:
            snap_data = json.loads(snap.read_text(encoding="utf-8"))
            # preserve history: append rollback entry but restore all fields from snapshot
            current_version = pol["version"]
            restored = json.loads(json.dumps(snap_data))  # deep copy
            # keep history from current, append rollback
            restored["history"] = list(pol.get("history", []))
            restored["history"].append({
                "version": target_version + "-rollback",
                "date": datetime.now(timezone.utc).isoformat(),
                "change": f"rollback to {target_version} (snapshot restore)",
                "evidence": f"rollback from {current_version} to {target_version}",
                "confidence": "validated",
                "previous_version": current_version,
                "restored_from_snapshot": True
            })
            restored["version"] = target_version + "-rollback"
            # But to satisfy spec "exact previous effective state restored", we set version to target_version then add rollback marker
            # Actually store exact snapshot + audit entry
            save(repo, restored)
            # verify
            reloaded = load(repo)
            # verify key fields match snapshot
            mismatch = []
            for k in ["specialist_threshold","skill_threshold","skill_budget","context_budget","risk_thresholds"]:
                if reloaded.get(k) != snap_data.get(k):
                    mismatch.append(k)
            if mismatch:
                return {"error": f"Rollback verification failed mismatch {mismatch}", "error_type": "VERIFICATION_ERROR"}
            return {"rolled_back_to": target_version, "via": "snapshot", "verified": True, "history": reloaded["history"][-2:]}
        except Exception as e:
            return {"error": f"Snapshot restore failed: {e}", "error_type": "POLICY_ERROR"}

    # fallback to history search
    found = None
    for h in reversed(pol.get("history",[])):
        if h.get("version") == target_version or h.get("previous_version") == target_version:
            found = h
            break
    if not found:
        return {"error": f"version {target_version} not in history and no snapshot", "error_type": "POLICY_ERROR"}
    # Need to find snapshot for previous_version
    prev_snap = snapshot_path(repo, found["previous_version"])
    if prev_snap.exists():
        return rollback(repo, found["previous_version"])
    # last resort: version string only (legacy)
    pol["version"] = found["previous_version"]
    pol["history"].append({"version": pol["version"]+"-rollback", "date": datetime.now(timezone.utc).isoformat(), "change": f"rollback to {target_version} (version-only, no snapshot)", "evidence": f"rollback from {found['version']}", "confidence": "validated", "previous_version": found["version"], "heuristic": True})
    save(repo, pol)
    return {"rolled_back_to": found["previous_version"], "via": "version-only", "warning": "No snapshot — fields not restored", "history": pol["history"][-2:]}

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--show", action="store_true")
    p.add_argument("--history", action="store_true")
    p.add_argument("--propose", nargs=2, metavar=("CHANGE","EVIDENCE"), help="propose change")
    p.add_argument("--apply", nargs=3, metavar=("CHANGE","EVIDENCE","CONFIDENCE"))
    p.add_argument("--apply-structured", action="store_true", help="use stdin json {path,new_value,reason,evidence,confidence}")
    p.add_argument("--rollback", default="", help="rollback to version")
    args = p.parse_args()
    repo = Path(args.repo)
    if args.show:
        print(json.dumps(load(repo), indent=2))
    elif args.history:
        pol = load(repo)
        print(json.dumps(pol.get("history",[]), indent=2))
    elif args.propose:
        ch, ev = args.propose
        print(json.dumps(propose(repo, ch, ev, "medium"), indent=2))
    elif args.apply:
        ch, ev, conf = args.apply
        print(json.dumps(apply_change(repo, ch, ev, conf), indent=2))
    elif args.rollback:
        res = rollback(repo, args.rollback)
        if "error" in res:
            print(json.dumps(res), file=sys.stderr); sys.exit(1)
        print(json.dumps(res, indent=2))
    else:
        print(json.dumps(load(repo), indent=2))
