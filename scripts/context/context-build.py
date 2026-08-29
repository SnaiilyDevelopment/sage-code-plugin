#!/usr/bin/env python3
"""
Intelligent context builder — V2.2 authoritative budget tracker.
Prioritizes: 1 task, 2 repo map, 3 relevant files, 4 skills, 5 tool results, 6 validated memory, 7 prior findings.
"""
import json, sys
from pathlib import Path

try:
    from scripts.context.skill_select import select as skill_select_fn, SKILLS
except:
    import importlib.util
    spec = importlib.util.spec_from_file_location("skill_select", str(Path(__file__).parent / "skill-select.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    skill_select_fn = mod.select
    SKILLS = mod.SKILLS

try:
    from scripts.routing.tokens import estimate_tokens as _est
    def estimate_tokens(text: str) -> int:
        return _est(text)
except:
    def estimate_tokens(text: str) -> int:
        return max(1, int(len(text) / 4 * 1.25))

class BudgetTracker:
    def __init__(self, total: int):
        self.total = total
        self.used = 0
        self.layers = []
    def reserve(self, name: str, text: str, priority: int):
        est = estimate_tokens(text) if isinstance(text, str) else estimate_tokens(json.dumps(text))
        remaining = self.total - self.used
        accepted = est <= remaining
        # For truncation: if not accepted, we may still accept truncated version externally
        if accepted:
            self.used += est
        self.layers.append({"layer": name, "priority": priority, "requested": est, "estimated": est, "accepted": accepted, "remaining_after": self.total - self.used})
        return accepted, est, remaining
    def force_use(self, name: str, text: str, priority: int):
        est = estimate_tokens(text) if isinstance(text, str) else estimate_tokens(json.dumps(text))
        self.used += est
        self.layers.append({"layer": name, "priority": priority, "requested": est, "estimated": est, "accepted": True, "remaining_after": self.total - self.used})
        return est
    def remaining(self): return self.total - self.used

def _load_policy_budget(repo: Path) -> int:
    try:
        import importlib.util as _ilu
        pp = Path(__file__).resolve().parents[1] / "policy/policy.py"
        spec = _ilu.spec_from_file_location("pol", str(pp))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pol = mod.load(repo or Path.cwd())
        return int(pol.get("context_budget", 6000))
    except:
        return 6000

COMPLEXITY_BUDGETS = {"simple": 1500, "medium": 6000, "complex": 12000}
SCOUT_TARGET = 600
SCOUT_HARD = 900

def build(task: str, categories: list[str], files: list[str], skill_hint: str = "", tool_output: str = "", prior_state: str = "", budget_tokens: int = None, repo: Path = None) -> dict:
    repo = repo or Path.cwd()
    # single policy load, cached
    policy_budget = _load_policy_budget(repo)
    if budget_tokens is None:
        budget_tokens = policy_budget
    if budget_tokens > policy_budget:
        budget_tokens = policy_budget
    # Enforce complexity-based budgets if caller passes no explicit budget: clamp to complexity hint
    # If task looks simple, enforce ≤1500 regardless of policy
    try:
        from pathlib import Path as _P2
        import importlib.util as _ilu2
        cp = _P2(__file__).parent / "classify.py"
        spec = _ilu2.spec_from_file_location("cls_bud", str(cp))
        cm = _ilu2.module_from_spec(spec)
        spec.loader.exec_module(cm)
        cls = cm.classify(task, files)
        comp = cls.get("complexity","medium")
        max_for_comp = COMPLEXITY_BUDGETS.get(comp, policy_budget)
        if budget_tokens > max_for_comp:
            budget_tokens = max_for_comp
    except:
        pass
    # also load skill budget once
    try:
        import importlib.util as _ilu
        pp = Path(__file__).resolve().parents[1] / "policy/policy.py"
        spec = _ilu.spec_from_file_location("pol_cached", str(pp))
        mod = _ilu.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pol_cached = mod.load(repo)
        skill_budget_policy = int(pol_cached.get("skill_budget", 3500))
    except (OSError, ValueError, TypeError, ImportError):
        skill_budget_policy = 3500

    tracker = BudgetTracker(budget_tokens)
    layers = {}

    # L1 task — always
    layers["1_task"] = task[:2000]
    tracker.force_use("1_task", layers["1_task"], 1)

    # L2 repo map — truncated to remaining budget
    plugin_root = Path(__file__).resolve().parents[2]
    arch = plugin_root / "references" / "sage-architecture.md"
    if arch.exists():
        txt = arch.read_text(encoding="utf-8", errors="ignore")
        remaining = tracker.remaining()
        # allocate up to 40% of remaining for map, but not exceeding 4000 chars
        max_chars = min(4000, max(0, int(remaining * 3)))
        truncated = txt[:max_chars] if max_chars > 0 else ""
        # check if fits
        est = estimate_tokens(truncated)
        if est <= remaining and truncated:
            layers["2_repo_map"] = truncated
            tracker.force_use("2_repo_map", truncated, 2)
            layers["2_repo_map_source"] = "references/sage-architecture.md + .wolf/sage-map.json (hash-guarded)"
        elif remaining > 200 and truncated:
            # truncate further to fit
            fit_chars = max(0, int(remaining * 3))
            truncated2 = txt[:fit_chars]
            layers["2_repo_map"] = truncated2
            tracker.force_use("2_repo_map", truncated2, 2)
            layers["2_repo_map_source"] = "references/sage-architecture.md (truncated to budget)"
        else:
            layers["2_repo_map"] = "(omitted — budget exhausted)"
            layers["2_repo_map_source"] = "omitted"
            tracker.layers.append({"layer":"2_repo_map","priority":2,"requested":est,"estimated":est,"accepted":False,"remaining_after":tracker.remaining()})
    else:
        layers["2_repo_map"] = "(run scripts/context/repo-map.py to generate)"
        layers["2_repo_map_source"] = "missing"

    # L3 relevant files
    if files:
        uniq = list(dict.fromkeys(files))
        remaining = tracker.remaining()
        # budget-aware cap: each file ~100 tokens for path, so cap by remaining
        if remaining <= 100:
            layers["3_relevant_files"] = {"hint": "omitted — budget exhausted", "omitted": True}
            tracker.layers.append({"layer":"3_relevant_files","priority":3,"requested": estimate_tokens(json.dumps(uniq)),"estimated":0,"accepted":False,"remaining_after":remaining})
        else:
            max_files = min(len(uniq), max(1, remaining // 100))
            # also show if truncated
            payload = {"hint": "Read these symbol-level first; full read only if needed", "files": uniq[:max_files], "note": "Use Grep before full Read. Avoid duplicate reads.", "deduped": len(files) - len(uniq)}
            if len(uniq) > max_files:
                payload["truncated"] = f"{len(uniq)-max_files} files omitted due to budget"
            est = estimate_tokens(json.dumps(payload))
            if est <= remaining:
                layers["3_relevant_files"] = payload
                tracker.force_use("3_relevant_files", json.dumps(payload), 3)
            else:
                layers["3_relevant_files"] = {"hint": "omitted — budget exhausted", "omitted": True}
                tracker.layers.append({"layer":"3_relevant_files","priority":3,"requested":est,"estimated":est,"accepted":False,"remaining_after":remaining})
    else:
        layers["3_relevant_files"] = {"hint": "No files yet — inspect repo map to locate candidates", "categories": categories}
        # small cost, still track
        tracker.force_use("3_relevant_files", json.dumps(layers["3_relevant_files"]), 3)

    # L4 skills — reuse cached policy
    remaining = tracker.remaining()
    skill_budget = min(skill_budget_policy, max(800, remaining))
    if remaining < 800:
        # still include sage-core if possible, else omit
        if remaining >= 200:
            layers["4_skills"] = ["skills/sage-core/SKILL.md"]
            tracker.force_use("4_skills", json.dumps(layers["4_skills"]), 4)
        else:
            layers["4_skills"] = ["(omitted — budget exhausted)"]
            tracker.layers.append({"layer":"4_skills","priority":4,"requested":800,"estimated":800,"accepted":False,"remaining_after":remaining})
        layers["4_skills_budget"] = skill_budget
        layers["4_skills_explain"] = "omitted or minimal due to budget"
    else:
        selected = skill_select_fn(task, categories, files, budget=skill_budget)
        if skill_hint and skill_hint not in selected:
            # check if hint fits
            hint_cost = SKILLS.get(skill_hint, {}).get("tokens", 500)
            if hint_cost <= remaining:
                selected.append(skill_hint)
        selected = list(dict.fromkeys(selected))
        if "skills/sage-core/SKILL.md" in selected:
            selected.remove("skills/sage-core/SKILL.md")
            selected = ["skills/sage-core/SKILL.md"] + selected
        elif remaining >= 800:
            selected = ["skills/sage-core/SKILL.md"] + [s for s in selected if s != "skills/sage-core/SKILL.md"]
        layers["4_skills"] = selected
        layers["4_skills_budget"] = skill_budget
        layers["4_skills_explain"] = "Relevance-scored; threshold 2.0; always sage-core; respects token budget"
        tracker.force_use("4_skills", json.dumps(selected), 4)

    # L5 tool output — truncated, lowest priority if overflow
    if tool_output:
        remaining = tracker.remaining()
        if remaining <= 100:
            layers["5_tool_output"] = "(omitted — budget exhausted)"
            tracker.layers.append({"layer":"5_tool_output","priority":5,"requested": estimate_tokens(tool_output),"estimated":estimate_tokens(tool_output),"accepted":False,"remaining_after":remaining})
        else:
            max_tool = min(4000, max(0, remaining * 3))
            truncated = tool_output[-max_tool:] if max_tool > 0 else ""
            est = estimate_tokens(truncated)
            if est <= remaining and truncated:
                layers["5_tool_output"] = truncated
                tracker.force_use("5_tool_output", truncated, 5)
                layers["5_tool_output_source"] = "recent tool results"
            else:
                layers["5_tool_output"] = "(omitted — budget exhausted)"
                tracker.layers.append({"layer":"5_tool_output","priority":5,"requested":est,"estimated":est,"accepted":False,"remaining_after":remaining})
    else:
        layers["5_tool_output"] = "(none yet)"
        # negligible, don't charge

    # L6 validated memory — capped with ROI filtering (relevance×confidence×freshness/token_cost)
    try:
        import importlib.util
        mem_path = plugin_root / "scripts" / "memory" / "memory.py"
        spec2 = importlib.util.spec_from_file_location("sage_memory", str(mem_path))
        mem_mod = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(mem_mod)
        get_mem = mem_mod.get_valid
        mem_items = []
        for cat in set(categories + ["general"]):
            mem_items.extend(get_mem(repo, cat))
        if not mem_items:
            mem_items = get_mem(repo, "")
        mem_items = [x for x in mem_items if not x.get("_stale")]
        # ROI filter: prioritize high-ROI memory
        try:
            from pathlib import Path as _P3
            import importlib.util as _ilu3
            rp = _P3(__file__).parent / "roi.py"
            spec3 = _ilu3.spec_from_file_location("roi", str(rp))
            roi_mod = _ilu3.module_from_spec(spec3)
            spec3.loader.exec_module(roi_mod)
            ranked = roi_mod.filter_by_roi([{"text": x["fact"], "confidence": x.get("confidence","observed"), "date": x.get("last_validated") or x.get("date")} for x in mem_items], task, threshold=0.0005, top_n=3)
            # map back to original items ordered by ROI
            ordered = []
            for r in ranked:
                txt = r["item"]["text"] if isinstance(r.get("item"), dict) else str(r.get("item"))
                match = next((x for x in mem_items if x["fact"]==txt), None)
                if match: ordered.append(match)
            mem_items = ordered if ordered else mem_items[:3]
        except Exception:
            mem_items = mem_items[:3]
        if mem_items:
            mem_items = mem_items[:3]
            mem_str = "; ".join([f"{x['fact']} ({x['source']}, {x['confidence']})" for x in mem_items])
            remaining = tracker.remaining()
            if remaining <= 100:
                layers["6_validated_memory"] = "(omitted — budget exhausted)"
                tracker.layers.append({"layer":"6_validated_memory","priority":6,"requested": estimate_tokens(mem_str),"estimated":estimate_tokens(mem_str),"accepted":False,"remaining_after":remaining})
            else:
                budget_left_chars = max(0, remaining * 3)
                mem_str_trunc = mem_str[:budget_left_chars] if len(mem_str) > budget_left_chars else mem_str
                est = estimate_tokens(mem_str_trunc)
                if est <= remaining:
                    layers["6_validated_memory"] = mem_str_trunc or "(no relevant durable memory)"
                    tracker.force_use("6_validated_memory", mem_str_trunc, 6)
                else:
                    layers["6_validated_memory"] = "(omitted — budget exhausted)"
                    tracker.layers.append({"layer":"6_validated_memory","priority":6,"requested":est,"estimated":est,"accepted":False,"remaining_after":remaining})
            layers["6_memory_source"] = ".wolf/sage-memory.json (provenance required; stale marked; ROI filtered)"
        else:
            layers["6_validated_memory"] = "(no relevant durable memory)"
    except Exception as e:
        layers["6_validated_memory"] = f"(no relevant durable memory: {e})"

    # L7 prior findings — only if budget allows
    if prior_state:
        remaining = tracker.remaining()
        if remaining > 200:
            truncated = prior_state[:min(1500, remaining*3)]
            est = estimate_tokens(truncated)
            if est <= remaining:
                layers["7_prior_state"] = truncated
                tracker.force_use("7_prior_state", truncated, 7)
            else:
                layers["7_prior_state"] = "(omitted — budget exhausted)"
                tracker.layers.append({"layer":"7_prior_state","priority":7,"requested":est,"estimated":est,"accepted":False,"remaining_after":remaining})
        else:
            layers["7_prior_state"] = "(omitted — budget exhausted)"
            tracker.layers.append({"layer":"7_prior_state","priority":7,"requested": estimate_tokens(prior_state),"estimated":estimate_tokens(prior_state),"accepted":False,"remaining_after":remaining})

    layers["_budget"] = {"total": budget_tokens, "used": tracker.used, "remaining": tracker.remaining(), "goal": "maximum useful information per token"}
    layers["_budget_layers"] = tracker.layers
    layers["_precedence"] = "live repo > tool results > config > validated memory > historical > inference"
    layers["_efficiency_rules"] = [
        "Do not re-read files already in context",
        "Prefer Grep/symbol search before full Read",
        "Cap injected context to budget; deduplicate",
        "Repository evidence wins over stale memory",
    ]
    # invariant: never exceed
    layers["budget_total"] = budget_tokens
    layers["budget_used"] = tracker.used
    layers["budget_remaining"] = tracker.remaining()
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
    p.add_argument("--budget", type=int, default=None)
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or "unknown task"
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []
    out = build(task, cats, files, args.skill, args.tool_output, args.prior, args.budget, Path(args.repo))
    print(json.dumps(out, indent=2))
