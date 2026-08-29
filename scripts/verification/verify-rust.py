#!/usr/bin/env python3
"""Minimal Rust/Tauri verification selector."""
import subprocess, sys
from pathlib import Path

def run(cmd, cwd="."):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=180)
    print(r.stdout[-4000:])
    if r.stderr: print(r.stderr[-3000:], file=sys.stderr)
    return r.returncode == 0

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", default=".")
    p.add_argument("--filter", default="", help="cargo test filter")
    args = p.parse_args()
    cwd = Path(args.cwd)
    tauri = cwd / "src-tauri" if (cwd / "src-tauri").exists() else cwd
    ok = True
    if (tauri / "Cargo.toml").exists():
        ok = run("cargo check", cwd=str(tauri)) and ok
        if args.filter:
            ok = run(f"cargo test {args.filter}", cwd=str(tauri)) and ok
        else:
            print("No filter — cargo check only (pass --filter for targeted cargo test)")
        # wiring checks if in repo root
        root = cwd if (cwd / "package.json").exists() else tauri.parent
        if (root / "package.json").exists():
            ok = run("pnpm wiring:check", cwd=str(root)) and ok
            ok = run("pnpm ipc:check", cwd=str(root)) and ok
    else:
        print("No Cargo.toml found")
    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
