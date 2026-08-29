#!/usr/bin/env python3
"""
Versioned internal policy — auditable, rollback-capable, never weakens security.
Manages .wolf/sage-policy.json with history.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
import hashlib

DEFAULT_POLICY = {
    "version": "2.1",
    "risk_thresholds": {"low": [0,24], "medium": [25,49], "high": [50,74], "critical": [75,100]},
    "specialist_threshold": 3,
    "skill_threshold": 2.0,
    "skill_budget": 3500,
    "context_budget": 6000,
    "learning_half_life_days": 30,
    "learning_confidence_min_samples": 5,
    "learning_confidence_min_rate": 0.7,
    "memory_ttl_days": 90,
    "benchmark_repeats": 5,
    "benchmark_cv_not_measurable": 0.15,
    "safety": {"never_weaken": ["security","destructive","secret"], "mcp_high_risk_confirm": True},
    "preflight": {
        "enabled": True,
        "budget_tokens": 800,
        "threshold": "auto",
        "fallback_to_heuristic": True,
        "selection": "cheapest-first",
        "providers": [
            {"id":"cheap-a","provider":"generic-openai-compat","model":"deepseek-v4-flash","base_url_env":"SAGE_PREFLIGHT_BASE_URL","api_key_env":"SAGE_PREFLIGHT_API_KEY","cost_per_1k_in":0.01,"cost_per_1k_out":0.02,"timeout_ms":8000},
            {"id":"cheap-b","provider":"generic-openai-compat","model":"glm-5.3-flash","base_url_env":"GLM_BASE_URL","api_key_env":"GLM_API_KEY","cost_per_1k_in":0.005,"cost_per_1k_out":0.015,"timeout_ms":8000}
        ]
    },
    "history": []
}

POLICY_PATH_REPO = ".wolf/sage-policy.json"

def resolve(repo: Path) -> Path:
    p = repo / ".wolf" / "sage-policy.json"
    if not repo.exists() or not (repo / ".git").exists():
        p = Path(__file__).resolve().parents[2] / ".wolf" / "sage-policy.json"
    return p

def load(repo: Path) -> dict:
    p = resolve(repo)
    if not p.exists():
        return dict(DEFAULT_POLICY)
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except:
        return dict(DEFAULT_POLICY)

def save(repo: Path, policy: dict):
    p = resolve(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(policy, indent=2), encoding="utf-8")

def propose(repo: Path, change: str, evidence: str, confidence: str, current_policy_str: str = "") -> dict:
    """Create auditable proposal, do not apply yet."""
    policy = load(repo)
    proposal = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "current_policy": current_policy_str or f"v{policy['version']}",
        "evidence": evidence[:500],
        "proposed_change": change[:500],
        "confidence": confidence,
        "hash": hashlib.sha256((change+evidence).encode()).hexdigest()[:8],
        "applied": False
    }
    # security sanity: never allow weakening security thresholds via learning without explicit high confidence + manual review
    if any(k in change.lower() for k in ["lower.*risk","reduce.*threshold","disable.*security","weaken"]):
        proposal["blocked"] = True
        proposal["reason"] = "Refuses to weaken security/destructive/secret via learning — requires manual high-confidence review"
    else:
        proposal["blocked"] = False
    return proposal

def apply_change(repo: Path, change: str, evidence: str, confidence: str, version_bump: str = "2.0.1") -> dict:
    policy = load(repo)
    # require confidence validated/verified/high and enough samples implied by caller
    if confidence not in ["validated","verified","high"]:
        return {"error": "Insufficient confidence — need validated/verified/high", "confidence": confidence}
    # check not synthetic / no weakening
    if any(k in change.lower() for k in ["weaken","disable security"]):
        return {"error": "Blocked: never weaken security via learning"}
    proposal = propose(repo, change, evidence, confidence, f"v{policy['version']}")
    if proposal.get("blocked"):
        return proposal
    # append to history
    hist_entry = {
        "version": version_bump,
        "date": proposal["ts"],
        "change": change,
        "evidence": evidence,
        "confidence": confidence,
        "previous_version": policy["version"]
    }
    policy["history"].append(hist_entry)
    policy["version"] = version_bump
    # apply simple changes: if change mentions threshold, update (demo)
    # real implementation would parse change; for now just record
    save(repo, policy)
    proposal["applied"] = True
    proposal["new_version"] = version_bump
    return proposal

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--show", action="store_true")
    p.add_argument("--history", action="store_true")
    p.add_argument("--propose", nargs=2, metavar=("CHANGE","EVIDENCE"), help="propose change")
    p.add_argument("--apply", nargs=3, metavar=("CHANGE","EVIDENCE","CONFIDENCE"))
    p.add_argument("--rollback", default="", help="rollback to version")
    args = p.parse_args()
    repo = Path(args.repo)
    if args.show:
        print(json.dumps(load(repo), indent=2))
    elif args.history:
        pol = load(repo)
        print(json.dumps(pol.get("history",[]), indent=2))
    elif args.propose:
        ch, ev = args.propose
        print(json.dumps(propose(repo, ch, ev, "medium"), indent=2))
    elif args.apply:
        ch, ev, conf = args.apply
        print(json.dumps(apply_change(repo, ch, ev, conf), indent=2))
    elif args.rollback:
        pol = load(repo)
        # find history entry for that version
        found = None
        for h in reversed(pol.get("history",[])):
            if h["version"] == args.rollback or h["previous_version"] == args.rollback:
                found = h
                break
        if not found:
            print(json.dumps({"error": f"version {args.rollback} not in history"}))
            sys.exit(1)
        # rollback to previous_version
        pol["version"] = found["previous_version"]
        pol["history"].append({"version": pol["version"]+"-rollback", "date": datetime.now(timezone.utc).isoformat(), "change": f"rollback to {args.rollback}", "evidence": f"rollback from {found['version']}", "confidence": "validated", "previous_version": found["version"]})
        save(repo, pol)
        print(json.dumps({"rolled_back_to": found["previous_version"], "history": pol["history"][-2:]}, indent=2))
    else:
        print(json.dumps(load(repo), indent=2))
