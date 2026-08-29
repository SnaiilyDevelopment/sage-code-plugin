#!/usr/bin/env python3
"""
Self-diagnostics — trustworthy actual state, not policy claims.
Shows SIMULATED vs REAL for preflight.
"""
import json, subprocess, sys
from pathlib import Path

def _run(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return json.loads(r.stdout) if r.stdout.strip().startswith("{") or r.stdout.strip().startswith("[") else {"raw": r.stdout[:2000], "stderr": r.stderr[:500]}
    except Exception as e:
        return {"error": str(e)[:300], "error_type": "UNKNOWN"}

def diagnose(task: str, categories: str = "", files: str = "", risk: int = -1, repo: str = "."):
    repo_path = Path(repo)
    out = {"task": task, "diagnostics": {}}
    # classify
    cr = _run(["python", str(Path(__file__).resolve().parents[1] / "context/classify.py"), task, "--files", files] if files else ["python", str(Path(__file__).resolve().parents[1] / "context/classify.py"), task], timeout=5)
    if "error" in cr and "categories" not in cr:
        out["diagnostics"]["classification_error"] = cr
        cats = categories
        comp = "medium"
        cats_list = [c.strip() for c in cats.split(",") if c.strip()]
    else:
        out["diagnostics"]["classification"] = cr
        cats = ",".join(cr.get("categories",[]))
        cats_list = cr.get("categories",[])
        comp = cr.get("complexity","medium")

    # risk
    if risk < 0:
        rr = _run(["python", str(Path(__file__).resolve().parents[1] / "safety/risk-score.py"), task, "--files", files, "--complexity", comp] if files else ["python", str(Path(__file__).resolve().parents[1] / "safety/risk-score.py"), task, "--complexity", comp], timeout=5)
    else:
        rr = {"risk_score": risk, "tier": "manual"}
    out["diagnostics"]["risk"] = rr
    rs = rr.get("risk_score", 0)

    # skills
    out["diagnostics"]["skills"] = _run(["python", str(Path(__file__).resolve().parents[1] / "context/skill-select.py"), task, "--categories", cats, "--files", files] if files else ["python", str(Path(__file__).resolve().parents[1] / "context/skill-select.py"), task, "--categories", cats], timeout=5)

    # specialist
    out["diagnostics"]["specialist"] = _run(["python", str(Path(__file__).resolve().parents[1] / "context/specialist-select.py"), "--risk", str(rs), "--categories", cats, "--complexity", comp, "--files", files], timeout=5)

    # mcp
    out["diagnostics"]["mcp"] = _run(["python", str(Path(__file__).resolve().parents[1] / "mcp/select.py"), task, "--categories", cats], timeout=5)

    # preflight — real
    pre = _run(["python", str(Path(__file__).resolve().parents[1] / "routing/preflight.py"), task, "--categories", cats, "--files", files, "--complexity", comp], timeout=10)
    out["diagnostics"]["preflight"] = pre
    scout = pre.get("scout") if isinstance(pre, dict) else None
    if isinstance(pre, dict) and pre.get("scout"):
        try:
            import importlib.util as _ilu
            ev_path = Path(__file__).resolve().parents[1] / "routing/evidence.py"
            spec_ev = _ilu.spec_from_file_location("ev", str(ev_path))
            mod_ev = _ilu.module_from_spec(spec_ev)
            spec_ev.loader.exec_module(mod_ev)
            # Pass repo for fabricated check and actual budget
            pol_pre = pre.get("preflight_config",{})
            budget = pol_pre.get("max_total_tokens", pol_pre.get("budget_tokens",800))
            pack = mod_ev.build_pack(task, pre.get("scout") or {}, [], budget=budget, repo=str(repo_path))
            out["diagnostics"]["evidence_pack"] = pack
            out["diagnostics"]["evidence_pack_tokens"] = pack.get("size_tokens_est",0)
            out["diagnostics"]["evidence_pack_budget"] = budget
        except Exception as e:
            out["diagnostics"]["evidence_pack_error"] = str(e)[:500]

    # context budget actual
    try:
        import importlib.util as _ilu2
        cb_path = Path(__file__).resolve().parents[1] / "context/context-build.py"
        spec_cb = _ilu2.spec_from_file_location("cb", str(cb_path))
        mod_cb = _ilu2.module_from_spec(spec_cb)
        spec_cb.loader.exec_module(mod_cb)
        ctx = mod_cb.build(task, cats_list, [f.strip() for f in files.split(",") if f.strip()], budget_tokens=None, repo=repo_path)
        out["diagnostics"]["context"] = {"budget_total": ctx.get("budget_total"), "budget_used": ctx.get("budget_used"), "budget_remaining": ctx.get("budget_remaining"), "layers": ctx.get("_budget_layers",[])[:4]}
    except Exception as e:
        out["diagnostics"]["context_error"] = str(e)[:500]

    # verification
    out["diagnostics"]["verification"] = cr.get("verification",[]) if isinstance(cr, dict) else []

    # memory — with status
    try:
        import importlib.util
        mem_path = Path(__file__).resolve().parents[2] / "scripts/memory/memory.py"
        spec = importlib.util.spec_from_file_location("mem", str(mem_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mem_status = mod.load_with_status(repo_path)
        mem = mem_status["data"].get("items",[])
        out["diagnostics"]["memory"] = {"status": mem_status["status"], "path": mem_status["path"], "items": len(mem), "sample": [f"{x['fact']} ({x['confidence']})" for x in mem[:2]]}
        if mem_status["status"] == "MEMORY_CORRUPTED":
            out["diagnostics"]["memory"]["error"] = mem_status.get("error","")
    except Exception as e:
        out["diagnostics"]["memory_error"] = str(e)[:500]

    # telemetry/learn
    out["diagnostics"]["learning"] = _run(["python", str(Path(__file__).resolve().parents[1] / "telemetry/learn.py"), "--repo", str(repo_path), "--threshold", "5"], timeout=5)

    # policy
    pol = _run(["python", str(Path(__file__).resolve().parents[1] / "policy/policy.py"), "--show", "--repo", str(repo_path)], timeout=5)
    out["diagnostics"]["policy"] = pol

    scout_info = scout or {}
    status_map = {"NO_PROVIDER":"NO_PROVIDER","HEURISTIC_ONLY":"HEURISTIC_ONLY","REAL_MODEL":"REAL_MODEL","FAILED":"FAILED","REFUSED_BUDGET_EXCEEDED":"REFUSED_BUDGET_EXCEEDED","SIMULATED":"SIMULATED_TEST","SIMULATED_TEST":"SIMULATED_TEST"}
    raw_status = scout_info.get("status","") if isinstance(scout_info, dict) else ""
    heuristic = scout_info.get("heuristic", False) if isinstance(scout_info, dict) else False
    if raw_status in status_map:
        status_label = status_map[raw_status]
    elif heuristic:
        status_label = "HEURISTIC"
    elif scout_info.get("simulated"):
        status_label = "SIMULATED_TEST"
    elif raw_status=="OK":
        status_label = "REAL_MODEL"
    else:
        status_label = raw_status or "NO_PROVIDER" if not scout_info else "HEURISTIC/UNAVAILABLE"

    pre_info = out["diagnostics"].get("preflight",{})
    scout = pre_info.get("scout") if isinstance(pre_info, dict) else None
    if not isinstance(scout, dict): scout = {}

    out["answers"] = {
        "Task": task[:200],
        "Classification": f"{cats} / {comp}",
        "Risk": f"{rs} ({rr.get('tier','') if isinstance(rr,dict) else ''})",
        "Scout used?": pre_info.get("routing",{}).get("decision","NO") if isinstance(pre_info, dict) else "NO",
        "Scout model": scout.get("model","-"),
        "Scout status": status_label,
        "Scout input tokens": scout.get("tokens_in",0),
        "Scout output tokens": scout.get("tokens_out",0),
        "Scout cost": scout.get("cost_usd", None),
        "Scout cost_status": scout.get("cost_status","UNKNOWN"),
        "Scout latency_ms": scout.get("latency_ms",0),
        "Findings": len(out["diagnostics"].get("evidence_pack",{}).get("findings",[])) if "evidence_pack" in out["diagnostics"] else 0,
        "Accepted findings": "see telemetry log --accepted-findings",
        "Rejected findings": "see telemetry",
        "Verified findings": len([f for f in out["diagnostics"].get("evidence_pack",{}).get("findings",[]) if f.get("verified")]) if "evidence_pack" in out["diagnostics"] else 0,
        "Skills": str(out["diagnostics"].get("skills",{}).get("selected","?")),
        "Which skills were selected?": str(out["diagnostics"].get("skills",{}).get("selected","?")),
        "Why specialist?": str(out["diagnostics"].get("specialist",{}).get("reasons","?")),
        "Why MCP?": out["diagnostics"].get("mcp",{}).get("recommendation","?"),
        "Which verification?": str(out["diagnostics"].get("verification","?")),
        "What did Sage decide?": f"Category {cats}, complexity {comp}, risk {rs}",
        "Why?": f"Risk {rs} + categories {cats} + complexity {comp}",
        "What did system learn?": f"{len(out['diagnostics'].get('learning',{}).get('recommendations',[]))} recommendations",
        "What memory changed?": f"{out['diagnostics'].get('memory',{}).get('items',0)} items",
        "Specialist": str(out["diagnostics"].get("specialist",{}).get("decision","?")),
        "MCP": out["diagnostics"].get("mcp",{}).get("recommendation","?"),
        "Context tokens": f"{out['diagnostics'].get('context',{}).get('budget_used','?')}/{out['diagnostics'].get('context',{}).get('budget_total','?')} remaining {out['diagnostics'].get('context',{}).get('budget_remaining','?')}",
        "Verification": str(out["diagnostics"].get("verification","?")),
        "Learning changes": f"{len(out['diagnostics'].get('learning',{}).get('recommendations',[]))} recommendations, hard_constraints {out['diagnostics'].get('learning',{}).get('hard_constraints','')}",
        "Memory changes": f"{out['diagnostics'].get('memory',{}).get('items',0)} items @ {out['diagnostics'].get('memory',{}).get('path','')} [{out['diagnostics'].get('memory',{}).get('status','')}]",
        "Policy version": out["diagnostics"].get("policy",{}).get("version","?"),
    }
    if status_label in ("SIMULATED_TEST","NO_PROVIDER","HEURISTIC"):
        out["answers"]["_warning"] = "Scout was heuristic/NO_PROVIDER (no API key) — not REAL_MODEL. Set SAGE_PREFLIGHT_API_KEY/GLM_API_KEY for real test."
    return out

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task")
    p.add_argument("--categories", default="")
    p.add_argument("--files", default="")
    p.add_argument("--risk", type=int, default=-1)
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or "unknown"
    print(json.dumps(diagnose(task, args.categories, args.files, args.risk, args.repo), indent=2))
