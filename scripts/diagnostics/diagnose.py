#!/usr/bin/env python3
"""
Self-diagnostics — answers: What did Sage decide? Why? Which skills? Why specialist? Why MCP? Which verification? What failed? What learned? What memory changed?
"""
import json, subprocess
from pathlib import Path

def diagnose(task: str, categories: str = "", files: str = "", risk: int = -1, repo: str = "."):
    repo_path = Path(repo)
    out = {"task": task, "diagnostics": {}}

    # classify
    try:
        r = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "context/classify.py"), task, "--files", files] if files else ["python", str(Path(__file__).resolve().parents[1] / "context/classify.py"), task], capture_output=True, text=True, timeout=5)
        cr = json.loads(r.stdout)
        out["diagnostics"]["classification"] = cr
        cats = ",".join(cr.get("categories",[]))
        comp = cr.get("complexity","medium")
    except Exception as e:
        out["diagnostics"]["classification_error"] = str(e)
        cats = categories
        comp = "medium"

    # risk
    try:
        if risk < 0:
            r2 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "safety/risk-score.py"), task, "--files", files, "--complexity", comp] if files else ["python", str(Path(__file__).resolve().parents[1] / "safety/risk-score.py"), task, "--complexity", comp], capture_output=True, text=True, timeout=5)
            rr = json.loads(r2.stdout)
        else:
            rr = {"risk_score": risk}
        out["diagnostics"]["risk"] = rr
        rs = rr.get("risk_score", 0)
    except Exception as e:
        out["diagnostics"]["risk_error"] = str(e)
        rs = risk if risk>=0 else 0

    # skills
    try:
        r3 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "context/skill-select.py"), task, "--categories", cats, "--files", files] if files else ["python", str(Path(__file__).resolve().parents[1] / "context/skill-select.py"), task, "--categories", cats], capture_output=True, text=True, timeout=5)
        out["diagnostics"]["skills"] = json.loads(r3.stdout)
    except Exception as e:
        out["diagnostics"]["skills_error"] = str(e)

    # specialist
    try:
        r4 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "context/specialist-select.py"), "--risk", str(rs), "--categories", cats, "--complexity", comp, "--files", files], capture_output=True, text=True, timeout=5)
        out["diagnostics"]["specialist"] = json.loads(r4.stdout)
    except Exception as e:
        out["diagnostics"]["specialist_error"] = str(e)

    # mcp
    try:
        r5 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "mcp/select.py"), task, "--categories", cats], capture_output=True, text=True, timeout=5)
        out["diagnostics"]["mcp"] = json.loads(r5.stdout)
    except Exception as e:
        out["diagnostics"]["mcp_error"] = str(e)

    # preflight
    try:
        r_pre = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "routing/preflight.py"), task, "--categories", cats, "--files", files, "--complexity", comp], capture_output=True, text=True, timeout=8)
        pre = json.loads(r_pre.stdout)
        out["diagnostics"]["preflight"] = pre
        # also build pack if scout ran
        if pre.get("scout"):
            import importlib.util as _ilu
            ev_path = Path(__file__).resolve().parents[1] / "routing/evidence.py"
            spec_ev = _ilu.spec_from_file_location("ev", str(ev_path))
            mod_ev = _ilu.module_from_spec(spec_ev)
            spec_ev.loader.exec_module(mod_ev)
            pack = mod_ev.build_pack(task, pre.get("scout") or {}, pre.get("scout",{}).get("findings") and [] or [])
            out["diagnostics"]["evidence_pack"] = pack
            out["diagnostics"]["evidence_pack_tokens"] = pack.get("size_tokens_est",0)
    except Exception as e:
        out["diagnostics"]["preflight_error"] = str(e)

    # verification (from classify)
    out["diagnostics"]["verification"] = cr.get("verification",[]) if 'cr' in locals() else []
    # memory
    try:
        import importlib.util
        mem_path = Path(__file__).resolve().parents[2] / "scripts/memory/memory.py"
        spec = importlib.util.spec_from_file_location("mem", str(mem_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mem = mod.get_valid(repo_path, "")
        out["diagnostics"]["memory_items"] = len(mem)
        out["diagnostics"]["memory_sample"] = [f"{x['fact']} ({x['confidence']})" for x in mem[:2]]
    except Exception as e:
        out["diagnostics"]["memory_error"] = str(e)

    # telemetry/learn
    try:
        r6 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "telemetry/learn.py"), "--repo", str(repo_path), "--threshold", "5"], capture_output=True, text=True, timeout=5)
        out["diagnostics"]["learning"] = json.loads(r6.stdout)
    except Exception as e:
        out["diagnostics"]["learning_error"] = str(e)

    # policy
    try:
        r7 = subprocess.run(["python", str(Path(__file__).resolve().parents[1] / "policy/policy.py"), "--show", "--repo", str(repo_path)], capture_output=True, text=True, timeout=5)
        out["diagnostics"]["policy"] = json.loads(r7.stdout)
    except Exception as e:
        out["diagnostics"]["policy_error"] = str(e)

    pre_info = out["diagnostics"].get("preflight",{})
    scout = pre_info.get("scout") or {}
    # plain answers
    out["answers"] = {
        "What did Sage decide?": f"Category {cats}, complexity {comp}, risk {rs}, decision {out['diagnostics'].get('specialist',{}).get('decision','unknown')}",
        "Why?": f"Risk {rs} + categories {cats} + complexity {comp} → specialist score {out['diagnostics'].get('specialist',{}).get('score','?')}",
        "Which skills were selected?": str(out["diagnostics"].get("skills",{}).get("selected","?")),
        "Why specialist?": str(out["diagnostics"].get("specialist",{}).get("reasons","?")),
        "Why MCP?": out["diagnostics"].get("mcp",{}).get("recommendation","?"),
        "Which verification?": str(out["diagnostics"].get("verification","?")),
        "Scout used": pre_info.get("routing",{}).get("decision","NO") if pre_info else "NO",
        "Scout model": scout.get("model","-") if scout else "-",
        "Scout why": pre_info.get("routing",{}).get("reason","-") if pre_info else "-",
        "Scout cost": scout.get("cost_usd",0) if scout else 0,
        "Useful findings": len(out["diagnostics"].get("evidence_pack",{}).get("findings",[])) if "evidence_pack" in out["diagnostics"] else 0,
        "Evidence pack tokens": out["diagnostics"].get("evidence_pack_tokens",0) if "evidence_pack_tokens" in out["diagnostics"] else 0,
        "What did system learn?": f"{len(out['diagnostics'].get('learning',{}).get('recommendations',[]))} recommendations from {out['diagnostics'].get('learning',{}).get('entries','?')} entries",
        "What memory changed?": f"{out['diagnostics'].get('memory_items',0)} durable items",
        "Policy version": out["diagnostics"].get("policy",{}).get("version","?")
    }
    return out

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task")
    p.add_argument("--categories", default="")
    p.add_argument("--files", default="")
    p.add_argument("--risk", type=int, default=-1)
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or "unknown"
    print(json.dumps(diagnose(task, args.categories, args.files, args.risk, args.repo), indent=2))
