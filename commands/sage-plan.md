---
name: sage-plan
description: Produce a concise plan for the current SageTweaks task — classify, risk, scope, verification.
---

# /sage-plan

Produce a read-only plan without modifying files.

1. Classify: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/classify.py" "<task>" --files "<comma list>"`
2. Risk: run `python "${CLAUDE_PLUGIN_ROOT}/scripts/safety/risk-score.py" "<task>" --files "<list>" --complexity <simple|medium|complex>`
3. Scope: list likely affected files/components from `references/sage-architecture.md` + `.wolf/sage-map.json`
4. Context: which skills (`sage-core` + 1-2 specialists) will be needed
5. Verification: what deterministic checks will prove success
6. Risk-gated steps: whether specialist review / rollback plan is needed
7. Output a short plan (3-8 steps) with verification at the end. Do not implement yet.
