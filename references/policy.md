# Sage Code Policy — v2.1

> Versioned internal policy. Tracks routing, skill selection, risk thresholds, learning thresholds, memory rules, verification rules.
> Changes require evidence + confidence + audit. Rollback available via `.wolf/sage-policy.json` history.
> Never weakens security/destructive/secret protection.

## Current Policy (2.1)

| Rule | Value | Source |
|------|-------|--------|
| Preflight | enabled, budget 800 tokens, auto threshold, fallback to heuristic | `scripts/routing/preflight.py` |

## Current Policy (2.0 archive)

| Rule | Value | Source |
|------|-------|--------|
| Risk thresholds | 0-24 low, 25-49 medium, 50-74 high, 75+ critical | spec §5, §12 |
| Specialist threshold | score ≥3 (risk+domain+complexity+ambiguity+size+failRate) | `scripts/context/specialist-select.py` |
| Skill threshold | relevance ≥2.0, budget 3500 skill tokens / 6000 total context | `scripts/context/skill-select.py` |
| Learning | half-life 30d, confidence ≥5 samples, rate ≥70% before recommend | `scripts/telemetry/learn.py` |
| Memory confidence | hypothesis < observed < verified < validated ; TTL 90d | `scripts/memory/memory.py` |
| Verification | task-aware targeted first, broader only if risk≥50 or regression | `commands/sage.md` |
| Benchmark | 5 repeats, noise max(2*stdev,2%*mean), CV>15% → not_measurable, 4 states | `scripts/verification/benchmark.py` |
| Safety | 16 Bash patterns, 10+ sensitive file patterns, MCP high-risk requires confirmation | `hooks/scripts/*.py` |
| Adaptation | No policy change from <5 samples, no weakening of security/destructive/secret, auditable proposal `CURRENT→EVIDENCE→CHANGE→CONFIDENCE` | `scripts/policy/policy.py` |

## Change Log

| Version | Date | Change | Evidence | Confidence | Rollback |
|---------|------|--------|----------|------------|----------|
| 2.0 | 2026-08-29 | Initial V2.0 policy | V1.1→V2.0 maturity pass | validated | git revert |

## Rollback

`python scripts/policy/policy.py --rollback v1.1` restores previous. `python scripts/policy/policy.py --history` shows auditable changes.
