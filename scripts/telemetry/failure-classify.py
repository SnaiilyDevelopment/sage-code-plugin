#!/usr/bin/env python3
"""
Classify failure cause from error text/tool output.
Categories: wrong_file, wrong_assumption, missing_context, incorrect_api, tool_failure, test_failure, build_failure, architecture_mistake, security_issue, environment_issue, unknown
"""
import re, sys, json

PATTERNS = [
    ("test_failure", [r"FAIL.*test", r"AssertionError", r"vitest.*fail", r"cargo test.*fail", r"expected.*received"]),
    ("build_failure", [r"cargo check.*error", r"tsc.*error", r"Type error", r"build failed", r"tauri.*build.*error"]),
    ("incorrect_api", [r"unknown.*registry", r"RegSetValue.*error", r"no.*such.*service", r"invalid.*api", r"undefined.*is not a function.*invoke"]),
    ("wrong_file", [r"No such file", r"ENOENT", r"file not found", r"cannot find module"]),
    ("missing_context", [r"needs.*context", r"stale.*memory", r"repo.*evidence.*wins", r"missing.*capability"]),
    ("tool_failure", [r"timeout", r"tool.*failed", r"command not found", r"pnpm.*ERR"]),
    ("architecture_mistake", [r"wiring:check.*fail", r"ipc.*mismatch", r"4-piece.*wiring", r"capability.*missing"]),
    ("security_issue", [r"permission.*denied", r"secret.*exposed", r"privilege.*error", r"elevation.*fail"]),
    ("environment_issue", [r"windows.*version", r"win10.*vs.*win11", r"powercfg.*not found", r"env.*not set"]),
    ("wrong_assumption", [r"assumption.*wrong", r"hypothesis.*inconclusive", r"placebo", r"no.*effect"]),
]

def classify(text: str) -> str:
    low = text.lower()
    for cause, pats in PATTERNS:
        for pat in pats:
            if re.search(pat, low, re.I):
                return cause
    return "unknown"

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("text", nargs="?", help="error text")
    args = p.parse_args()
    t = args.text or sys.stdin.read()
    print(json.dumps({"failure_cause": classify(t), "text_preview": t[:200]}))
