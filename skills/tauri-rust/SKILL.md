---
name: tauri-rust
description: Use for Rust, Tauri v2, IPC, native integration, packaging, and desktop architecture work.
version: 1.0.0
---

# Tauri + Rust

Alias for `sage-tauri`. See `skills/sage-tauri/SKILL.md` and `references/tauri.md`.

- Follow Tauri v2 4-piece wiring (handler → lib.rs → permission → capability).
- Keep IPC contracts explicit and validated; avoid state duplication.
- Prefer idiomatic Rust and strong error handling; avoid `unwrap()` in prod.
- Run `cargo check` / `cargo test` / `pnpm wiring:check` / `pnpm ipc:check` after edits.
- NSIS-only packaging; `Cargo.toml` release profile authoritative.
