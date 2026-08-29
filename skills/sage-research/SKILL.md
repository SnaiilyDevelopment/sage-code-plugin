---
name: sage-research
description: Use when current external behavior, APIs, Windows docs, or Tauri/Rust guidance materially affects correctness. MCP-aware.
version: 1.1.0
---

# Sage Research

Intelligent research workflow — prefer cheapest reliable source.

## Order

```
repository
  ↓ (not found)
project documentation (docs/, references/)
  ↓
installed package/documentation (node_modules, Cargo.lock, local docs)
  ↓
MCP documentation (if available)
  ↓
web (authoritative: Microsoft Learn, Tauri docs, docs.rs, Rust docs)
```

Use `scripts/mcp/select.py` to decide MCP need. Check `scripts/telemetry/learn.py` — repeated failures for a pattern should increase documentation verification for that pattern.

## Rules

- Use web/MCP only when it materially improves correctness (current API, changing docs, Windows behavior, dependency version).
- Preserve source (URL, title, date) when external claims matter.
- Distinguish: **verified fact** (repo/tool confirms) / **inference** (derived) / **hypothesis** (untested) / **unknown** — never present unverified assumption as fact.
- Never expose secrets into research/telemetry/memory.
