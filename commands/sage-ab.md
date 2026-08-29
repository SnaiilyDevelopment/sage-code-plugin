# /sage-ab — A/B experiment: Claude direct vs Scout→Claude
Run repeatable experiment to measure scout value.
Usage: /sage-ab "task" --control --treatment --runs 3 --repo .
Measures: Claude tokens, total tokens, scout tokens, cost, duration, retries, tool calls, success, verified issues, false positives → net deltas.
See scripts/telemetry/ab.py and scripts/telemetry/learn.py ab comparison.
Do not store secrets; metrics anonymized local.
