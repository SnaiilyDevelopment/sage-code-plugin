#!/usr/bin/env python3
"""
Adaptive learning — analyzes .wolf/sage-telemetry.jsonl with recency weighting.
Outputs insights: skill success per category, verification effectiveness, specialist benefit, failure patterns, waste.
Requires confidence threshold before changing behavior; recent data weighted higher (half-life ~30 days).
Does NOT mutate behavior automatically — emits recommendations.
"""
import json, math, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict, Counter

HALF_LIFE_DAYS = 30
CONFIDENCE_MIN_SAMPLES = 5
CONFIDENCE_MIN_RATE = 0.7

def recency_weight(ts_str: str) -> float:
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z","+00:00"))
        now = datetime.now(timezone.utc)
        days = (now - ts).total_seconds() / 86400
        # exp decay: weight = 0.5^(days/half_life)
        return 0.5 ** (max(0, days) / HALF_LIFE_DAYS)
    except:
        return 0.5

def load_entries(repo: Path) -> list:
    p = repo / ".wolf" / "sage-telemetry.jsonl"
    if not p.exists() and not repo.exists():
        p = Path(__file__).resolve().parents[2] / ".wolf" / "sage-telemetry.jsonl"
    elif not (repo / ".wolf" / "sage-telemetry.jsonl").exists():
        # if repo exists but file missing, don't fallback to plugin
        p = repo / ".wolf" / "sage-telemetry.jsonl"
    if not p.exists():
        return []
    entries = []
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip(): continue
        try:
            entries.append(json.loads(line))
        except: continue
    return entries

HARD_CONSTRAINTS = ["security","destructive","secret","permission","dangerous"]

