---
name: sage-test
description: Run the most relevant deterministic SageTweaks verification — targeted tests → typecheck → lint → build.
---

# /sage-test

Task-aware verification — cheapest reliable evidence first.

1. Classify the change (or inspect `git diff`) to pick scope:
   - frontend/backend → `pnpm type-check` → `pnpm lint` → `pnpm test -- <pattern>`
   - rust/tauri → `cargo check` in `src-tauri` → `cargo test` → `pnpm wiring:check` → `pnpm ipc:check`
   - windows/registry → targeted validation + rollback check
   - docs only → no tests required
2. Run smallest relevant set. Report exact command, duration, pass/fail.
3. On failure: use `scripts/verification/verify-*.py` helpers if needed, then self-correct with new evidence.
4. Only run full suite if risk≥50 or regression suspected.

Use `scripts/verification/verify-frontend.py` / `verify-rust.py` for deterministic selection.
