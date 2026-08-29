#!/usr/bin/env python3
"""
Advanced persistent memory — JSON store with provenance, TTL, last_validated, related_area.
Location: .wolf/sage-memory.json (git-ignored) + references/sage-memory.md rendered view.
Confidence: hypothesis < observed < verified < validated. Truth hierarchy: live repo > tool output > config > validated memory > historical > inference.
"""
import json, re, hashlib
from pathlib import Path
from datetime import datetime, timezone

SENSITIVE_RE = re.compile(r"secret|token|private_key|supabase.*service_role|stripe_secret|license\.dat|hwid\.dat|credentials|api_key|sk-", re.I)

# confidence ordering
ORDER = {"hypothesis":0, "observed":1, "verified":2, "validated":3, "low":0, "medium":1, "high":2}
ALIAS = {"low":"hypothesis", "medium":"observed", "high":"verified", "validated":"validated", "hypothesis":"hypothesis","observed":"observed","verified":"verified"}

def normalize_conf(c: str) -> str:
    c = c.lower().strip()
    return ALIAS.get(c, c)

def resolve_path(repo: Path) -> Path:
    p = repo / ".wolf" / "sage-memory.json"
    if not repo.exists() or not (repo / ".git").exists():
        p = Path(__file__).resolve().parents[2] / ".wolf" / "sage-memory.json"
    return p

def load(repo: Path) -> dict:
    p = resolve_path(repo)
    if not p.exists():
        return {"items": [], "version": 1, "policy_version": "2.0"}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # migrate old confidence
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
    except:
        return {"items": [], "version": 1, "policy_version": "2.0"}

def save(repo: Path, data: dict):
    p = resolve_path(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    for it in data.get("items",[]):
        if SENSITIVE_RE.search(json.dumps(it)):
            raise ValueError("Memory item contains sensitive data — refused")
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    render_md(repo, data)

def add_item(repo: Path, fact: str, source: str, confidence: str = "observed", category: str = "general", ttl_days: int = 90, related_area: str = ""):
    if SENSITIVE_RE.search(fact) or SENSITIVE_RE.search(source):
        raise ValueError("Sensitive data in memory fact/source — refused")
    if len(fact.strip()) < 10:
        raise ValueError("Fact too short — not durable")
    # Bad patterns: line numbers without context
    if re.match(r"^(changed line|fixed line|updated line)\s+\d+", fact, re.I):
        raise ValueError("Trivial line change not durable — save reusable engineering fact instead")
    data = load(repo)
    confidence = normalize_conf(confidence)
    if confidence not in ORDER:
        confidence = "observed"
    related_area = related_area or category
    now_iso = datetime.now(timezone.utc).isoformat()
    item = {
        "id": hashlib.sha256(fact.encode()).hexdigest()[:8],
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
    # if exists, update last_validated and confidence if higher
    existing = next((x for x in data["items"] if x["id"] == item["id"]), None)
    if existing:
        # upgrade confidence only, never downgrade validated via weaker evidence
        if ORDER[confidence] > ORDER.get(existing.get("confidence","observed"),0):
            existing["confidence"] = confidence
        existing["last_validated"] = now_iso
        existing["source"] = source  # provenance update
        save(repo, data)
        return existing
    data["items"].append(item)
    if len(data["items"]) > 100:
        data["items"].sort(key=lambda x: (ORDER.get(x["confidence"],0), x["last_validated"]), reverse=True)
        data["items"] = data["items"][:100]
    save(repo, data)
    return item

def get_valid(repo: Path, category: str = "") -> list:
    data = load(repo)
    now = datetime.now(timezone.utc)
    valid = []
    for it in data.get("items",[]):
        try:
            d = datetime.fromisoformat(it.get("last_validated") or it.get("date").replace("Z","+00:00"))
            # handle both date formats
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
    """Auto memory extraction — heuristic durable vs not durable."""
    if not success:
        return []
    candidates = []
    low = task.lower() + " " + verification.lower()
    # Good patterns: architecture, compatibility, known fix, measured perf
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
    # Bad: trivial line change
    if re.match(r"changed line \d+", task, re.I):
        return []
    return candidates

def render_md(repo: Path, data: dict):
    plugin_md = Path(__file__).resolve().parents[2] / "references" / "sage-memory.md"
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

    if plugin_md.exists():
        txt = plugin_md.read_text(encoding="utf-8", errors="ignore")
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
            plugin_md.write_text(new_txt, encoding="utf-8")
            return
    lines = ["# Sage Memory — Persistent Project Knowledge", "", "> Auto-rendered durable items from `.wolf/sage-memory.json`. Repository evidence wins. Every item has provenance (fact, source, date, confidence, last_validated, ttl, related_area). Raw JSON is authoritative.", ""]
    lines.extend(auto_lines)
    plugin_md.write_text("\n".join(lines), encoding="utf-8")

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
    else:
        data = load(repo)
        print(json.dumps(data, indent=2))
