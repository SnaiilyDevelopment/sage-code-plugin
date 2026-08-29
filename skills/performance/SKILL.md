---
name: performance
description: Use for performance, FPS, latency, startup, memory, CPU/GPU, IO, scheduler, or benchmark changes.
version: 1.0.0
---

# Performance

- Establish baseline before claiming improvement — `scripts/verification/benchmark.py` or manual `presentmon`/`diskspd`/`iperf3`.
- Repeatable measurements: same OS build, driver, power plan, hardware, sample count. Report conditions.
- Separate CPU, GPU, I/O, network, scheduler effects — do not conflate.
- Avoid placebo/speculative tweaks. Use `src/lib/proveIt.ts` `capped_impact`, `matches_wddm_display_critical` guards; zero-value TDR tweaks are often no-ops.
- Report: hypothesis → expected effect → measured effect → inconclusive/regression. Never "optimized" without data outside noise band.
- Startup: profile `probe_scan_cache`, avoid `rayon::par_iter` on hot path, lazy-load off-critical screens.
