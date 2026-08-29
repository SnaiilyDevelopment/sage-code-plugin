---
name: sage-build
description: Run the appropriate SageTweaks build with minimal scope and report evidence.
---

# /sage-build

Run the smallest build that covers the change.

1. Inspect `references/sage-architecture.md` for build commands.
2. If frontend changed: `pnpm build` (or `pnpm type-check` for quick check).
3. If Rust/Tauri changed: `cargo check` in `src-tauri/` then `pnpm build`; only run `pnpm tauri:build` if user explicitly asks (slow).
4. Always report: exact command, duration, pass/fail, and next step if failed.

Do not claim success without build evidence. Prefer fast checks first.
