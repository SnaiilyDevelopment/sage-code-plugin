#!/usr/bin/env python3
"""Quality lint wrapper."""
import subprocess, sys
from pathlib import Path

def run(cmd, cwd):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=60)
    print(r.stdout[-4000:])
    if r.stderr: print(r.stderr[-2000:], file=sys.stderr)
    return r.returncode == 0

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", default=".")
    args = p.parse_args()
    cwd = Path(args.cwd)
    ok = True
    if (cwd / "package.json").exists():
        ok = run("pnpm lint", cwd=str(cwd)) and ok
        ok = run("pnpm type-check", cwd=str(cwd)) and ok
    sys.exit(0 if ok else 1)
