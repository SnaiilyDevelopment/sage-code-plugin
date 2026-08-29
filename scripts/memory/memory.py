#!/usr/bin/env python3
"""
Advanced persistent memory — JSON store with provenance, TTL, last_validated, related_area.
Location: <repo>/.wolf/sage-memory.json + <repo>/.wolf/sage-memory.md (project-local).
Confidence: hypothesis < observed < verified < validated.
"""
import json, re, hashlib, os, tempfile
from pathlib import Path
from datetime import datetime, timezone

SENSITIVE_RE = re.compile(r"secret|token|private_key|supabase.*service_role|stripe_secret|license\.dat|hwid\.dat|credentials|api_key|sk-", re.I)

ORDER = {"hypothesis":0, "observed":1, "verified":2, "validated":3, "low":0, "medium":1, "high":2}
ALIAS = {"low":"hypothesis", "medium":"observed", "high":"verified", "validated":"validated", "hypothesis":"hypothesis","observed":"observed","verified":"verified"}

def normalize_conf(c: str) -> str:
    c = c.lower().strip()
    return ALIAS.get(c, c)

def _atomic_write_json(path: Path, obj: dict):
    # delegate to shared utils.atomic with lock
    try:
        from scripts.utils.atomic import atomic_write_json as _shared
        _shared(path, obj)
        return
    except (ImportError, OSError): pass
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            bak = path.with_suffix(path.suffix + ".bak")
            bak.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except (OSError, UnicodeError): pass
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="."+path.name+".tmp.")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps(obj, indent=2))
            f.flush()
            try: os.fsync(f.fileno())
            except (OSError, AttributeError): pass
        os.replace(tmp, str(path))
    except (OSError, IOError) as e:
        try: os.unlink(tmp)
        except (OSError, FileNotFoundError): pass
        raise

def _atomic_write_text(path: Path, text: str):
    try:
        from scripts.utils.atomic import atomic_write as _shared_t
        _shared_t(path, text)
        return
    except (ImportError, OSError): pass
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="."+path.name+".tmp.")
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
            f.flush()
            try: os.fsync(f.fileno())
            except (OSError, AttributeError): pass
        os.replace(tmp, str(path))
    except (OSError, IOError):
        try: os.unlink(tmp)
        except (OSError, FileNotFoundError): pass
        raise

def resolve_path(repo: Path) -> Path:
    # Project-local only: <repo>/.wolf/sage-memory.json
    # If repo is not a git repo, require explicit repo or fail — do not leak to plugin root
    repo = Path(repo)
    p = repo / ".wolf" / "sage-memory.json"
    # Only use plugin fallback if repo literally does not exist (e.g., tests with temp)
    # but never for cross-project leak: check if repo path exists
    if not repo.exists():
        p = Path(__file__).resolve().parents[2] / ".wolf" / "sage-memory.json"
        return p
    # If repo exists but no .git, still use repo-local .wolf (isolated), not plugin
    return p

def resolve_md_path(repo: Path) -> Path:
    repo = Path(repo)
    if not repo.exists():
        return Path(__file__).resolve().parents[2] / ".wolf" / "sage-memory.md"
    return repo / ".wolf" / "sage-memory.md"

