---
name: sage-context
description: Show compact SageTweaks repository intelligence and relevant context for the current task.
---

# /sage-context

1. If `.wolf/sage-map.json` exists, show its summary; otherwise run `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/repo-map.py" --repo .`.
2. Show `references/sage-architecture.md` preview (architecture, modules, build/test commands, pitfalls).
3. Run `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/git-summary.py --cwd ."` for branch/diff awareness.
4. Optionally classify a provided task: `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/classify.py" "<task>"`.

Do not dump full file contents — keep it compact and prioritized.
