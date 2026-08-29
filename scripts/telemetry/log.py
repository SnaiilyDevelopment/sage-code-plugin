#!/usr/bin/env python3
"""
Enhanced telemetry — appends JSONL to .wolf/sage-telemetry.jsonl (git-ignored).
V1.1: task_id, category/complexity/risk, files, skills/agents/tools, MCP, verification, outcome, failures, duration, memory_updates, lesson.
Never records secrets; uses secret-strip.
"""
import json, sys, re, uuid
from pathlib import Path
from datetime import datetime, timezone

# Import secret strip patterns
try:
    from scripts.safety.secret_strip import strip as strip_text
except:
    def strip_text(t): return t

SENSITIVE_RE = re.compile(r"secret|token|key|license\.dat|hwid\.dat|supabase.*service_role|stripe_secret|private_key|credentials", re.I)

def strip_secrets_obj(obj: dict) -> dict:
    for k,v in list(obj.items()):
        if isinstance(v, str) and SENSITIVE_RE.search(v):
            obj[k] = "[REDACTED]"
        elif isinstance(v, str) and len(v) > 200 and any(x in v.lower() for x in ["sk-", "bearer"]):
            obj[k] = "[REDACTED]"
        elif isinstance(v, list):
            obj[k] = [("[REDACTED]" if isinstance(x,str) and SENSITIVE_RE.search(x) else x) for x in v]
    # also strip inside nested strings via strip_text for verification/tools
    for k in ["verification","tools","lesson","failure_cause"]:
        if k in obj and isinstance(obj[k], str):
            obj[k] = strip_text(obj[k]) if len(obj[k]) < 5000 else "[TRUNCATED]"
    return obj

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--task-id", default="")
    p.add_argument("--command", default="unknown")
    p.add_argument("--category", default="general")
    p.add_argument("--complexity", default="medium")
    p.add_argument("--risk", type=int, default=0)
    p.add_argument("--files", default="")
    p.add_argument("--skills", default="")
    p.add_argument("--agents", default="")
    p.add_argument("--tools", default="")
    p.add_argument("--mcp", default="", help="comma list of MCP servers used")
    p.add_argument("--verification", default="")
    p.add_argument("--result", default="unknown", help="success|failure|inconclusive")
    p.add_argument("--failure-cause", default="", help="classified failure cause")
    p.add_argument("--retries", type=int, default=0)
    p.add_argument("--review-required", default="false")
    p.add_argument("--duration-ms", type=int, default=0)
    p.add_argument("--lesson", default="")
    p.add_argument("--memory-updates", default="")
    p.add_argument("--preflight-model", default="", help="scout model used")
    p.add_argument("--preflight-provider", default="")
    p.add_argument("--preflight-cost", type=float, default=0.0)
    p.add_argument("--preflight-latency", type=int, default=0)
    p.add_argument("--preflight-tokens-in", type=int, default=0)
    p.add_argument("--preflight-tokens-out", type=int, default=0)
    p.add_argument("--preflight-useful", default="", help="yes/no/unknown")
    p.add_argument("--preflight-wrong", default="", help="yes/no")
    p.add_argument("--repo", default=".")
    args = p.parse_args()

    task_id = args.task_id or str(uuid.uuid4())[:8]
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "task_id": task_id,
        "command": args.command,
        "category": args.category,
        "complexity": args.complexity,
        "risk": args.risk,
        "files_touched": [s.strip() for s in args.files.split(",") if s.strip()],
        "skills": [s.strip() for s in args.skills.split(",") if s.strip()],
        "agents": [s.strip() for s in args.agents.split(",") if s.strip()],
        "tools": [s.strip() for s in args.tools.split(",") if s.strip()],
        "mcp_usage": [s.strip() for s in args.mcp.split(",") if s.strip()],
        "verification": args.verification,
        "result": args.result,
        "failure_cause": args.failure_cause,
        "retries": args.retries,
        "review_required": args.review_required.lower() in ("true","1","yes"),
        "duration_ms": args.duration_ms,
        "lesson": args.lesson[:500],
        "memory_updates": [s.strip() for s in args.memory_updates.split(",") if s.strip()],
        "preflight_model": args.preflight_model,
        "preflight_provider": args.preflight_provider,
        "preflight_cost": args.preflight_cost,
        "preflight_latency_ms": args.preflight_latency,
        "preflight_tokens_in": args.preflight_tokens_in,
        "preflight_tokens_out": args.preflight_tokens_out,
        "preflight_useful": args.preflight_useful,
        "preflight_wrong": args.preflight_wrong,
    }
    entry = strip_secrets_obj(entry)

    repo = Path(args.repo)
    out = repo / ".wolf" / "sage-telemetry.jsonl"
    if not repo.exists() or not (repo / ".git").exists():
        out = Path(__file__).resolve().parents[2] / ".wolf" / "sage-telemetry.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry, indent=2))
    print(f"# logged to {out}", file=sys.stderr)

if __name__ == "__main__":
    main()
