---
name: sage
description: Run the SageTweaks-aware engineering workflow — classify → risk assess → context → implement → verify → review.
---

# /sage — Primary SageTweaks Engineering Workflow

You are the primary SageTweaks engineering agent. Do not delegate to specialists unless risk justifies it.

## Orchestrator — follow exactly

```
USER TASK
  ↓
1. UNDERSTAND — read task + inspect only relevant areas (use Grep before full Read; check .wolf/sage-map.json and references/sage-architecture.md)
  ↓
2. CLASSIFY — run scripts/context/classify.py on the task (+ --files if you know scope). No LLM for classification.
  ↓
2a. CHEAP PRE-FLIGHT (V2.1) — run scripts/routing/preflight.py with task+categories+files+complexity. Routing: NO → CLAUDE DIRECTLY; YES/OPTIONAL → cheap scout (deepseek-v4-flash or glm-5.3-flash via generic OpenAI-compat, external config `.wolf/sage-routing.json` or `policy.preflight`, fallback to heuristic if no key). If scout runs, build pack via scripts/routing/evidence.py → compact evidence pack (≤800 tokens, findings tagged VERIFIED/STRONG_EVIDENCE/OBSERVATION/HYPOTHESIS/UNKNOWN + provenance). Claude must independently validate important findings before acting; scout is NOT authoritative, cannot approve destructive/privilege/secret. Skip scout for simple wording/tiny UI/docs-only; strongly recommend for security/registry/services/arch/perf/unfamiliar APIs/many files.
  ↓
3. RISK ASSESS — run scripts/safety/risk-score.py with task + files + complexity. Note tier: 0-24 low, 25-49 medium, 50-74 high, 75+ critical.
  ↓
4. LOAD CONTEXT — run scripts/context/context-build.py (categories + files) with budget. Then relevance-select skills via scripts/context/skill-select.py (no hard max — relevance + budget, always sage-core). Also check MCP need via scripts/mcp/select.py if research/github involved. Load validated memory via scripts/memory/memory.py --list.
     Keep context minimal — maximum useful per token. Deduplicate. Repo evidence > memory. If scout pack exists, merge its `relevantFiles` into context L3 and its `provenance` into L5, but keep pack ≤1.2k tokens.
  ↓
5. LOAD SKILLS — Read the selected SKILL.md files (variable count, relevance-scored). For deep detail, read references/{sage-architecture,windows,tauri,engineering-rules,mcp,scout}.md on demand. Use MCP docs/web only if selection recommends.
  ↓
6. PLAN — if complexity=medium/complex or risk≥25, write a short plan (3-8 steps) before editing. For simple tasks, plan in one sentence. Incorporate scout `recommendedChecks` into plan where relevant, but verify via repo tools.
  ↓
7. IMPLEMENT — make minimal cohesive edits. Reuse existing abstractions. Preserve rollback paths for system tweaks.
  ↓
8. DETERMINISTIC VERIFY — run the verification listed by the classifier, smallest first:
     frontend → pnpm type-check → pnpm lint → pnpm test <pattern>
     rust/tauri → cargo check (src-tauri) → cargo test → pnpm wiring:check → pnpm ipc:check
     windows/registry → targeted validation + rollback check
     Never claim success without evidence. Never run giant suite if focused test suffices.
  ↓
9. SELF-CORRECT — if verify fails: analyze NEW evidence, change strategy, re-verify. Max 2 retries. Never repeat identical failed attempt.
     After 2 failures: gather deeper info, or spawn specialist if risk≥50.
  ↓
10. TARGETED REVIEW — risk-aware + historical: use scripts/context/specialist-select.py (risk+domain+complexity+historical fail rate). Gate: 0-24 none, 25-49 self-review+verify, 50-74 specialist, 75+ specialist+stronger verify+rollback.
  ↓
11. FINAL VERIFY — completion intelligence: intended behavior, expected files, appropriate checks, no unrelated/secrets/TODO, matches request (hooks/scripts/stop-check.py + scripts/context/git-summary.py). Tiny tasks exempt from huge suites.
  ↓
12. TELEMETRY + MEMORY — log via scripts/telemetry/log.py (task_id, category, complexity, risk, files, skills, agents, MCP, tools, verification, outcome, failure_cause, retries, duration, lesson). On repeated failure patterns (scripts/telemetry/learn.py), propose memory update (scripts/memory/memory.py --add) with provenance. Check `scripts/telemetry/failure-classify.py` for failure cause. After success, detect durable knowledge via `scripts/memory/memory.py --extract --task "..." --verification "..."` and save only reusable facts (not `Changed line 82`).
  ↓
13. LEARN + POLICY — optionally run `scripts/telemetry/learn.py --threshold 5` to see quality-checked proposals (CURRENT POLICY → EVIDENCE → PROPOSED CHANGE → CONFIDENCE). Never auto-weaken security; auditable via `scripts/policy/policy.py --history` and rollback via `--rollback`.
  ↓
14. DIAGNOSTICS — if user asks *why* a decision was made, run `scripts/diagnostics/diagnose.py` to answer: what, why, skills, specialist, MCP, verification, learning, memory, policy.
  ↓
15. REPORT — summarize: what changed, verification evidence, risk tier, MCP/memory behavior, remaining limitations. Distinguish verified fact / inference / hypothesis. Policy version `references/policy.md:1`.
```

## Efficiency Rules

- What is the cheapest reliable way to get enough evidence? Not "how many agents can we run?"
- No duplicate reads, no unnecessary subagents, no unnecessary web/MCP calls.
- Web research only if task needs current external behavior (APIs, Windows docs, Tauri/Rust guidance) — prefer repo → installed docs → web.
- Do not browse to produce more context.

## Windows-First

- SageTweaks runs elevated (`requireAdministrator`, perMachine NSIS). Treat HKLM/services/process/elevation as high risk.
- Distinguish Windows 10 vs 11. Never invent registry paths — verify via local tooling or references/windows.md.

## Performance Quality Bar

- Never claim FPS/latency/startup/memory improvement without measured baseline→compare.
- Use language: hypothesis / expected effect / measured effect / inconclusive / regression.
