#!/usr/bin/env python3
"""
Relevance-based skill selection with context budget.
No hard max — selects by relevance score, deduplicates, respects token budget.
Always includes sage-core; adds others by relevance threshold.
"""
import json, re

# Skill definitions with keywords and estimated tokens
SKILLS = {
    "skills/sage-core/SKILL.md": {"keywords": [], "tokens": 800, "always": True},
    "skills/sage-windows/SKILL.md": {"keywords": [r"windows", r"registry", r"\bHKLM\b", r"\bHKCU\b", r"\bservice\b", r"power", r"\bUAC\b", r"\bWMI\b", r"\bprocess\b"], "tokens": 1200},
    "skills/sage-tauri/SKILL.md": {"keywords": [r"tauri", r"\brust\b", r"cargo", r"\bipc\b", r"serde", r"capability", r"permission", r"sidecar"], "tokens": 1100},
    "skills/performance/SKILL.md": {"keywords": [r"performance", r"\bfps\b", r"latency", r"startup", r"benchmark", r"\bcpu\b", r"\bgpu\b", r"memory", r"scheduler", r"presentmon", r"diskspd"], "tokens": 700},
    "skills/security/SKILL.md": {"keywords": [r"security", r"privilege", r"elevation", r"secret", r"auth", r"\bcve\b", r"permission", r"xss", r"injection"], "tokens": 700},
    "skills/sage-debugging/SKILL.md": {"keywords": [r"debug", r"repro", r"stack trace", r"crash", r"panic", r"fix.*bug"], "tokens": 600},
    "skills/sage-testing/SKILL.md": {"keywords": [r"\btest\b", r"vitest", r"cargo test", r"qa:vm", r"spec"], "tokens": 500},
    "skills/sage-research/SKILL.md": {"keywords": [r"research", r"investigate", r"whether.*changed", r"current.*behavior", r"docs.*lookup"], "tokens": 500},
    "skills/sage-git/SKILL.md": {"keywords": [r"\bgit\b", r"\bdiff\b", r"commit", r"\bbranch\b", r"\bpr\b", r"github"], "tokens": 400},
}

ALIAS_MAP = {
    "skills/windows-tweaks/SKILL.md": "skills/sage-windows/SKILL.md",
    "skills/tauri-rust/SKILL.md": "skills/sage-tauri/SKILL.md",
}

BUDGET_TOKENS = 3500  # total skill budget excluding sage-core

def score_skill(skill_path: str, task: str, categories: list, files: list) -> float:
    info = SKILLS.get(skill_path)
    if not info or info.get("always"):
        return 10.0
    text = (task + " " + " ".join(categories) + " " + " ".join(files)).lower()
    score = 0
    for pat in info["keywords"]:
        if re.search(pat, text, re.I):
            score += 2
    # category direct match bonus
    cat_map = {
        "skills/sage-windows/SKILL.md": ["windows","registry","services","processes"],
        "skills/sage-tauri/SKILL.md": ["rust","tauri"],
        "skills/performance/SKILL.md": ["performance"],
        "skills/security/SKILL.md": ["security","authentication"],
        "skills/sage-debugging/SKILL.md": ["debugging"],
        "skills/sage-testing/SKILL.md": ["testing"],
        "skills/sage-research/SKILL.md": ["research"],
        "skills/sage-git/SKILL.md": ["git"],
    }
    for cat in categories:
        if cat.lower() in [c.lower() for c in cat_map.get(skill_path,[])]:
            score += 3
    return score

def select(task: str, categories: list, files: list, budget: int = BUDGET_TOKENS, threshold: float = 2.0) -> list:
    # Always include sage-core
    selected = ["skills/sage-core/SKILL.md"]
    budget_remaining = budget
    candidates = []
    for path in SKILLS:
        if path == "skills/sage-core/SKILL.md": continue
        s = score_skill(path, task, categories, files)
        candidates.append((s, path))
    candidates.sort(reverse=True)  # high score first
    for score, path in candidates:
        if score < threshold:
            continue
        cost = SKILLS[path]["tokens"]
        if cost <= budget_remaining:
            selected.append(path)
            budget_remaining -= cost
        # if not enough budget, skip (don't partially include)
    return selected

if __name__ == "__main__":
    import argparse, sys
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?")
    p.add_argument("--categories", default="")
    p.add_argument("--files", default="")
    p.add_argument("--budget", type=int, default=BUDGET_TOKENS)
    args = p.parse_args()
    task = args.task or sys.stdin.read().strip() or ""
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    out = select(task, cats, files, args.budget)
    # also output scores for explainability
    scores = {path: score_skill(path, task, cats, files) for path in SKILLS}
    print(json.dumps({"selected": out, "scores": scores, "budget": args.budget}, indent=2))
