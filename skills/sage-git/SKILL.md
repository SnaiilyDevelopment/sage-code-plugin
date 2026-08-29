---
name: sage-git
description: Use for git diff inspection, changed-file summaries, accidental-change detection, commit prep, branch awareness, regression checks.
version: 1.0.0
---

# Sage Git

- **Diff inspection**: `scripts/context/git-summary.py` + `git diff --stat` + `git diff <file>` for targeted review.
- **Accidental-change detection**: watch for lockfile churn, secrets, unrelated file edits (`git status --porcelain` suspicious list).
- **Commit prep**: stage only intended files; never `git add .` without review; never `git reset --hard` / `git clean -fdx` without scope — hooks will ask.
- **Branch awareness**: check `git rev-parse --abbrev-ref HEAD` before push; never force-push without confirmation.
- **Regression checks**: `git diff` review before declaring success; `git log --oneline -5` for context.
- **Safety**: never silently destroy user work; never auto-perform destructive Git operations.
