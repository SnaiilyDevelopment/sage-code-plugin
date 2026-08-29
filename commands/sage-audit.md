---
name: sage-audit
description: Audit the current task or diff — category, risk drivers, affected components, verification, specialist need.
---

# /sage-audit

Read-only audit. Do not modify files.

1. Classify: `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/classify.py" "<task>" --files "<diff files>"`
2. Risk: `python "${CLAUDE_PLUGIN_ROOT}/scripts/safety/risk-score.py" "<task>" --files "<list>" --complexity <c>`
3. Context: `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/git-summary.py"` for branch/diff/accidental-change.
4. Determine: task category, complexity, risk drivers (7 dimensions), affected files/components, external assumptions, required verification, whether specialist review is justified (thresholds 0-24/25-49/50-74/75+).
5. Output audit summary with routing recommendation.
