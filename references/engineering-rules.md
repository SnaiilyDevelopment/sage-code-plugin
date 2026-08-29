# Engineering Rules — SageTweaks

## Core Philosophy

- Claude is primary agent. Tools provide ground truth. Skills provide expertise.
- Optimize for **maximum successful development output per model usage**, not maximum agent count.
- Cheapest reliable evidence wins.

## Change Principles

- Minimal, cohesive diffs. Reuse existing abstractions (`src/lib/`, `src/hooks/`, `src-tauri/src/system/`).
- One source of truth: `CLAUDE.md` (why), `AGENTS.md` (what), `.claude/rules/*.md` (how) — never duplicate across them.
- Preserve rollback for every system tweak (`revert_vault/`, `restore_points/`).

## Verification

- Never say "looks good" when a deterministic check exists.
- Task-aware: docs-only → no tests; frontend → typecheck/lint/targeted Vitest; Rust/Tauri → cargo check/test + wiring:check; Windows → state/rollback validation.
- Self-correct: `verify → analyze new evidence → fix (different strategy) → verify`, max 2 retries.

## Risk-Based Review

- 0-24 low: no specialist
- 25-49 medium: self-review + verification
- 50-74 high: specialist review
- 75+ critical: specialist + stronger verification + rollback plan
- Review the diff, not the whole repo.

## Security

- Least privilege; validate untrusted input before shell/process/file use.
- Never expose secrets; stage no `license.dat`, `hwid.dat`, `audit_signing.key`, `supabase service_role`.
- Registry/services/process/elevation = high risk.

## Performance Quality Bar

- Hypotheses are not results. Language: hypothesis / expected effect / measured effect / inconclusive / regression.
- Establish baseline → run workload → make change → run same workload → compare with noise band.
- Use `src/lib/proveIt.ts` `capped_impact` / `matches_wddm_display_critical` guards; avoid placebo tweaks.

## Windows-First

- Test on Windows 10 and 11, AMD/Intel, NVIDIA/AMD where relevant.
- `perMachine` install + `requireAdministrator` — assume elevated, but verify privilege boundaries.

## Efficiency

- No duplicate reads, duplicate analysis, unnecessary subagents/reviews/web/MCP.
- Prefer symbol search (Grep) before full Read. Cap injected context.
- Repository evidence wins over stale memory.

## Research

- Prefer: repository → project docs → installed package/docs → MCP documentation → web (authoritative: Microsoft Learn, Tauri docs, Rust docs).
- Use web/MCP only when it materially improves correctness. Distinguish verified fact / inference / hypothesis / unknown; preserve source.

## Memory vs Repository Precedence

```
live repository evidence
> current tool results
> current project configuration
> validated memory (.wolf/sage-memory.json, confidence validated/high)
> historical observations (telemetry)
> inference
```

When sources conflict, tell Claude which is authoritative and why. Do not silently overwrite validated knowledge. Stale items (past TTL) require re-validation against repo.

## Context Budget

- Total skill + map budget ~3500 tokens. Prioritize: task → repo map → relevant files → skills → tool output → validated memory → prior findings. Deduplicate, avoid giant dumps. Goal: maximum useful information per token.
