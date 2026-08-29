#!/usr/bin/env python3
"""
Smart specialist delegation — evidence-driven.
Inputs: risk score, categories, complexity, ambiguity (from task), file count, historical failure rate (optional).
Default: Claude alone. Spawn only when justified.
"""
import json, sys, re

def select(risk: int, categories: list, complexity: str, files: list, ambiguity: bool = False, historical_fail_rate: float = 0.0) -> dict:
    reasons = []
    score = 0

    # risk weight
    if risk >= 75:
        score += 4
        reasons.append(f"risk {risk} critical")
    elif risk >= 50:
        score += 3
        reasons.append(f"risk {risk} high")
    elif risk >= 25:
        score += 1

    # domain high-risk
    high_domains = {"windows","registry","services","security","authentication"}
    if any(c in high_domains for c in categories):
        score += 2
        reasons.append(f"high-risk domain {set(categories)&high_domains}")

    # complexity
    if complexity == "complex":
        score += 2
        reasons.append("complexity complex")
    # ambiguity
    if ambiguity:
        score += 1
        reasons.append("ambiguity high")
    # size
    if len(files) > 8:
        score += 1
        reasons.append(f"large scope {len(files)} files")
    # historical failure rate from learn.py
    if historical_fail_rate >= 0.4:
        score += 2
        reasons.append(f"historical fail rate {historical_fail_rate:.0%}")

    # map category to specialist
    specialist_map = {
        "windows": "sage-windows-specialist",
        "registry": "sage-windows-specialist",
        "services": "sage-windows-specialist",
        "rust": "sage-tauri-rust-specialist",
        "tauri": "sage-tauri-rust-specialist",
        "performance": "sage-performance-specialist",
        "security": "sage-security-specialist",
        "authentication": "sage-security-specialist",
    }
    candidates = []
    for c in categories:
        if c in specialist_map and specialist_map[c] not in candidates:
            candidates.append(specialist_map[c])

    # decision
    # threshold: score >=3 => specialist justified
    if score >= 3 and candidates:
        decision = "specialist"
        # pick highest priority: security > windows > tauri > performance
        priority = ["sage-security-specialist","sage-windows-specialist","sage-tauri-rust-specialist","sage-performance-specialist"]
        chosen = sorted(candidates, key=lambda x: priority.index(x) if x in priority else 99)[0]
        # if multiple high-risk domains, recommend reviewer
        if len(candidates) > 1 and risk >= 50:
            chosen = "sage-reviewer"
            reasons.append("cross-domain → reviewer")
    elif score >= 3 and not candidates:
        decision = "reviewer"
        chosen = "sage-reviewer"
        reasons.append("high score but no domain specialist → reviewer")
    else:
        decision = "claude_alone"
        chosen = None

    return {
        "decision": decision,
        "specialist": chosen,
        "candidates": candidates,
        "score": score,
        "reasons": reasons,
        "threshold": 3,
        "note": "Default Claude alone; score≥3 justifies specialist. Historical fail rate boosts score.",
    }

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--risk", type=int, default=0)
    p.add_argument("--categories", default="")
    p.add_argument("--complexity", default="medium")
    p.add_argument("--files", default="")
    p.add_argument("--ambiguity", action="store_true")
    p.add_argument("--fail-rate", type=float, default=0.0)
    args = p.parse_args()
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    print(json.dumps(select(args.risk, cats, args.complexity, files, args.ambiguity, args.fail_rate), indent=2))
