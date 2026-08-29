---
name: sage-debugging
description: Use for reproduce → isolate → inspect evidence → change one variable → verify root cause debugging.
version: 1.0.0
---

# Sage Debugging

- **Reproduce**: get exact failure (test output, stack trace, `cargo test` log, `presentmon` capture). Do not guess or invent.
- **Isolate**: narrow to smallest failing scope — one file, one tweak, one IPC call, one registry key. Use `git diff` + `scripts/context/git-summary.py`.
- **Inspect evidence**: read relevant code + tool output + prior state. Prefer Grep before full Read.
- **One variable at a time**: change exactly one thing, re-verify with smallest relevant check. Never batch speculative fixes.
- **Verify root cause**: confirm fix addresses cause, not symptom; add regression test if applicable.
- **Tauri/Rust state bugs**: check 4-piece wiring (handler/lib.rs/permission/capability), `AppliedTweakRecord` persistence, `OnceLock<Mutex<>>` cache invalidation (see `settings.rs`).
- **Windows bugs**: snapshot registry/service state before/after, check Win10 vs 11 delta, elevation.
