# Sage Code — v2.4.0

A SageTweaks-focused Claude Code engineering layer with **cheap pre-flight intelligence** — Sage understands cheap vs expensive reasoning.

**Philosophy:** `Claude + domain expertise + repo intelligence + validated memory + smart skill selection + MCP when useful + cheap scout + deterministic verification + risk-aware delegation + failure learning` — not a swarm. Optimizes for *less expensive Claude exploration + more useful context + better correctness + minimal added latency*.

Claude is primary and final authority; scout is research, not truth.

Claude remains primary agent. The environment gets smarter with use.

## Quick Start

```bash
claude --plugin-dir /path/to/sage-code
```
Restart after hook/plugin changes. Portable via `${CLAUDE_PLUGIN_ROOT}`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/context/repo-map.py" --repo .   # regen map
python "${CLAUDE_PLUGIN_ROOT}/scripts/telemetry/learn.py" --threshold 5  # insights
python "${CLAUDE_PLUGIN_ROOT}/scripts/memory/memory.py" --list          # durable memory
```

## Commands — primary stays simple

| Command | Purpose |
|---------|---------|
| `/sage` | Full workflow: classify → **cheap scout (if needed) → evidence pack → Claude validation** → risk → context+skills+MCP → plan → implement → verify → self-correct → review → telemetry → report |
| `/sage-plan` | Read-only plan with routing + scout gate |
| `/sage-build` | Minimal build |
| `/sage-debug` | Reproduce → isolate → one-variable fix |
| `/sage-test` | Task-aware verification |
| `/sage-review` | Risk-gated diff review (low none / medium self / high specialist / critical +rollback) |
| `/sage-audit` | Category/risk/scope/verification audit |
| `/sage-benchmark` | Baseline → controlled workload → repeated runs → noise → improvement/regression/inconclusive/not_measurable |
| `/sage-context` | Compact repo intelligence + git summary |
| `/sage-diagnose` | What/why skills/specialist/MCP/scout(cost, useful/verified/rejected), verification, learning, memory, policy |

Advanced users use the rest; normal work is just `/sage`. Scout diagnostics via `/sage-diagnose`.

## Architecture

```
sage-code/
├── .claude-plugin/plugin.json  v2.1.0
├── commands/       10 (sage primary + diagnose)
├── agents/         5 specialists + aliases
├── skills/         9 + aliases (core, windows, tauri, performance, security, debugging, testing, research, git, scout via references/scout.md)
├── hooks/          session-start, validate-bash/write, format-guard, stop-check V2.0
├── scripts/
│   ├── context/    classify, skill-select (relevance+budget), context-build (budget+memory+dedup), specialist-select, repo-map, git-summary
│   ├── routing/    preflight (cheap scout router, provider-agnostic), evidence (compact pack ≤800, provenance)
│   ├── memory/     memory (provenance hypothesis<observed<verified<validated, stale, no secrets, auto-extract)
│   ├── policy/     policy (versioned 2.1, auditable CURRENT→EVIDENCE→CHANGE→CONFIDENCE, rollback)
│   ├── diagnostics/ diagnose (now includes scout cost/useful/verified)
│   ├── mcp/        select (github/docs/web) + safety
│   ├── telemetry/  log (+preflight_cost/latency/tokens/useful/wrong), learn (+preflight signals, scout_by_category), failure-classify
│   ├── verification/ verify-frontend/rust/tauri, benchmark (CV, noise, 4 states)
│   ├── quality/    lint-check
│   └── safety/     secret-strip, risk-score
├── references/     sage-architecture (entry points, deps, freq-modified, tests), windows, tauri, engineering-rules (precedence+budget), sage-memory, mcp, scout, policy (2.1), routing.example
└── tests/          classify, risk, hooks, context, v11 (12), v2 (12), v21 (12)
```

## Cheap Pre-Flight (V2.1)

`scripts/routing/preflight.py` decides `SKIP simple wording/tiny UI/docs-only` → `CLAUDE_DIRECTLY` else `YES for security/registry/services/privilege/arch/perf/many files/research`. Generic adapter via `SAGE_PREFLIGHT_BASE_URL`/`SAGE_PREFLIGHT_API_KEY` (external config `.wolf/sage-routing.json` or `policy.preflight`), fallback to heuristic. Default `deepseek-v4-flash` (optional `glm-5.3-flash` as second opinion only when `ambiguity high`). Evidence via `scripts/routing/evidence.py` ≤800 tokens `VERIFIED/STRONG_EVIDENCE/OBSERVATION/HYPOTHESIS/UNKNOWN` + `file:symbol:line` + `source URL/date/model/confidence` + `verified=false` until Claude validates via repo tools/MCP/tests. Never huge transcript, config budget. Scout cannot approve destructive/privilege/secret. Cost tracked `model, tokens_in/out, cost_usd, latency_ms, useful?/wrong?` via `log.py` and `learn.py` `preflight.useful_rate`. See `references/scout.md:1`.

## Adaptive Learning

`scripts/telemetry/log.py` records per task: `task_id, category, complexity, risk, files, skills, agents, MCP, tools, verification, result, failure_cause, retries, duration, lesson, memory_updates` (secrets stripped). `scripts/telemetry/learn.py` analyzes with **recency weighting** (half-life 30d) and **confidence threshold** (default 5) — emits: which skills work per category, which verification catches issues, which tasks need specialist, which categories fail, which workflows waste time. Single example never changes behavior. Repeated `failure_classify` patterns (wrong_file, missing_context, incorrect_api, etc.) suggest memory/skill updates.

## Validated Memory

`scripts/memory/memory.py` → `.wolf/sage-memory.json` (git-ignored) + `references/sage-memory.md` view. Every item: `fact, source, date, confidence (low/medium/high/validated), ttl_days, hash`. Stale detection via TTL. Precedence: `live repo > tool results > config > validated memory > historical > inference`. Conflicts tell Claude which source wins. No secrets, no chatter — durable engineering knowledge only. See `references/sage-memory.md:1`.

## Skill Selection — relevance + budget

`scripts/context/skill-select.py` scores each skill by keyword+category relevance, always includes `sage-core`, respects token budget (default 3500 for skills, 6000 total context). No hard max — quality determines count:

- Registry+Tauri+Rust+security → `sage-core, sage-windows, sage-tauri, security` (4)
- Simple frontend → `sage-core` (1)
- Performance investigation → `sage-core, performance, research` (3)

Deduplicates, threshold 2.0, word-boundary safe.

## Context — maximum useful per token

`scripts/context/context-build.py` prioritizes: 1 task → 2 repo map (hash-guarded) → 3 relevant files (dedupe, cap 8) → 4 skills (relevance) → 5 tool results → 6 validated memory (relevant + non-stale, cap 3) → 7 prior findings. Token budget, no duplicate files/summaries, no giant dumps. `references/engineering-rules.md:1` defines precedence.

## MCP — native orchestration

Claude Code already supports MCP. Sage is **MCP-aware** (`references/mcp.md:1`, `scripts/mcp/select.py:1`):

- `github` — issue/PR investigation
- `documentation` — current Tauri/Rust/Windows API
- `web/browser` — current web/security advisories

Scoring 0-10, threshold 5. Examples: repo-only question → No MCP; Tauri current API → docs MCP; GitHub PR → github MCP. Preference order: `repo > project docs > installed docs > MCP docs > web`. High-risk remote delete/modify requires confirmation.

## Repository Intelligence

`scripts/context/repo-map.py:1` identifies architecture, entry points (`src/main.tsx`, `src/App.tsx`, `src-tauri/src/lib.rs`), modules, deps, Tauri config, permissions (431), Windows code, important config, **frequently modified** (last 100 commits), tests (181 vitest, 283 rust), change detection via **hash**. Avoids rescan if unchanged.

## Agents — evidence-driven

`scripts/context/specialist-select.py:1` scores `risk + domain + complexity + ambiguity + size + historical fail rate` (threshold 3). Default `Claude alone`; cross-domain high-risk → `sage-reviewer`. Respects `learn.py` fail rates. Review policy: 0-24 none, 25-49 self+verify, 50-74 specialist, 75+ specialist+stronger+rollback.

## Verification & Benchmarking

Task-aware pipeline: docs none, frontend type-check/lint/targeted Vitest, Rust cargo check/test + wiring:check, Windows state/rollback. Benchmark `scripts/verification/benchmark.py:1` does baseline → controlled workload → 5 repeats → stdev/CV/noise → `improvement / regression / inconclusive / not_measurable` (high CV → not_measurable). No fake hardware measurements.

## Safety & Completion

Hooks deterministic lightweight (no LLM): `validate-bash` (16 patterns), `validate-write` (secrets + license.dat/hwid.dat), `format-guard`, `stop-check` V1.1 (intended files, tests, unrelated changes, secrets, TODO, matches request). MCP high-risk requires confirmation. Secrets stripped via `scripts/safety/secret-strip.py:1`.

## Tests

```
python tests/test_classify.py  # 7 pass
python tests/test_risk.py      # 5 pass
python tests/test_hooks.py     # 8 pass
python tests/test_context.py   # 3 pass
python tests/test_v11.py       # 12 pass — skill relevance, budget, MCP, specialist, memory, telemetry, learn
```

See `references/engineering-rules.md`, `references/sage-architecture.md`, `references/mcp.md`.
