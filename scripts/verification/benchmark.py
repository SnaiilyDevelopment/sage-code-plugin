#!/usr/bin/env python3
"""
Benchmark harness V1.1 — baseline, controlled workload, repeated runs, noise, before/after, regression detection.
Supports improvement / regression / inconclusive / not_measurable.
Uses actual system tools when available (presentmon, diskspd, iperf3, smartctl in src-tauri/binaries) via sidecar pattern; falls back to timed command.
"""
import json, sys, time, subprocess, statistics, argparse
from pathlib import Path

def run_workload(cmd: str, repeats: int = 5) -> dict:
    samples = []
    for i in range(repeats):
        start = time.time()
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
            elapsed = time.time() - start
            # try to parse numeric metric from stdout (e.g., diskspd MB/s or presentmon fps)
            metric = None
            out = r.stdout or ""
            import re
            # look for float in output as potential metric; fallback to elapsed
            m = re.search(r"(\d+\.\d+)", out)
            if m and r.returncode == 0 and len(out) < 2000:
                try:
                    metric = float(m.group(1))
                    # if output explicitly contains metric keyword, use it; else elapsed is more reliable
                    if any(k in out.lower() for k in ["fps","mb/s","latency","ms"]):
                        samples.append(metric)
                    else:
                        samples.append(elapsed)
                except:
                    samples.append(elapsed)
            else:
                samples.append(elapsed)
            print(f"  sample {i+1}: {samples[-1]:.4f} (exit {r.returncode})")
        except Exception as e:
            print(f"  sample {i+1} failed: {e}")
            samples.append(None)
    valid = [s for s in samples if s is not None]
    if not valid:
        return {"error": "no valid samples", "samples": samples, "repeats": repeats}
    if len(valid) == 1:
        return {"samples": valid, "mean": valid[0], "stdev": 0, "min": valid[0], "max": valid[0], "n": 1, "repeats": repeats}
    return {
        "samples": valid,
        "mean": statistics.mean(valid),
        "stdev": statistics.stdev(valid) if len(valid) > 1 else 0,
        "min": min(valid),
        "max": max(valid),
        "n": len(valid),
        "repeats": repeats,
        "cv": (statistics.stdev(valid)/statistics.mean(valid) if statistics.mean(valid) else 0),
    }

def compare(baseline: dict, current: dict) -> dict:
    if "error" in baseline or "error" in current:
        return {"classification": "not_measurable", "reason": "missing samples", "delta": 0}
    if baseline["n"] < 2 or current["n"] < 2:
        return {"classification": "not_measurable", "reason": "insufficient repeats (<2)", "delta": 0}
    delta = current["mean"] - baseline["mean"]
    delta_pct = (delta / baseline["mean"] * 100) if baseline["mean"] else 0
    # noise: 2*stdev or 2% or 5% CV threshold, whichever larger
    noise = max(baseline["stdev"] * 2, baseline["mean"] * 0.02, baseline["mean"] * baseline.get("cv",0)*1.5)
    # not measurable if CV high (>15%)
    if baseline.get("cv",0) > 0.15 or current.get("cv",0) > 0.15:
        return {"classification": "not_measurable", "reason": f"high variance CV baseline {baseline.get('cv',0):.2%} current {current.get('cv',0):.2%}", "delta": delta, "delta_pct": delta_pct, "noise": noise}
    if abs(delta) < noise:
        cls = "inconclusive"
        reason = f"delta {delta:.4f} within noise {noise:.4f}"
    elif delta < 0:
        cls = "improvement"
        reason = f"faster by {abs(delta_pct):.1f}% outside noise"
    else:
        cls = "regression"
        reason = f"slower by {delta_pct:.1f}% outside noise"
    return {"classification": cls, "delta": delta, "delta_pct": delta_pct, "noise": noise, "reason": reason}

def main():
    p = argparse.ArgumentParser(description="SageTweaks benchmark harness V1.1")
    p.add_argument("--baseline-cmd", default="echo baseline")
    p.add_argument("--current-cmd", default="")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--hypothesis", default="no hypothesis")
    p.add_argument("--tool", default="elapsed", help="presentmon|diskspd|iperf3|elapsed")
    args = p.parse_args()
    current_cmd = args.current_cmd or args.baseline_cmd
    print(f"Hypothesis: {args.hypothesis}")
    print(f"Tool: {args.tool} | Repeats: {args.repeats}")
    print(f"Baseline workload: {args.baseline_cmd} x{args.repeats}")
    baseline = run_workload(args.baseline_cmd, args.repeats)
    print(f"Baseline: {json.dumps(baseline, indent=2)}")
    print(f"\nCurrent workload: {current_cmd} x{args.repeats}")
    current = run_workload(current_cmd, args.repeats)
    print(f"Current: {json.dumps(current, indent=2)}")
    result = compare(baseline, current)
    print(f"\n# Result: {result['classification']} — {result['reason']}")
    print(f"# Hypothesis: {args.hypothesis}")
    print(f"# Measured: baseline mean {baseline.get('mean',0):.4f}, current mean {current.get('mean',0):.4f}, delta {result.get('delta',0):.4f} ({result.get('delta_pct',0):.1f}%)")
    print(f"# Distinction: improvement / regression / inconclusive / not_measurable — do not fake hardware metrics")
    print(f"# Conditions: record OS build / driver / power plan / hardware manually for publishable claims")
    print(json.dumps({"hypothesis": args.hypothesis, "tool": args.tool, "baseline": baseline, "current": current, "result": result}, indent=2))

if __name__ == "__main__":
    main()
