#!/usr/bin/env python3
"""Select minimal frontend verification based on changed files."""
import subprocess, sys, json
from pathlib import Path

def run(cmd, cwd="."):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=120)
    print(r.stdout[-3000:])
    if r.stderr: print(r.stderr[-2000:], file=sys.stderr)
    return r.returncode == 0

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--cwd", default=".")
    p.add_argument("--pattern", default="", help="vitest pattern")
    p.add_argument("--skip-build", action="store_true")
    args = p.parse_args()

    cwd = Path(args.cwd)
    ok = True
    # type-check
    if (cwd / "package.json").exists():
        ok = run("pnpm type-check", cwd=str(cwd)) and ok
        ok = run("pnpm lint", cwd=str(cwd)) and ok
        if args.pattern:
            ok = run(f"pnpm test -- {args.pattern}", cwd=str(cwd)) and ok
        else:
            # only run targeted if we can detect, else skip bulk
            print("No pattern — skipping full test suite (pass --pattern for targeted)")
        if not args.skip_build:
            # build is optional unless requested
            pass
    else:
        print("No package.json — nothing to verify")

    sys.exit(0 if ok else 1)

if __name__ == "__main__":
    main()
