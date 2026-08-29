#!/usr/bin/env python3
"""Budget reservation system for scout calls."""
import json, uuid, time
from pathlib import Path
from datetime import datetime, timezone
try:
    from scripts.routing.tokens import estimate_tokens, calc_cost
except:
    import importlib.util as _ilu
    _tp = Path(__file__).parent / "tokens.py"
    _spec = _ilu.spec_from_file_location("tokens", str(_tp))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    estimate_tokens = _mod.estimate_tokens
    calc_cost = _mod.calc_cost

def check_budget(task: str, evidence_text: str, provider: dict, policy: dict) -> dict:
    """Before making scout request: estimate input, check budgets, return reservation or refusal."""
    pre = policy.get("preflight", {})
    max_in = pre.get("max_input_tokens", 600)
    max_out = pre.get("max_output_tokens", 800)
    max_total = pre.get("max_total_tokens", pre.get("budget_tokens", 800))
    max_cost = pre.get("max_cost_usd", 0.05)
    timeout_ms = pre.get("timeout_ms", 8000)

    # estimate input tokens: task + evidence + system prompt overhead (~200 tokens)
    evidence_tokens = estimate_tokens(evidence_text) if evidence_text else 0
    task_tokens = estimate_tokens(task)
    system_overhead = 200
    est_input = task_tokens + evidence_tokens + system_overhead
    est_output = max_out  # reserve max
    est_total = est_input + est_output

    cost_info = calc_cost(est_input, est_output, provider)
    est_cost = cost_info["cost_usd"]  # None if UNKNOWN

    reasons = []
    refused = False
    if est_input > max_in:
        reasons.append(f"estimated input {est_input} > max_input_tokens {max_in}")
        refused = True
    if est_total > max_total:
        reasons.append(f"estimated total {est_total} > max_total_tokens {max_total}")
        refused = True
    if est_cost is not None and est_cost > max_cost:
        reasons.append(f"estimated cost ${est_cost:.4f} > max_cost_usd ${max_cost}")
        refused = True

    reservation = {
        "id": str(uuid.uuid4())[:8],
        "ts": datetime.now(timezone.utc).isoformat(),
        "estimated_input_tokens": est_input,
        "estimated_output_tokens": est_output,
        "estimated_total_tokens": est_total,
        "estimated_cost_usd": est_cost,
        "cost_status": cost_info["cost_status"],
        "provider": provider.get("id",""),
        "model": provider.get("model",""),
        "max_input_tokens": max_in,
        "max_output_tokens": max_out,
        "max_total_tokens": max_total,
        "max_cost_usd": max_cost,
        "timeout_ms": timeout_ms,
        "refused": refused,
        "refusal_reasons": reasons,
    }
    return reservation

def finalize_reservation(reservation: dict, actual_in: int, actual_out: int, provider: dict) -> dict:
    cost_info = calc_cost(actual_in, actual_out, provider)
    reservation["actual_input_tokens"] = actual_in
    reservation["actual_output_tokens"] = actual_out
    reservation["actual_total_tokens"] = actual_in + actual_out
    reservation["actual_cost_usd"] = cost_info["cost_usd"]
    reservation["actual_cost_status"] = cost_info["cost_status"]
    if cost_info["cost_usd"] is not None and reservation.get("estimated_cost_usd") is not None:
        reservation["unused_cost_reserved"] = round(max(0, reservation["estimated_cost_usd"] - cost_info["cost_usd"]), 6)
    else:
        reservation["unused_cost_reserved"] = None
    reservation["released"] = True
    return reservation
