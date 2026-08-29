---
name: sage-windows
description: Use for Windows 10/11, registry, services, processes, privileges, UAC, power, networking, system APIs, rollback, compatibility.
version: 1.0.0
---

# Sage Windows

Canonical Windows expertise (alias: `windows-tweaks`).

## Coverage

- **OS deltas**: Win10 vs 11 — DWM, scheduler QoS, Efficiency Mode, service lists. Validate key exists before write.
- **Registry**: `HKCU` (per-user, reversible) vs `HKLM` (machine, elevated, high risk). `HKLM\SYSTEM\CurrentControlSet\Services` — wrong `Start` bricks boot.
- **Services**: `sc query`/`sc qc`/`sc config`/`sc delete` — snapshot `Start`/`ImagePath` before change.
- **Processes**: `taskkill`/`Get-Process`/`CreateProcess`/sidecars — never kill `svchost*` without allowlist.
- **Privileges**: `requireAdministrator`, UAC, `perMachine` NSIS. Test elevated and non-elevated paths.
- **Power**: `powercfg` GUIDs, `/export`/`/import` for rollback.
- **Networking**: `netsh`, `iperf3`, firewall rules — measure, don't speculate.
- **System APIs**: WMI, WinAPI, registry via `winreg` crate — prefer documented, reversible calls.

## Safety

- Snapshot → modify → re-read → verify. Store original in `AppliedTweakRecord` + `revert_vault/`.
- Gate display-critical tweaks via `matches_wddm_display_critical()`.
- Risk≥50 + specialist review for `reg delete HKLM`, `sc delete`, `bcdedit`, `compact`, TDR-zero tweaks.
- Never claim FPS/latency gain without `presentmon` baseline→compare outside noise band.

See `references/windows.md` for deep reference.
