#!/usr/bin/env python3
"""Tauri-specific checks wrapper."""
import subprocess, sys
from pathlib import Path

def run(cmd, cwd="."):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
    print(r.stdout[-4000:])
    if r.stderr: print(r.stderr[-3000:], file=sys.stderr)
    return r.returncode == 0

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", default=".")
    args = p.parse_args()
    cwd = Path(args.cwd)
    root = cwd if (cwd / "package.json").exists() else Path("C:/Users/SageOS/Documents/GitHub/sage-tweaks")
    ok = True
    ok = run("pnpm wiring:check", cwd=str(root)) and ok
    ok = run("pnpm ipc:check", cwd=str(root)) and ok
    ok = run("pnpm security:policy", cwd=str(root)) and ok
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
