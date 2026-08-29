---
name: sage-debug
description: Debug a SageTweaks failure — reproduce, isolate, inspect evidence, fix one variable at a time.
---

# /sage-debug

Follow the debugging skill (`skills/sage-debugging/SKILL.md`).

1. Reproduce: get the exact failure (log, stack trace, test output). Do not guess.
2. Isolate: narrow to smallest failing scope — one file, one tweak, one IPC path.
3. Inspect evidence: read relevant code + tool output + `git diff`; use `scripts/context/git-summary.py` for diff.
4. Change one variable at a time. Verify after each change with the smallest relevant check.
5. Confirm root cause is fixed (not just symptom) before closing.
6. If Rust/Tauri state bug: check 4-piece wiring (handler, lib.rs, permission, capability) and state duplication.
