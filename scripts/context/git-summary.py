#!/usr/bin/env python3
"""Git intelligence: diff stats, changed files, branch, accidental-change detection."""
import subprocess, json, sys, re
from pathlib import Path

def run(cmd, cwd="."):
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=10)
    return r.stdout.strip(), r.stderr.strip(), r.returncode

def summarize(cwd="."):
    branch,_,_ = run("git rev-parse --abbrev-ref HEAD", cwd)
    status,_ ,_ = run("git status --porcelain", cwd)
    diff_stat,_,_ = run("git diff --stat", cwd)
    diff_cached,_,_ = run("git diff --cached --stat", cwd)
    diff_files,_,_ = run("git diff --name-only", cwd)
    untracked,_,_ = run("git ls-files --others --exclude-standard", cwd)
    log,_,_ = run("git log --oneline -5", cwd)

    changed = [f for f in diff_files.splitlines() if f.strip()]
    untracked_list = [f for f in untracked.splitlines() if f.strip()]
    status_lines = [l for l in status.splitlines() if l.strip()]

    # accidental-change heuristics
    suspicious = []
    for f in changed + untracked_list:
        if re.search(r"\.env|credentials|secrets|\.pem|\.key|license\.dat|hwid\.dat", f, re.I):
            suspicious.append(f"secrets-like file touched: {f}")
        if re.search(r"package-lock\.json|pnpm-lock\.yaml|Cargo\.lock", f) and len(changed)>5:
            suspicious.append(f"lockfile churn: {f}")
    if len(changed) > 20:
        suspicious.append(f"large diff: {len(changed)} files changed")

    return {
        "branch": branch or "unknown",
        "changed_files": changed,
        "changed_count": len(changed),
        "untracked": untracked_list[:20],
        "status_lines": status_lines[:20],
        "diff_stat": diff_stat[:2000],
        "diff_cached_stat": diff_cached[:2000],
        "log_recent": log.splitlines()[:5],
        "suspicious": suspicious,
    }

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", default=".")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = summarize(args.cwd)
    print(json.dumps(data, indent=2))
