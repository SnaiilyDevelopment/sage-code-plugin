---
name: sage-benchmark
description: Establish baseline → run workload → compare → report with noise/uncertainty (Sage performance quality bar).
---

# /sage-benchmark

Use `scripts/verification/benchmark.py` where available.

1. Establish baseline: run the relevant workload (FPS via presentmon, latency, startup, IO via diskspd, network via iperf3) — record exact conditions.
2. Make the change (or compare before/after).
3. Run the same workload again under identical conditions.
4. Compare: report hypothesis vs measured effect, delta, noise/uncertainty, sample count.
5. Classify result: **improvement / inconclusive / regression** — never claim improvement without evidence outside noise band.
6. Preserve conditions (OS build, driver, power plan, hardware) in the report.

Language: hypothesis, expected effect, measured effect, inconclusive, regression — not "optimized" without data.
