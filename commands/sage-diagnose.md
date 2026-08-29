---
name: sage-diagnose
description: Diagnose Sage decisions — what was decided, why, which skills/specialist/MCP/verification, learning, memory.
---

# /sage-diagnose

Self-diagnostics for transparency. Answers:

- What did Sage decide? Why?
- Which skills were selected? Why?
- Why was a specialist selected?
- Why was MCP used?
- Which verification ran?
- What failed?
- What did the system learn?
- What memory changed?
- Policy version

Run:

```
python "${CLAUDE_PLUGIN_ROOT}/scripts/diagnostics/diagnose.py" "task description" --files "comma list" --repo .
```

Or broadly: `python scripts/diagnostics/diagnose.py "Fix registry rollback bug" --files "src-tauri/src/tweaks/mod.rs"`

Also available:

- `python scripts/routing/preflight.py "task" --categories "cats" --files "list"` — scout routing + evidence pack
- `python scripts/routing/evidence.py --task "task"` — build compact pack
- `python scripts/telemetry/learn.py --threshold 5` — learning insights (including preflight)
- `python scripts/policy/policy.py --show` — current policy (now 2.1 with preflight)
- `python scripts/memory/memory.py --list` — durable memory
- `python scripts/context/skill-select.py "task" --categories "cats"` — skill rationale

Preflight diagnostics: `python scripts/diagnostics/diagnose.py` now also reports `Scout used, model, why, cost, useful/verified/rejected, MCP, specialist`.

Also: `python scripts/diagnostics/diagnose.py` extends to preflight — see `scripts/diagnostics/diagnose.py:1`.
