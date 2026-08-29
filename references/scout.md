# Scout — Cheap Pre-Flight Reconnaissance

> Read-only checklist for cheap scout (`scripts/routing/preflight.py`). Leveraged by `tweak_status_probes.rs` / `registry_probe.rs` / `probe_scan_cache.rs` in the target repo. Never invent paths.

## Checklist (≤800 tokens, <2s)

- [ ] **Relevant files** via `rg --files-with-matches` for tweak_id / symbol (`TweakInfo`, `AppliedTweakRecord`, `HKLM\SYSTEM\CurrentControlSet\Services`)
- [ ] **Symbols** line-anchored: `rg -n "fn get_tweak_status|RegKey::open|matches_wddm"` `src-tauri/src/tweaks`
- [ ] **Registry probe** read-only: `reg query HKLM\... /v Start` expected `NOT_FOUND | Applied | Unknown` — do not write
- [ ] **Service probe** `sc query` / `Get-CimInstance Win32_Service` for startup type
- [ ] **WMI class probe** `Win32_Processor`, `Win32_VideoController` via `hardware_detection.rs` — existence only
- [ ] **Binary presence** `Test-Path src-tauri/binaries/presentmon-x86_64*`
- [ ] **WDDM gate** `rg -n "TdrLevel|TdrDelay|HwSchMode" src-tauri/src/tweaks --json | matches_wddm_display_critical()`
- [ ] **Dependencies** `cargo metadata` affected crates vs `tweaks/types.rs`
- [ ] **Related tests** `rg -l "*.test.*|cargo test -- --list"`
- [ ] **Apply reversibility** `AppliedTweakRecord` snapshot exists? `revert_vault/` path?

## Output

Evidence pack via `scripts/routing/evidence.py` with tagged findings `VERIFIED | STRONG_EVIDENCE | OBSERVATION | HYPOTHESIS | UNKNOWN`, file:symbol:line, source provenance, cost tracking.

## Safety

Scout is read-only. Never `reg delete`, `sc delete`, `bcdedit`, or secret access. Hooks remain authoritative.
