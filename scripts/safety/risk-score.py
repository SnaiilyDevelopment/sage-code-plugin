#!/usr/bin/env python3
"""
7-dimension risk scorer 0-100.
Dimensions: security, system_impact, destructive, architecture, scale, ambiguity, failure_rate
Thresholds: 0-24 none, 25-49 self-review, 50-74 specialist, 75+ specialist+strong
"""
import sys, json, re, argparse

DIMENSIONS = ["security","system_impact","destructive","architecture","scale","ambiguity","failure_rate"]
WEIGHTS = {"security":2.0,"system_impact":2.0,"destructive":1.5,"architecture":1.0,"scale":1.0,"ambiguity":1.0,"failure_rate":1.0}
MAX_WEIGHTED = sum(WEIGHTS[d]*10 for d in DIMENSIONS)

def score_dimension(dim: str, task: str, files: list[str], complexity: str) -> int:
    t = task.lower()
    ftext = " ".join(files).lower()
    combined = t + " " + ftext
    s = 0
    if dim == "security":
        if re.search(r"privilege|elevation|uac|auth|secret|token|credential|permission|security|cve|injection|xss|audit.*elevation", combined): s = 9
        elif re.search(r"process|service|registry.*hklm", combined): s = 6
        elif re.search(r"input.*valid|sanit", combined): s = 4
        # elevation path alone is high security
        if re.search(r"elevation.*path|privilege.*boundary", combined): s = max(s, 8)
    elif dim == "system_impact":
        if re.search(r"registry|hklm|hkcu.*system|services\.msc|sc (delete|config|create)|bcdedit|powercfg|netsh|firewall", combined): s = 9
        elif re.search(r"windows|tauri.*command|sidecar|startup", combined): s = 5
        elif re.search(r"frontend|css|wording", combined): s = 1
    elif dim == "destructive":
        if re.search(r"delete|remove.*recurse|format|del /|rm -rf|reset --hard|destructive|rollback", combined): s = 10
        elif re.search(r"migration|drop|truncate|overwrite", combined): s = 7
        elif re.search(r"edit.*config|tweak.*apply", combined): s = 4
    elif dim == "architecture":
        if re.search(r"architecture|bounded context|service boundary|queue|migration|refactor.*module", combined): s = 8
        elif re.search(r"refactor|extract.*module|ipc.*contract", combined): s = 5
        elif complexity=="complex": s = 4
    elif dim == "scale":
        n = len(files)
        if n > 10: s = 8
        elif n > 5: s = 5
        elif n > 2: s = 3
        elif re.search(r"bulk|all.*tweaks|global.*change", combined): s = 6
    elif dim == "ambiguity":
        if re.search(r"investigate|whether|maybe|unclear|unknown|research|check.*current", combined): s = 7
        elif re.search(r"fix.*bug.*without.*repro|hard.*to.*repro", combined): s = 6
        elif complexity=="simple" and len(combined.split())<10: s = 2
    elif dim == "failure_rate":
        if re.search(r"registry.*tweak|wddm|tdr|power plan|game mode|firmware", combined): s = 7
        elif re.search(r"rust.*state|tauri.*ipc|race.*condition", combined): s = 6
        elif re.search(r"known.*pitfall|technical.*debt", combined): s = 5
    return min(10, s)

def compute(task: str, files: list[str], complexity: str = "medium") -> dict:
    scores = {d: score_dimension(d, task, files, complexity) for d in DIMENSIONS}
    weighted = sum(scores[d]*WEIGHTS[d] for d in DIMENSIONS)
    normalized = int(round(weighted / MAX_WEIGHTED * 100))
    # Threshold routing
    if normalized <= 24:
        tier = "low"
        action = "no specialist review; standard verification"
    elif normalized <= 49:
        tier = "medium"
        action = "targeted self-review + deterministic verification"
    elif normalized <= 74:
        tier = "high"
        action = "specialist review required"
    else:
        tier = "critical"
        action = "specialist review + stronger verification + rollback plan"

    reasons = []
    for d, v in scores.items():
        if v >= 7:
            reasons.append(f"{d}={v} high")
    if not reasons:
        reasons = ["no dimension >=7; overall low"]

    return {
        "risk_score": normalized,
        "tier": tier,
        "action": action,
        "dimensions": scores,
        "reasons": reasons,
        "thresholds": {"low":"0-24","medium":"25-49","high":"50-74","critical":"75-100"},
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task description")
    p.add_argument("--files", default="")
    p.add_argument("--complexity", default="medium")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip()
    if not task:
        print(json.dumps({"error":"no task"})); sys.exit(1)
    files = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []
    result = compute(task, files, args.complexity)
    result["task_preview"] = task[:200]
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
