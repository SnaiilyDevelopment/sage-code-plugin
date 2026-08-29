---
name: windows-tweaks
description: Use for Windows registry, services, processes, power, scheduler, networking, system tweaks, permissions, or performance behavior.
version: 1.0.0
---

# Windows Tweaks

Windows system-level expertise for SageTweaks.

- Identify exact OS/API behavior before changing it — check `references/windows.md`, Microsoft Learn, or local `reg query`/`sc query`/`powercfg /query`.
- Prefer documented APIs and reversible operations. Snapshot original value before write (`reg export`, `powercfg /export`, store in `AppliedTweakRecord`).
- Preserve explicit rollback path — inverse operation for every tweak.
- Consider elevation and privilege boundaries (`HKLM` vs `HKCU`, `requireAdministrator`, UAC, `perMachine` install).
- Distinguish Windows 10 and Windows 11 behavior; validate hive existence before write.
- Never claim a tweak improves FPS/latency without measured baseline→compare (`references/engineering-rules.md` performance bar, use `presentmon`/`diskspd`/`iperf3`).
- Validate affected state after apply (re-read registry, `Get-ItemProperty`, `sc qc`).
- High-risk (risk≥50): `reg delete`, `sc delete`, `bcdedit`, `compact`, service `Start` edits — require specialist review + rollback plan.
- Check `profile_tweak_filters::matches_wddm_display_critical()` to gate display-critical tweaks.

See also: `skills/sage-windows/SKILL.md` (canonical) and `references/windows.md`.
