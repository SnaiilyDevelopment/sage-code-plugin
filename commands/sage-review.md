---
name: sage-review
description: Risk-gated review of the current diff for correctness, security, regression, and architecture.
---

# /sage-review

Risk-aware review (V1.1 policy).

1. Get diff: `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/git-summary.py --cwd ."` and `git diff`.
2. Risk-assess: `python "${CLAUDE_PLUGIN_ROOT}/scripts/safety/risk-score.py" "<task>" --files "<diff files>"`
3. Specialist decision: `python "${CLAUDE_PLUGIN_ROOT}/scripts/context/specialist-select.py" --risk <score> --categories "<cats>" --complexity <c> --files "<diff>"`
4. Gate:
   - **Low 0-24** (text/style/docs): no specialist review
   - **Medium 25-49** (feature/moderate refactor): deterministic verification + self-review
   - **High 50-74** (registry/services/privileges/auth/security/large arch): specialist review
   - **Critical 75+** (destructive/privilege-sensitive/high-impact): specialist + stronger verification + rollback analysis
5. Check: correctness, regressions, Windows 10/11, Rust/Tauri 4-piece wiring, security/privilege, rollback, test evidence, complexity, secrets staged.
6. Return findings by severity (blocker / important / suggestion). Do not modify files unless user asks. Consider historical failure rate from `python scripts/telemetry/learn.py --threshold 5` if available.
