---
name: sage-core
description: Use for any SageTweaks engineering task — evidence-driven, minimal diffs, task-aware verification.
version: 1.0.0
---

# Sage Core

Core engineering discipline for all SageTweaks work.

## Workflow

Follow `/sage` orchestrator: Understand → Classify (`scripts/context/classify.py`) → Risk (`scripts/safety/risk-score.py`) → Context (`scripts/context/context-build.py`) → Plan → Implement → Verify → Self-correct → Review if risk≥50 → Report.

## Rules

- **Inspect before edit**: Grep/symbol search before full Read; read relevant code, not whole repo.
- **Minimal cohesive changes**: reuse existing abstractions in `src/lib/`, `src/hooks/`, `src-tauri/src/system/`. Do not create new layers to appear clever.
- **Ground truth is tool output**: tests, typecheck, lint, build, `wiring:check`, `ipc:check`. Never claim success without evidence.
- **Hypothesis ≠ measured fact**: separate speculation from tool output.
- **Rollback for system tweaks**: every registry/service/power change must have inverse stored in `applied_tweaks.json` / `revert_vault/`.
- **Compatibility**: Windows 10/11, AMD/Intel, NVIDIA/AMD. Check `matches_wddm_display_critical` for display-critical tweaks.
- **No swarm**: Claude is primary. Spawn specialists only when risk≥50 or cross-domain complexity demands it.
- **Efficiency**: cheapest reliable evidence. No duplicate reads, no redundant test suites, no giant context dumps. Repository evidence wins over stale memory.

## Completion Gate (Stop hook)

Before declaring success, confirm: intended files changed, relevant tests/typecheck passed, no unrelated diff, no secrets staged, task requirements satisfied. Docs-only exempt.

## References

For deep detail, see `references/{sage-architecture.md,engineering-rules.md}` and `.wolf/sage-map.json`.
