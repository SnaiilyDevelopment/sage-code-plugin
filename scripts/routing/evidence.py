#!/usr/bin/env python3
"""
Compact evidence pack — converts scout output into Claude-consumable pack with provenance.
Statuses: VERIFIED (only via mark_verified), STRONG_EVIDENCE, OBSERVATION, HYPOTHESIS, UNKNOWN.
"""
import json, re
from pathlib import Path
from datetime import datetime, timezone

STATUSES = ["VERIFIED","STRONG_EVIDENCE","OBSERVATION","HYPOTHESIS","UNKNOWN"]
BUDGET_TOKENS = 800

def estimate_tokens(obj) -> int:
    try:
        from scripts.routing.tokens import estimate_tokens as _est, estimate_tokens_obj as _esto
        return _esto(obj)
    except:
        return max(1, int(len(json.dumps(obj)) / 4 * 1.25))

def _check_fabricated(files: list, repo: Path) -> list:
    """Check if files exist in repo; return list of booleans fabricated flags."""
    out = []
    for f in files:
        # strip line number :42
        base = f.split(":")[0].strip()
        if not base:
            out.append(True); continue
        # path traversal check
        if ".." in base or base.startswith("/") or base.startswith("\\"):
            out.append(True); continue
        p = repo / base
        # also check via git ls-files for tracked files
        exists = p.exists()
        out.append(not exists)
    return out

def build_pack(task: str, scout_result: dict, relevant_files: list = None, budget: int = BUDGET_TOKENS, repo: str = ".", research_sources: list = None) -> dict:
    findings = scout_result.get("findings", []) if scout_result else []
    repo_path = Path(repo)
    normed = []
    for f in findings[:6]:
        raw_status = f.get("status","UNKNOWN").upper()
        # Scout can NEVER mark VERIFIED — downgrade
        downgraded = False
        if raw_status == "VERIFIED":
            raw_status = "STRONG_EVIDENCE"
            downgraded = True
        if raw_status not in STATUSES:
            raw_status = "OBSERVATION"
        files = (f.get("files") or [])[:3]
        # Fabricated path check
        fabricated_flags = _check_fabricated(files, repo_path) if files else []
        status = raw_status
        if any(fabricated_flags):
            status = "UNKNOWN"
        # separate confidence from verification
        try:
            conf = round(float(f.get("confidence", 0.5)), 2)
            conf = max(0.0, min(1.0, conf))
        except:
            conf = 0.5
        entry = {
            "claim": f.get("claim","")[:300],
            "status": status,
            "verification_status": "UNVERIFIED" if status != "VERIFIED" else "VERIFIED",
            "verification_source": "none",
            "verification_evidence": "",
            "files": files,
            "evidence": f.get("evidence","")[:500],
            "confidence": conf,
            "source": f.get("source","scout:" + scout_result.get("model","unknown")),
            "model": scout_result.get("model","unknown"),
            "verified": False,
            "cost_status": scout_result.get("cost_status","UNKNOWN"),
        }
        if downgraded:
            entry["downgraded_from_verified"] = True
            entry["downgrade_reason"] = "Scout cannot mark VERIFIED — downgraded to STRONG_EVIDENCE per trust model"
        if any(fabricated_flags):
            entry["fabricated"] = True
            entry["fabrication_detail"] = "One or more file paths not found in repo — downgraded to UNKNOWN"
        normed.append(entry)

    rel = list(dict.fromkeys(relevant_files or []))[:5]
    # also validate rel files
    rel_fabricated = _check_fabricated(rel, repo_path) if rel else []
    # filter fabricated from rel? keep but mark unknown
    checks = []
    for f in normed:
        if "registry" in f["claim"].lower(): checks.append("reg query or registry_probe")
        if "security" in f["claim"].lower(): checks.append("validate-bash + security scan")
        if "tauri" in f["claim"].lower(): checks.append("cargo check + wiring:check")
    checks = list(dict.fromkeys(checks))[:3]

    # research sources with provenance
    research_sources = research_sources or scout_result.get("research_sources") or []
    # Normalize research source provenance
    normed_research = []
    for rs in (research_sources or [])[:5]:
        if isinstance(rs, str):
            normed_research.append({"url": rs[:500], "source": "unknown", "fetched_at": datetime.now(timezone.utc).isoformat()})
        elif isinstance(rs, dict):
            normed_research.append({
                "url": rs.get("url","")[:500],
                "snippet": rs.get("snippet","")[:400] if rs.get("snippet") else "",
                "fetched_at": rs.get("fetched_at", datetime.now(timezone.utc).isoformat()),
                "status": rs.get("status","unknown"),
                "source": rs.get("source","web")
            })

    pack = {
        "task": task[:500],
        "findings": normed,
        "suspectedRootCauses": [f["claim"] for f in normed if f["status"] in ["STRONG_EVIDENCE","HYPOTHESIS"]][:2],
        "relevantFiles": rel,
        "relevantFiles_provenance": {"checked": True, "fabricated_flags": rel_fabricated} if rel else {"checked": False},
        "recommendedChecks": checks,
        "researchSources": normed_research,
        "unknowns": [f["claim"] for f in normed if f["status"] == "UNKNOWN"],
        "provenance": {
            "model": scout_result.get("model",""),
            "provider": scout_result.get("provider",""),
            "tokens_in": scout_result.get("tokens_in",0),
            "tokens_out": scout_result.get("tokens_out",0),
            "cost_usd": scout_result.get("cost_usd", None),
            "cost_status": scout_result.get("cost_status","UNKNOWN"),
            "latency_ms": scout_result.get("latency_ms",0),
            "simulated": scout_result.get("simulated", False),
            "reservation": scout_result.get("reservation", {}),
            "date": datetime.now(timezone.utc).isoformat()
        },
        "_instruction": "UNTRUSTED EVIDENCE — Scout is NOT authoritative. Claude must independently validate findings via repo tools/MCP/tests before acting. Use verification_status + verification_source. Confidence != verified."
    }
    # Accurate size accounting: full pack
    pack["size_tokens_est"] = estimate_tokens(pack)
    pack["budget_tokens"] = budget
    pack["budget_remaining_est"] = budget - pack["size_tokens_est"]

    # enforce budget: truncate findings with full-pack accounting
    while estimate_tokens(pack) > budget and len(pack["findings"]) > 1:
        pack["findings"] = pack["findings"][:len(pack["findings"])-1]
        pack["size_tokens_est"] = estimate_tokens(pack)
        pack["budget_remaining_est"] = budget - pack["size_tokens_est"]
    # also enforce max limits
    if len(pack["findings"]) > 6:
        pack["findings"] = pack["findings"][:6]
    for f in pack["findings"]:
        f["claim"] = f["claim"][:300]
        f["evidence"] = f["evidence"][:500]
        # ensure limits
        if len(f.get("files",[])) > 3:
            f["files"] = f["files"][:3]

    # final size
    pack["size_tokens_est"] = estimate_tokens(pack)
    pack["budget_remaining_est"] = budget - pack["size_tokens_est"]
    return pack

