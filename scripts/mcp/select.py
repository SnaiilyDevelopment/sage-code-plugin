#!/usr/bin/env python3
"""
MCP-aware selection — determines which MCP servers are useful for a task.
Does NOT invoke MCP; just recommends.
"""
import re, json, sys

SCORES = {
    "github": [r"github", r"\bpr\b", r"issue #?\d+", r"pull request", r"\bgh\b", r"octokit"],
    "documentation": [r"tauri.*current|current.*tauri", r"rust.*current|current.*rust", r"windows.*api|win32.*api", r"whether.*changed|current.*behavior", r"docs.*lookup|lookup.*docs"],
    "web": [r"current.*web|web.*current", r"external.*service", r"security.*advisory", r"\bbrowser\b", r"stripe.*api|supabase.*current"],
}

def _sanitize_for_mcp(text: str) -> str:
    """Apply same secret firewall to MCP-bound content — never send unnecessary repo content."""
    try:
        import importlib.util as _ilu
        from pathlib import Path as _P
        sp = _P(__file__).resolve().parents[1] / "safety" / "secret-strip.py"
        spec = _ilu.spec_from_file_location("ss_mcp", str(sp))
        m = _ilu.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m.strip(text)
    except:
        return text

def select(task: str, categories: list) -> dict:
    # Priority: repo → project docs → installed docs → MCP docs → web (only if unavailable locally)
    # Do not call MCP just because it exists; score 0-10 threshold 5
    task_sanitized = _sanitize_for_mcp(task)
    text = (task_sanitized + " " + " ".join(categories)).lower()
    scores = {}
    for server, pats in SCORES.items():
        s = 0
        for pat in pats:
            if re.search(pat, text, re.I):
                s += 5
        # category bonus
        if server == "github" and "git" in categories: s += 3
        if server == "documentation" and "research" in categories: s += 3
        if server == "web" and "research" in categories: s += 2
        scores[server] = min(10, s)

    recommended = [k for k,v in scores.items() if v >= 5]
    if not recommended:
        recommendation = "No MCP needed — repository already has answer."
    else:
        recommendation = f"Use {', '.join(recommended)} MCP"

    # Safety: flag high-risk if task wants to delete/modify remote
    high_risk = bool(re.search(r"delete.*remote|modify.*repo|change.*external|execute.*remote|push.*force|remove.*branch", text, re.I))
    safety = "High-risk MCP operation — requires confirmation" if high_risk else "Read-only or low-risk"

    return {
        "scores": scores,
        "recommended": recommended,
        "recommendation": recommendation,
        "safety": safety,
        "preference_order": "repository > project docs > installed docs > MCP docs > web",
        "sanitized": task_sanitized != task,
        "note": "MCP content passes through secret firewall; never send unnecessary repository content"
    }

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?")
    p.add_argument("--categories", default="")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or ""
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    print(json.dumps(select(task, cats), indent=2))
