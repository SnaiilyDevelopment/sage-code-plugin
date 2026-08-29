#!/usr/bin/env python3
"""
A/B experiment helper: compare Claude-direct vs Scout+Claude
Measures tokens, cost, duration, tool calls, success, verified issues, false positives.
"""
import json, sys, time, subprocess, uuid
from pathlib import Path

def run_variant(task: str, variant: str, repo: str = ".") -> dict:
    """Run a single variant, log telemetry, return metrics."""
    # This is a harness — actual Claude execution is outside, we measure via telemetry log
    # For now, simulate measurement by calling preflight for scout variant
    start = time.time()
    metrics = {"variant": variant, "task": task[:100], "experiment_id": str(uuid.uuid4())[:8]}
    if variant == "scout":
        try:
            r = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "routing/preflight.py"), task, "--repo", repo], capture_output=True, text=True, timeout=10)
            pre = json.loads(r.stdout)
            scout = pre.get("scout") or {}
            metrics["scout_tokens"] = scout.get("tokens_in",0) + scout.get("tokens_out",0)
            metrics["scout_cost"] = scout.get("cost_usd",0)
            metrics["scout_latency"] = scout.get("latency_ms",0)
            metrics["scout_status"] = scout.get("status","unknown")
        except Exception as e:
            metrics["error"] = str(e)[:200]
    metrics["duration_ms"] = int((time.time()-start)*1000)
    return metrics

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?")
    p.add_argument("--repo", default=".")
    p.add_argument("--runs", type=int, default=1)
    args = p.parse_args()
    task = args.task or "test task"
    results = []
    for i in range(args.runs):
        c = run_variant(task, "control", args.repo)
        s = run_variant(task, "scout", args.repo)
        results.append({"run": i, "control": c, "scout": s})
    # summary
    print(json.dumps({"experiment": "Claude-direct vs Scout+Claude", "runs": results, "note": "Do not claim scout beneficial until delta_success >0 and cost saving measured. Real experiment requires paired task execution via Claude Code telemetry."}, indent=2))
