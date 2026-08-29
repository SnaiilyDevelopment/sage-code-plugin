#!/usr/bin/env python3
"""
Intelligent context builder — V1.1 with budget, validated memory, deduplication.
Prioritizes: 1 task, 2 repo map, 3 relevant files, 4 skills, 5 tool results, 6 validated memory, 7 prior findings.
Avoids duplicate files/summaries/irrelevant history/giant dumps/repeated discovery.
"""
import json, sys
from pathlib import Path

# Reuse skill selection logic
try:
    from scripts.context.skill_select import select as skill_select_fn, SKILLS
except:
    # fallback import via file
    import importlib.util
    spec = importlib.util.spec_from_file_location("skill_select", str(Path(__file__).parent / "skill-select.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    skill_select_fn = mod.select
    SKILLS = mod.SKILLS

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def build(task: str, categories: list[str], files: list[str], skill_hint: str = "", tool_output: str = "", prior_state: str = "", budget_tokens: int = 6000, repo: Path = None) -> dict:
    layers = {}
    budget_remaining = budget_tokens

    # L1 task — always, ~200 tokens
    layers["1_task"] = task[:2000]
    budget_remaining -= estimate_tokens(layers["1_task"])

    # L2 repo map — truncated to budget
    plugin_root = Path(__file__).resolve().parents[2]
    arch = plugin_root / "references" / "sage-architecture.md"
    if arch.exists():
        txt = arch.read_text(encoding="utf-8", errors="ignore")
        # Respect budget: allocate ~1200 tokens max for map
        max_chars = min(4000, budget_remaining // 2)
        layers["2_repo_map"] = txt[:max_chars]
        budget_remaining -= estimate_tokens(layers["2_repo_map"])
        layers["2_repo_map_source"] = "references/sage-architecture.md + .wolf/sage-map.json (hash-guarded)"
    else:
        layers["2_repo_map"] = "(run scripts/context/repo-map.py to generate)"
        layers["2_repo_map_source"] = "missing"

    # L3 relevant files — symbol-level, budget-aware
    if files:
        # dedupe
        uniq = list(dict.fromkeys(files))
        # cap to 8 files within budget
        max_files = min(len(uniq), max(1, budget_remaining // 400))
        layers["3_relevant_files"] = {
            "hint": "Read these symbol-level first; full read only if needed",
            "files": uniq[:max_files],
            "note": "Use Grep before full Read. Avoid duplicate reads.",
            "deduped": len(files) - len(uniq),
        }
        budget_remaining -= estimate_tokens(json.dumps(layers["3_relevant_files"]))
    else:
        layers["3_relevant_files"] = {"hint": "No files yet — inspect repo map to locate candidates", "categories": categories}

    # L4 skills — relevance-based via skill_select, with budget
    remaining_budget = max(800, budget_remaining // 2)
    selected = skill_select_fn(task, categories, files, budget=remaining_budget)
    # skill_hint boost
    if skill_hint and skill_hint not in selected:
        selected.append(skill_hint)
    # dedupe, ensure sage-core first
    selected = list(dict.fromkeys(selected))
    if "skills/sage-core/SKILL.md" in selected:
        selected.remove("skills/sage-core/SKILL.md")
        selected = ["skills/sage-core/SKILL.md"] + selected
    layers["4_skills"] = selected
    layers["4_skills_budget"] = remaining_budget
    layers["4_skills_explain"] = "Relevance-scored; threshold 2.0; always sage-core; respects token budget"
    budget_remaining -= sum(SKILLS.get(s, {}).get("tokens", 500) for s in selected)

    # L5 tool output — truncated, lowest priority if overflow
    if tool_output:
        # keep last 4000 chars, but respect budget
        max_tool = min(4000, max(500, budget_remaining * 4))
        layers["5_tool_output"] = tool_output[-max_tool:]
        layers["5_tool_output_source"] = "recent tool results"
    else:
        layers["5_tool_output"] = "(none yet)"

    # L6 validated memory — include only relevant category items, capped
    try:
        repo_path = repo or Path.cwd()
        # dynamic import to avoid sys.path issues
        import importlib.util
        mem_path = plugin_root / "scripts" / "memory" / "memory.py"
        spec2 = importlib.util.spec_from_file_location("sage_memory", str(mem_path))
        mem_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mem_mod)
        get_mem = mem_mod.get_valid
        mem_items = []
        for cat in set(categories + ["general"]):
            mem_items.extend(get_mem(repo_path, cat))
        if not mem_items:
            mem_items = get_mem(repo_path, "")
        mem_items = [x for x in mem_items if not x.get("_stale")][:3]
        if mem_items:
            mem_str = "; ".join([f"{x['fact']} ({x['source']}, {x['confidence']})" for x in mem_items])
            budget_left = max(0, budget_remaining - 300)
            mem_str = mem_str[:budget_left*4] if budget_left > 0 else ""
            layers["6_validated_memory"] = mem_str or "(no relevant durable memory)"
            layers["6_memory_source"] = ".wolf/sage-memory.json (provenance required; stale marked)"
        else:
            layers["6_validated_memory"] = "(no relevant durable memory)"
    except Exception as e:
        layers["6_validated_memory"] = f"(no relevant durable memory: {e})"

    # L7 prior findings — only if relevant and budget allows
    if prior_state and budget_remaining > 500:
        layers["7_prior_state"] = prior_state[:min(1500, budget_remaining*4)]
    elif prior_state:
        layers["7_prior_state"] = "(omitted — budget exhausted)"

    layers["_budget"] = {"total": budget_tokens, "remaining": budget_remaining, "goal": "maximum useful information per token"}
    layers["_precedence"] = "live repo > tool results > config > validated memory > historical > inference"
    layers["_efficiency_rules"] = [
        "Do not re-read files already in context",
        "Prefer Grep/symbol search before full Read",
        "Cap injected context to budget; deduplicate",
        "Repository evidence wins over stale memory",
    ]
    return layers

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task")
    p.add_argument("--categories", default="general")
    p.add_argument("--files", default="")
    p.add_argument("--skill", default="")
    p.add_argument("--tool-output", default="")
    p.add_argument("--prior", default="")
    p.add_argument("--budget", type=int, default=6000)
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or "unknown task"
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []
    out = build(task, cats, files, args.skill, args.tool_output, args.prior, args.budget, Path(args.repo))
    print(json.dumps(out, indent=2))