def load(repo: Path) -> dict:
    p = resolve_path(repo)
    if not p.exists():
        return {"items": [], "version": 1, "policy_version": "2.0"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        for it in data.get("items",[]):
            if "confidence" in it:
                it["confidence"] = normalize_conf(it["confidence"])
            if "last_validated" not in it:
                it["last_validated"] = it.get("date","")
            if "related_area" not in it:
                it["related_area"] = it.get("category","general")
            if "ttl_days" not in it:
                it["ttl_days"] = 90
        return data
    except (json.JSONDecodeError, UnicodeError, OSError) as e:
        try:
            corrupt_copy = p.with_name(p.name + ".corrupt." + datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"))
            corrupt_copy.write_text(p.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
        except (OSError, UnicodeError): pass
        bak = p.with_suffix(p.suffix + ".bak")
        if bak.exists():
            try:
                data = json.loads(bak.read_text(encoding="utf-8"))
                data["_recovery"] = "recovered from .bak"
                data["_corruption_detected"] = True
                data["_corruption_error"] = str(e)[:300]
                return data
            except (json.JSONDecodeError, OSError, UnicodeError): pass
        return {"items": [], "version": 1, "policy_version": "2.0", "_corruption_detected": True, "_corruption_error": str(e)[:300], "_status": "MEMORY_CORRUPTED", "_corrupt_path": str(p)}

def load_with_status(repo: Path) -> dict:
    """Returns data plus status field for diagnostics."""
    p = resolve_path(repo)
    if not p.exists():
        return {"data": {"items": [], "version": 1}, "status": "MISSING", "path": str(p)}
    data = load(repo)
    if data.get("_status") == "MEMORY_CORRUPTED" or data.get("_corruption_detected"):
        return {"data": data, "status": "MEMORY_CORRUPTED", "path": str(p), "error": data.get("_corruption_error","")}
    return {"data": data, "status": "OK", "path": str(p)}

def save(repo: Path, data: dict):
    p = resolve_path(repo)
    for it in data.get("items",[]):
        if SENSITIVE_RE.search(json.dumps(it)):
            raise ValueError("Memory item contains sensitive data — refused")
    # remove internal markers before save
    clean = json.loads(json.dumps(data))
    clean.pop("_corruption_detected", None)
    clean.pop("_corruption_error", None)
    clean.pop("_status", None)
    clean.pop("_recovery", None)
    clean.pop("_corrupt_path", None)
    _atomic_write_json(p, clean)
    render_md(repo, clean)

def add_item(repo: Path, fact: str, source: str, confidence: str = "observed", category: str = "general", ttl_days: int = 90, related_area: str = ""):
    if SENSITIVE_RE.search(fact) or SENSITIVE_RE.search(source):
        raise ValueError("Sensitive data in memory fact/source — refused")
    if len(fact.strip()) < 10:
        raise ValueError("Fact too short — not durable")
    if re.match(r"^(changed line|fixed line|updated line)\s+\d+", fact, re.I):
        raise ValueError("Trivial line change not durable — save reusable engineering fact instead")
    # deduplication: check existing by fact hash within last 24h to avoid duplicate entries
    data = load(repo)
    confidence = normalize_conf(confidence)
    if confidence not in ORDER:
        confidence = "observed"
    related_area = related_area or category
    now_iso = datetime.now(timezone.utc).isoformat()
    fid = hashlib.sha256(fact.encode()).hexdigest()[:8]
    # idempotency: if same fact exists and last_validated within 1h, just touch
    existing = next((x for x in data["items"] if x["id"] == fid), None)
    if existing:
        # check if recently added (within 1 hour) — avoid duplicate churn
        try:
            last = datetime.fromisoformat((existing.get("last_validated") or existing.get("date")).replace("Z","+00:00"))
            age_h = (datetime.now(timezone.utc) - last).total_seconds()/3600
            if age_h < 1 and ORDER[confidence] <= ORDER.get(existing.get("confidence","observed"),0):
                return existing
        except: pass
        if ORDER[confidence] > ORDER.get(existing.get("confidence","observed"),0):
            existing["confidence"] = confidence
        existing["last_validated"] = now_iso
        existing["source"] = source
        save(repo, data)
        return existing
    item = {
        "id": fid,
        "fact": fact[:500],
        "source": source[:300],
        "category": category,
        "related_area": related_area,
        "date": now_iso,
        "last_validated": now_iso,
        "confidence": confidence,
        "ttl_days": ttl_days,
        "hash": hashlib.sha256(fact.encode()).hexdigest()[:12],
    }
    data["items"].append(item)
    if len(data["items"]) > 100:
        data["items"].sort(key=lambda x: (ORDER.get(x["confidence"],0), x["last_validated"]), reverse=True)
        data["items"] = data["items"][:100]
    save(repo, data)
    return item

def get_valid(repo: Path, category: str = "") -> list:
    data = load(repo)
    # if corrupted marker, return empty but caller can check status
    if data.get("_status") == "MEMORY_CORRUPTED":
        return []
    now = datetime.now(timezone.utc)
    valid = []
    for it in data.get("items",[]):
        try:
            d = datetime.fromisoformat(it.get("last_validated") or it.get("date").replace("Z","+00:00"))
            if isinstance(d, str):
                d = datetime.fromisoformat(d.replace("Z","+00:00"))
            age_days = (now - d).total_seconds()/86400
            if age_days > it.get("ttl_days",90):
                it["_stale"] = True
            else:
                it["_stale"] = False
            if category and it.get("category") != category and it.get("related_area") != category:
                continue
            valid.append(it)
        except Exception:
            continue
    return valid

def extract_candidates(task: str, verification: str, files: list, success: bool) -> list:
    if not success:
        return []
    candidates = []
    low = task.lower() + " " + verification.lower()
    good_patterns = [
        (r"requires elevation", "Windows service requires elevation and rollback must restore startup type", "windows", "references/windows.md"),
        (r"tauri.*wiring|4-piece", "Tauri 4-piece wiring must stay in sync", "architecture", "references/tauri.md"),
        (r"registry.*hklm|hkcu", "Registry path requires validation before write", "windows", "references/windows.md"),
        (r"measured|baseline.*compare|presentmon", "Performance claims require baseline→compare outside noise", "performance", "references/engineering-rules.md"),
        (r"wiring:check|ipc:check", "Wiring checks catch IPC unsync", "tauri", "scripts/verification/verify-tauri.py"),
    ]
    for pat, fact_template, cat, src in good_patterns:
        if re.search(pat, low, re.I):
            candidates.append({"fact": fact_template, "category": cat, "source": src, "confidence": "observed"})
    if re.match(r"changed line \d+", task, re.I):
        return []
    return candidates

def render_md(repo: Path, data: dict):
    md_path = resolve_md_path(repo)
    auto_lines = ["<!-- auto-rendered below from .wolf/sage-memory.json — do not edit manually -->"]
    categories = {}
    now = datetime.now(timezone.utc)
    for it in data.get("items",[]):
        try:
            d = datetime.fromisoformat((it.get("last_validated") or it.get("date")).replace("Z","+00:00"))
            it["_stale"] = (now - d).total_seconds()/86400 > it.get("ttl_days",90)
        except:
            it["_stale"] = False
        categories.setdefault(it.get("category","general"), []).append(it)
    for cat, items in sorted(categories.items()):
        auto_lines.append(f"## {cat} (auto)")
        for it in sorted(items, key=lambda x: x.get("last_validated") or x.get("date"), reverse=True)[:10]:
            stale = " *(stale — re-validate)*" if it.get("_stale") else ""
            auto_lines.append(f"- **{it['fact']}** — source: `{it['source']}` | {it['date'][:10]} | confidence: {it['confidence']} | last_validated: {it.get('last_validated','')[:10]} | area: {it.get('related_area',cat)}{stale}")
        auto_lines.append("")
    if not categories:
        auto_lines.append("_No durable auto memory yet — add via `python scripts/memory/memory.py --add \"fact\" --source \"repo:file:line\"`_")

    # If project-local md exists, update it
    # Also keep plugin references/sage-memory.md in sync only if repo is plugin itself
    plugin_root = Path(__file__).resolve().parents[2]
    is_plugin_repo = (Path(repo).resolve() == plugin_root.resolve())

    target = md_path
    if is_plugin_repo:
        # for plugin self, also maintain references/sage-memory.md
        plugin_md = plugin_root / "references" / "sage-memory.md"
        # write to both
        for dest in [target, plugin_md]:
            if dest.exists():
                txt = dest.read_text(encoding="utf-8", errors="ignore")
                marker = "<!-- auto-rendered below from .wolf/sage-memory.json — do not edit manually -->"
                if marker in txt:
                    before = txt.split(marker)[0] + marker + "\n"
                    static_marker = "## Static Knowledge"
                    if static_marker in txt:
                        tail = txt.split(static_marker)[1]
                        tail = "## Static Knowledge" + tail
                        new_txt = before + "\n".join(auto_lines[1:]) + "\n\n" + tail
                    else:
                        new_txt = before + "\n".join(auto_lines[1:])
                    _atomic_write_text(dest, new_txt)
                    continue
            lines = ["# Sage Memory — Persistent Project Knowledge", "", "> Auto-rendered durable items from `.wolf/sage-memory.json`. Repository evidence wins. Every item has provenance (fact, source, date, confidence, last_validated, ttl, related_area). Raw JSON is authoritative.", ""]
            lines.extend(auto_lines)
            _atomic_write_text(dest, "\n".join(lines))
        return

    if md_path.exists():
        txt = md_path.read_text(encoding="utf-8", errors="ignore")
        marker = "<!-- auto-rendered below from .wolf/sage-memory.json — do not edit manually -->"
        if marker in txt:
            before = txt.split(marker)[0] + marker + "\n"
            new_txt = before + "\n".join(auto_lines[1:])
            _atomic_write_text(md_path, new_txt)
            return
    lines = ["# Sage Memory — Persistent Project Knowledge", "", "> Auto-rendered durable items from `.wolf/sage-memory.json`. Repository evidence wins.", ""]
    lines.extend(auto_lines)
    _atomic_write_text(md_path, "\n".join(lines))

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--add", default="", help="fact to add")
    p.add_argument("--source", default="", help="provenance source")
    p.add_argument("--category", default="general")
    p.add_argument("--confidence", default="observed", help="hypothesis|observed|verified|validated")
    p.add_argument("--related-area", default="")
    p.add_argument("--ttl", type=int, default=90)
    p.add_argument("--list", action="store_true")
    p.add_argument("--list-category", default="")
    p.add_argument("--extract", action="store_true", help="demo extract from task/verification")
    p.add_argument("--task", default="")
    p.add_argument("--verification", default="")
    p.add_argument("--status", action="store_true", help="show load status")
    args = p.parse_args()
    repo = Path(args.repo)
    if args.add:
        if not args.source:
            print("ERROR: --source required for provenance", file=sys.stderr); sys.exit(1)
        item = add_item(repo, args.add, args.source, args.confidence, args.category, args.ttl, args.related_area)
        print(json.dumps(item, indent=2))
    elif args.list:
        items = get_valid(repo, args.list_category)
        print(json.dumps(items, indent=2))
    elif args.extract:
        cands = extract_candidates(args.task, args.verification, [], True)
        print(json.dumps(cands, indent=2))
    elif args.status:
        print(json.dumps(load_with_status(repo), indent=2))
    else:
        data = load(repo)
        print(json.dumps(data, indent=2))
