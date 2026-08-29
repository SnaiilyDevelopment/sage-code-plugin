import json, sys, subprocess, re, os
from pathlib import Path

try:
    data = json.load(sys.stdin)
except:
    print(json.dumps({"continue": True})); sys.exit(0)

def run(cmd, cwd=None):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=8, cwd=cwd)
        return r.stdout.strip()
    except:
        return ""

cwd = os.getcwd()
repo = None
p = Path(cwd)
for parent in [p] + list(p.parents):
    if (parent / ".git").exists():
        repo = str(parent)
        break

if not repo:
    print(json.dumps({"continue": True})); sys.exit(0)

diff_stat = run("git diff --stat", cwd=repo)
diff_cached = run("git diff --cached --stat", cwd=repo)
changed = run("git diff --name-only", cwd=repo)
diff_text = run("git diff", cwd=repo)
has_changes = bool(diff_stat or diff_cached)

if not has_changes:
    print(json.dumps({"continue": True})); sys.exit(0)

changed_files = [l.strip() for l in changed.splitlines() if l.strip()]
is_docs_only = all(re.search(r"\.md$|docs/|README", f, re.I) for f in changed_files) if changed_files else False

if is_docs_only:
    print(json.dumps({"continue": True})); sys.exit(0)

# Completion intelligence V1.1
issues = []
warnings = []

if len(changed_files) > 15:
    issues.append(f"Large diff ({len(changed_files)} files) — ensure targeted verification ran and scope matches request")

for f in changed_files:
    if re.search(r"\.env|secrets|credentials|\.pem|\.key|license\.dat|hwid\.dat|audit_signing\.key", f, re.I):
        issues.append(f"Sensitive file in diff: {f}")
    if re.search(r"package-lock\.json|pnpm-lock\.yaml|Cargo\.lock", f) and len(changed_files) > 5:
        warnings.append(f"Lockfile churn: {f} — verify intentional")

# TODO left unresolved
if re.search(r"TODO|FIXME|HACK|XXX", diff_text):
    warnings.append("TODO/FIXME/HACK found in diff — ensure no important TODO left unresolved")

# Unrelated changes heuristic: many distinct directories
dirs = set(os.path.dirname(f) for f in changed_files)
if len(dirs) > 5 and len(changed_files) > 8:
    warnings.append(f"Changes span {len(dirs)} directories — check for unrelated changes")

# No test file changed but source changed (for medium+ changes)
has_test_change = any(re.search(r"\.test\.|__tests__", f) for f in changed_files)
has_source = any(re.search(r"\.(ts|tsx|rs)$", f) for f in changed_files)
if has_source and not has_test_change and len(changed_files) > 3:
    warnings.append("Source changed without test — consider regression test if fixing bug")

# Combine
all_notes = []
if issues:
    all_notes.append("Blockers:\n- " + "\n- ".join(issues))
if warnings:
    all_notes.append("Warnings:\n- " + "\n- ".join(warnings))

if all_notes:
    print(json.dumps({
        "continue": True,
        "systemMessage": "Sage completion gate V1.1 — review before declaring success:\n" + "\n\n".join(all_notes) + "\n\nVerify: intended behavior implemented, expected files changed, appropriate tests/checks passed, no secrets, no unrelated changes, result matches user request. Tiny changes exempt from huge suites."
    }))
else:
    print(json.dumps({
        "continue": True,
        "systemMessage": "Sage completion gate V1.1: verify before finishing — intended behavior implemented, expected files changed, appropriate tests/checks passed, no unrelated/secrets, no TODO left, result matches request. (Docs-only exempt.)"
    }))
