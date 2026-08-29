---
name: sage-testing
description: Use for targeted tests, typecheck, lint, build, integration and regression testing — evidence-based completion.
version: 1.0.0
---

# Sage Testing

- **Targeted first**: run smallest relevant test (`pnpm test -- <pattern>` / `cargo test <filter>`) before full suite.
- **Order**: targeted tests → `pnpm type-check` → `pnpm lint` → `pnpm build` → broader tests only if justified (risk≥50 or regression suspected).
- **Integration**: `cargo test` (src-tauri), `pnpm wiring:check` / `ipc:check` / `security:policy`, `qa:vm:matrix` for OS-level.
- **Regression**: add test for every bug fix; verify `revert_vault` round-trip for tweak changes.
- **Evidence**: report exact command, duration, pass/fail. Never "looks good" without tool output.
- **Selector**: use `scripts/verification/verify-frontend.py` / `verify-rust.py` for deterministic mapping.
