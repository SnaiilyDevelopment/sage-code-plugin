#!/usr/bin/env python3
"""
Compact evidence pack — converts scout output into Claude-consumable pack with provenance.
Statuses: VERIFIED, STRONG_EVIDENCE, OBSERVATION, HYPOTHESIS, UNKNOWN. Never huge raw transcript.
"""
import json, re
from pathlib import Path
from datetime import datetime, timezone

STATUSES = ["VERIFIED","STRONG_EVIDENCE","OBSERVATION","HYPOTHESIS","UNKNOWN"]
BUDGET_TOKENS = 800

def estimate_tokens(obj) -> int:
    return len(json.dumps(obj)) // 4

def build_pack(task: str, scout_result: dict, relevant_files: list = None, budget: int = BUDGET_TOKENS) -> dict:
    findings = scout_result.get("findings", []) if scout_result else []
    # normalize statuses
    normed = []
    for f in findings[:6]:  # cap 6 findings
        status = f.get("status","UNKNOWN").upper()
        if status not in STATUSES: status = "OBSERVATION"
        # provenance
        normed.append({
            "claim": f.get("claim","")[:300],
            "status": status,
            "files": (f.get("files") or [])[:3],
            "evidence": f.get("evidence","")[:500],
            "confidence": round(float(f.get("confidence", 0.5)), 2),
            "source": f.get("source","scout:" + scout_result.get("model","unknown")),
            "model": scout_result.get("model","unknown"),
            "verified": False  # Claude must set to true after validation
        })
    # compact relevant files (dedup)
    rel = list(dict.fromkeys(relevant_files or []))[:5]
    # recommended checks derived from findings
    checks = []
    for f in normed:
        if "registry" in f["claim"].lower(): checks.append("reg query or registry_probe")
        if "security" in f["claim"].lower(): checks.append("validate-bash + security scan")
        if "tauri" in f["claim"].lower(): checks.append("cargo check + wiring:check")
    checks = list(dict.fromkeys(checks))[:3]

    pack = {
        "task": task[:500],
        "findings": normed,
        "suspectedRootCauses": [f["claim"] for f in normed if f["status"] in ["STRONG_EVIDENCE","HYPOTHESIS"]][:2],
        "relevantFiles": rel,
        "recommendedChecks": checks,
        "researchSources": [],
        "unknowns": [f["claim"] for f in normed if f["status"] == "UNKNOWN"],
        "provenance": {
            "model": scout_result.get("model",""),
            "provider": scout_result.get("provider",""),
            "tokens_in": scout_result.get("tokens_in",0),
            "tokens_out": scout_result.get("tokens_out",0),
            "cost_usd": scout_result.get("cost_usd",0),
            "latency_ms": scout_result.get("latency_ms",0),
            "simulated": scout_result.get("simulated", False),
            "date": datetime.now(timezone.utc).isoformat()
        },
        "size_tokens_est": estimate_tokens({"findings": normed}),
        "_instruction": "Scout is NOT authoritative. Claude must independently validate important findings via repo tools/MCP/tests before acting. Every finding has status VERIFIED/STRONG_EVIDENCE/OBSERVATION/HYPOTHESIS/UNKNOWN + confidence. Verified only after Claude confirms."
    }
    # enforce budget: truncate findings if over
    while estimate_tokens(pack) > budget and len(pack["findings"]) > 1:
        pack["findings"] = pack["findings"][:len(pack["findings"])-1]
        pack["size_tokens_est"] = estimate_tokens({"findings": pack["findings"]})
    return pack

def mark_verified(pack: dict, claim_idx: int, verified: bool, evidence: str = "") -> dict:
    if 0 <= claim_idx < len(pack.get("findings",[])):
        pack["findings"][claim_idx]["verified"] = verified
        if verified:
            pack["findings"][claim_idx]["status"] = "VERIFIED"
        if evidence:
            pack["findings"][claim_idx]["verification_evidence"] = evidence[:500]
    return pack

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--task", default="")
    p.add_argument("--budget", type=int, default=BUDGET_TOKENS)
    args = p.parse_args()
    # demo: build from simulated scout
    task = args.task or sys.stdin.read().strip() or "demo task"
    scout = {"model":"deepseek-v4-flash","provider":"generic","findings":[{"claim":"Potential registry rollback mismatch","status":"STRONG_EVIDENCE","files":[r"src-tauri/src/tweaks/impls/power.rs:42"],"evidence":r"HKLM SYSTEM\Services Start not snapshot","confidence":0.86}], "tokens_in":80,"tokens_out":120,"cost_usd":0.008,"latency_ms":820,"simulated":True}
    print(json.dumps(build_pack(task, scout, budget=args.budget), indent=2))