def mark_verified(pack: dict, claim_idx: int, verified: bool, evidence: str = "", source: str = "claude") -> dict:
    """Only Claude or deterministic verification may mark VERIFIED. Enforces canonical truth."""
    if not (0 <= claim_idx < len(pack.get("findings",[]))):
        return pack
    f = pack["findings"][claim_idx]
    if verified:
        # Only allow VERIFIED if source is claude/deterministic and evidence present
        if source not in ("claude","deterministic"):
            f["verification_status"] = "STRONG_EVIDENCE"
            f["verified"] = False
            f["verification_source"] = source
            f["verification_evidence"] = evidence[:500] + " [rejected: source must be claude/deterministic for VERIFIED]"
            return pack
        if not evidence or len(evidence.strip()) < 5:
            f["verification_status"] = "STRONG_EVIDENCE"
            f["verified"] = False
            f["verification_source"] = source
            f["verification_evidence"] = "[rejected: VERIFIED requires evidence]"
            return pack
        f["verified"] = True
        f["status"] = "VERIFIED"
        f["verification_status"] = "VERIFIED"
        f["verification_source"] = source
        f["verification_evidence"] = evidence[:500]
    else:
        f["verified"] = False
        if f.get("status") == "VERIFIED":
            f["status"] = "STRONG_EVIDENCE"
            f["verification_status"] = "STRONG_EVIDENCE"
        f["verification_evidence"] = evidence[:500] if evidence else f.get("verification_evidence","")
        if source:
            f["verification_source"] = source
    # enforce invariant: status VERIFIED => verified true
    if f["status"] == "VERIFIED" and not f["verified"]:
        f["status"] = "STRONG_EVIDENCE"
    return pack

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--task", default="")
    p.add_argument("--budget", type=int, default=BUDGET_TOKENS)
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or "demo task"
    scout = {"model":"deepseek-v4-flash","provider":"generic","findings":[{"claim":"Potential registry rollback mismatch","status":"STRONG_EVIDENCE","files":[r"src-tauri/src/tweaks/impls/power.rs:42"],"evidence":r"HKLM SYSTEM\Services Start not snapshot","confidence":0.86}], "tokens_in":80,"tokens_out":120,"cost_usd":0.008,"cost_status":"OK","latency_ms":820,"simulated":True}
    print(json.dumps(build_pack(task, scout, budget=args.budget, repo=args.repo), indent=2))
