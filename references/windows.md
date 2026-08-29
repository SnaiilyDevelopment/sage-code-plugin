# Windows Reference — SageTweaks

> Authority: local repo + Microsoft Learn. Verify before implying behavior.

## OS Differences

| Area | Windows 10 | Windows 11 |
|------|-----------|-----------|
| Registry | Same hive layout; some keys missing (e.g., 11-only DWM) | Extra DWM/scheduler keys; validate existence before write |
| Power | `powercfg` GUIDs stable, but 11 adds Efficiency Mode | Check `powercfg /list` on target OS |
| Scheduler | Legacy foreground boost | 11 has additional QoS; avoid placebo tweaks |
| Services | Similar | 11 has extra telemetry services — do not bulk-disable |

## Hives & Privilege

- **HKCU** — per-user, no elevation, reversible by user.
- **HKLM** — machine-wide, requires elevation (`requireAdministrator`), affects all users. High risk.
- **HKLM\SYSTEM\CurrentControlSet\Services** — service config; wrong `Start` value bricks boot. Always snapshot before change.
- **UAC/elevation**: App runs elevated (Tauri `requireAdministrator`, NSIS `perMachine`). Never assume non-elevated works. Test both.

## Safe Patterns

- **Snapshot before write**: `reg export <key> backup.reg` or store original value in `applied_tweaks.json` / `revert_vault`.
- **Rollback path**: every tweak must have inverse operation documented in `src-tauri/src/tweaks/impls/*.rs` and `optimization_state.rs:AppliedTweakRecord`.
- **Validate after apply**: re-read key, confirm `Get-ItemProperty` matches intended value.
- **Compatibility**: check `profile_tweak_filters::matches_wddm_display_critical()` — skip WDDM/TDR-zero tweaks on unsafe hardware.

## Dangerous Operations (require risk≥50 + review)

- `reg delete HKLM\...`, `sc delete`, `bcdedit`, `compact /compactos`, `powercfg /deletescheme`, `netsh advfirewall`, `taskkill /f /im svchost*`.

## Power / Scheduler / Networking

- `powercfg`: export scheme before change (`powercfg /export`), restore on rollback.
- Scheduler tweaks: measure with presentmon / latency probe; do not claim FPS gain without baseline.
- Networking: `netsh`, `iperf3` binary in `src-tauri/binaries/` — prefer measured iperf3 runs over registry speculation.

## Tools

- `reg query`, `reg export`, `sc query`, `sc qc`, `powercfg /query`, `Get-Service`, `Get-ItemProperty`.