def analyze(entries: list, confidence_threshold: int = CONFIDENCE_MIN_SAMPLES) -> dict:
    if not entries:
        return {"status": "no data", "entries": 0}

    # Weighted stats per category
    cat_stats = defaultdict(lambda: {"total_w": 0, "success_w": 0, "fail_w": 0, "count": 0})
    skill_stats = defaultdict(lambda: {"total_w": 0, "success_w": 0})
    verif_stats = defaultdict(lambda: {"total_w": 0, "caught_w": 0})  # verification that caught issues = failures with that verif
    specialist_stats = {"with_specialist": {"total_w":0, "success_w":0}, "without": {"total_w":0, "success_w":0}}
    failure_causes = Counter()
    waste = {"avg_duration_by_category": defaultdict(list), "retries_by_category": defaultdict(list)}
    # preflight stats — objective signals
    preflight_stats = {"used": 0, "useful": 0, "wrong": 0, "cost": 0.0, "latency": [], "tokens": 0, "accepted": 0, "rejected": 0, "verified": 0, "false_positive": 0}
    scout_by_cat = defaultdict(lambda: {"used":0, "useful":0})
    ab_stats = {"control": {"count":0, "tokens":0, "cost":0.0, "success":0}, "scout": {"count":0, "tokens":0, "cost":0.0, "success":0}}

    for e in entries:
        w = recency_weight(e.get("ts",""))
        cat = e.get("category","general")
        res = e.get("result","unknown")
        success = 1 if res == "success" else 0
        fail = 0 if success else 1

        cat_stats[cat]["total_w"] += w
        cat_stats[cat]["count"] += 1
        if success: cat_stats[cat]["success_w"] += w
        else: cat_stats[cat]["fail_w"] += w

        for s in e.get("skills",[]):
            skill_stats[f"{cat}:{s}"]["total_w"] += w
            if success: skill_stats[f"{cat}:{s}"]["success_w"] += w

        verif = e.get("verification","")
        if verif:
            for v in verif.split(","):
                v=v.strip()
                if not v: continue
                verif_stats[v]["total_w"] += w
                if fail: verif_stats[v]["caught_w"] += w

        has_spec = len(e.get("agents",[])) > 0
        key = "with_specialist" if has_spec else "without"
        specialist_stats[key]["total_w"] += w
        if success: specialist_stats[key]["success_w"] += w

        if e.get("failure_cause"):
            failure_causes[e["failure_cause"]] += 1

        # preflight signals — include objective accepted/rejected
        if e.get("preflight_model"):
            preflight_stats["used"] += 1
            preflight_stats["cost"] += float(e.get("preflight_cost",0) or e.get("estimated_cost",0))
            preflight_stats["tokens"] += int(e.get("preflight_tokens_in",0) or e.get("scout_tokens",0)) + int(e.get("preflight_tokens_out",0))
            preflight_stats["accepted"] += int(e.get("accepted_findings",0))
            preflight_stats["rejected"] += int(e.get("rejected_findings",0))
            preflight_stats["verified"] += int(e.get("verified_findings",0))
            preflight_stats["false_positive"] += int(e.get("false_positive_findings",0))
            if e.get("preflight_latency_ms"):
                preflight_stats["latency"].append(int(e.get("preflight_latency_ms",0)))
            if e.get("preflight_useful") == "yes":
                preflight_stats["useful"] += 1
                scout_by_cat[cat]["useful"] += 1
            if e.get("preflight_wrong") == "yes":
                preflight_stats["wrong"] += 1
            scout_by_cat[cat]["used"] += 1
        # A/B variant
        variant = e.get("variant","")
        if variant in ("control","scout"):
            ab_stats[variant]["count"] += 1
            ab_stats[variant]["tokens"] += int(e.get("total_tokens",0) or (e.get("claude_tokens",0)+e.get("scout_tokens",0)))
            ab_stats[variant]["cost"] += float(e.get("estimated_cost",0) or e.get("preflight_cost",0))
            if e.get("result") == "success":
                ab_stats[variant]["success"] += 1

        waste["avg_duration_by_category"][cat].append(e.get("duration_ms",0))
        waste["retries_by_category"][cat].append(e.get("retries",0))

    # Quality control: check no synthetic, no selection bias, enough samples, not contradictory
    quality_notes = []
    # Weighted count vs raw: require weighted sum too
    weighted_total = sum(recency_weight(e.get("ts","")) for e in entries)
    if len(entries) < confidence_threshold:
        quality_notes.append(f"Insufficient samples ({len(entries)} < {confidence_threshold}) — no policy change")
    if weighted_total < confidence_threshold * 0.5:
        quality_notes.append(f"Insufficient weighted samples ({weighted_total:.1f} < {confidence_threshold*0.5}) — data too old")
    # detect synthetic: all same task_id
    if len(set(e.get("task_id","") for e in entries)) == 1 and len(entries) > 3:
        quality_notes.append("Selection bias: single task_id dominates — not representative")
    # repeated task detection (same task text hash)
    task_hashes = [e.get("task_id","") for e in entries]
    if len(task_hashes) != len(set(task_hashes)) and len(entries) >= 5:
        dup_ratio = 1 - len(set(task_hashes))/len(task_hashes)
        if dup_ratio > 0.5:
            quality_notes.append(f"Repeated tasks: {dup_ratio:.0%} duplicates — not independent evidence")
    # Check for synthetic/weak data labels
    weak_count = sum(1 for e in entries if e.get("synthetic") or e.get("verification") == "unverified")
    if weak_count > len(entries) * 0.5:
        quality_notes.append(f"Weak data: {weak_count}/{len(entries)} unverified/synthetic — exclude from adaptation")

    # Build recommendations with confidence
    recommendations = []
    policy_proposals = []

    for cat, st in cat_stats.items():
        if st["count"] >= confidence_threshold:
            fail_rate = st["fail_w"] / max(1, st["total_w"])
            if fail_rate >= 0.4:
                rec = {
                    "type": "high_failure_category",
                    "category": cat,
                    "fail_rate": round(fail_rate,2),
                    "count": st["count"],
                    "action": f"Increase verification + consider specialist for '{cat}' (fail rate {fail_rate:.0%})"
                }
                recommendations.append(rec)
                # auditable policy proposal
                policy_proposals.append({
                    "CURRENT_POLICY": f"Specialist threshold 3 for {cat}",
                    "EVIDENCE": f"{cat} fail rate {fail_rate:.0%} over {st['count']} samples (weighted), recent-weighted",
                    "PROPOSED_CHANGE": f"Lower specialist threshold for {cat} or require verification for {cat}",
                    "CONFIDENCE": "observed" if st["count"] < 10 else "verified",
                    "THRESHOLD_MET": st["count"] >= confidence_threshold
                })

    for key, st in skill_stats.items():
        if st["total_w"] >= confidence_threshold:
            succ = st["success_w"] / max(1, st["total_w"])
            if succ >= CONFIDENCE_MIN_RATE:
                cat, skill = key.split(":",1)
                recommendations.append({
                    "type": "skill_effective",
                    "category": cat,
                    "skill": skill,
                    "success_rate": round(succ,2),
                    "action": f"Prefer '{skill}' for '{cat}'"
                })

    for v, st in verif_stats.items():
        if st["total_w"] >= 3:
            catch_rate = st["caught_w"] / max(1, st["total_w"])
            if catch_rate >= 0.3:
                recommendations.append({
                    "type": "verification_effective",
                    "verification": v,
                    "catch_rate": round(catch_rate,2),
                    "action": f"Verification '{v}' catches real issues — keep using"
                })

    if failure_causes:
        top = failure_causes.most_common(3)
        for cause, n in top:
            if n >= 3:
                recommendations.append({
                    "type": "repeated_failure",
                    "cause": cause,
                    "count": n,
                    "action": f"Repeated '{cause}' ({n}x) — update relevant skill/memory to address"
                })

    # specialist benefit
    for k in ["with_specialist","without"]:
        st = specialist_stats[k]
        if st["total_w"] >= 3:
            st["success_rate"] = round(st["success_w"]/max(1,st["total_w"]),2)

    # preflight learning signals §15 — never propose weakening hard constraints
    for cat, st in scout_by_cat.items():
        if st["used"] >= confidence_threshold:
            # If cat is hard constraint (security etc), never propose skipping scout via learning alone
            if cat.lower() in HARD_CONSTRAINTS and st["used"] < 20:
                quality_notes.append(f"Hard constraint '{cat}' — scout skip requires manual review even if useful_rate low")
                continue
            useful_rate = st["useful"] / max(1, st["used"])
            if useful_rate < 0.2:
                if cat.lower() in HARD_CONSTRAINTS:
                    recommendations.append({"type": "scout_not_useful_hard_constraint_blocked", "category": cat, "useful_rate": round(useful_rate,2), "action": f"Scout rarely useful for {cat} but hard-constraint — no auto-skip (requires human)"})
                else:
                    recommendations.append({"type": "scout_not_useful", "category": cat, "useful_rate": round(useful_rate,2), "action": f"Scout rarely useful for {cat} ({useful_rate:.0%}) — learn to skip"})
                    policy_proposals.append({"CURRENT_POLICY": f"Scout optional for {cat}", "EVIDENCE": f"scout useful {useful_rate:.0%} over {st['used']} samples", "PROPOSED_CHANGE": f"Skip scout for {cat}", "CONFIDENCE": "observed", "THRESHOLD_MET": True, "auto_applicable": False})
            elif useful_rate > 0.6:
                recommendations.append({"type": "scout_useful", "category": cat, "useful_rate": round(useful_rate,2), "action": f"Scout frequently useful for {cat} — increase recommendation"})
                policy_proposals.append({"CURRENT_POLICY": f"Scout optional for {cat}", "EVIDENCE": f"scout useful {useful_rate:.0%} over {st['used']}", "PROPOSED_CHANGE": f"Strongly recommend scout for {cat}", "CONFIDENCE": "verified", "THRESHOLD_MET": True})

    preflight_summary = {
        "used": preflight_stats["used"],
        "useful": preflight_stats["useful"],
        "wrong": preflight_stats["wrong"],
        "accepted_findings": preflight_stats["accepted"],
        "rejected_findings": preflight_stats["rejected"],
        "verified_findings": preflight_stats["verified"],
        "false_positive_findings": preflight_stats["false_positive"],
        "useful_rate": round(preflight_stats["useful"]/max(1,preflight_stats["used"]),2) if preflight_stats["used"] else 0,
        "wrong_rate": round(preflight_stats["wrong"]/max(1,preflight_stats["used"]),2) if preflight_stats["used"] else 0,
        "verified_rate": round(preflight_stats["verified"]/max(1,preflight_stats["accepted"]+preflight_stats["rejected"]),2) if (preflight_stats["accepted"]+preflight_stats["rejected"]) else 0,
        "total_cost_usd": round(preflight_stats["cost"],4),
        "avg_latency_ms": round(sum(preflight_stats["latency"])/len(preflight_stats["latency"])) if preflight_stats["latency"] else 0,
        "total_tokens": preflight_stats["tokens"]
    }

    # A/B comparison
    ab_comparison = {}
    if ab_stats["control"]["count"] > 0 and ab_stats["scout"]["count"] > 0:
        for k in ["control","scout"]:
            ab_stats[k]["avg_tokens"] = round(ab_stats[k]["tokens"]/ab_stats[k]["count"]) if ab_stats[k]["count"] else 0
            ab_stats[k]["avg_cost"] = round(ab_stats[k]["cost"]/ab_stats[k]["count"],4) if ab_stats[k]["count"] else 0
            ab_stats[k]["success_rate"] = round(ab_stats[k]["success"]/ab_stats[k]["count"],2) if ab_stats[k]["count"] else 0
        ab_comparison = {
            "control": ab_stats["control"],
            "scout": ab_stats["scout"],
            "delta_tokens": ab_stats["scout"]["avg_tokens"] - ab_stats["control"]["avg_tokens"],
            "delta_cost": round(ab_stats["scout"]["avg_cost"] - ab_stats["control"]["avg_cost"],4),
            "delta_success": round(ab_stats["scout"]["success_rate"] - ab_stats["control"]["success_rate"],2),
            "conclusion": "insufficient data for benefit claim" if (ab_stats["control"]["count"]+ab_stats["scout"]["count"] < 10) else ("scout beneficial" if ab_stats["scout"]["success_rate"] > ab_stats["control"]["success_rate"] else "no benefit measured")
        }

    return {
        "entries": len(entries),
        "categories": {k: {"count": v["count"], "fail_rate": round(v["fail_w"]/max(1,v["total_w"]),2)} for k,v in cat_stats.items()},
        "specialist": specialist_stats,
        "top_failures": failure_causes.most_common(5),
        "preflight": preflight_summary,
        "scout_by_category": {k: dict(v) for k,v in scout_by_cat.items()},
        "ab": ab_comparison,
        "ab_raw": ab_stats,
        "recommendations": recommendations,
        "policy_proposals": [p for p in policy_proposals if p.get("CONFIDENCE") in ("verified","high")] if quality_notes else policy_proposals,
        "quality_notes": quality_notes,
        "confidence_threshold": confidence_threshold,
        "half_life_days": HALF_LIFE_DAYS,
        "hard_constraints": HARD_CONSTRAINTS,
        "adaptable": ["skill_selection","scout_usage","verification_priority","specialist_routing","research_selection"],
        "never_auto_weaken": HARD_CONSTRAINTS,
        "note": "Recommendations require confidence_threshold samples; recent data weighted heavier. Policy proposals are auditable: CURRENT POLICY -> EVIDENCE -> PROPOSED CHANGE -> CONFIDENCE. Never weaken security via learning. Hard constraints require human approval.",
        "rollback_note": "Use scripts/policy/policy.py --history / --rollback to audit/rollback."
    }

if __name__ == "__main__":
    import argparse, json
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default=".")
    p.add_argument("--threshold", type=int, default=CONFIDENCE_MIN_SAMPLES)
    args = p.parse_args()
    entries = load_entries(Path(args.repo))
    out = analyze(entries, args.threshold)
    print(json.dumps(out, indent=2))
