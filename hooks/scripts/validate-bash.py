import json, sys, re
try:
    d = json.load(sys.stdin)
except:
    print(json.dumps({"continue": True}))
    sys.exit(0)

cmd = (d.get("tool_input") or {}).get("command", "")
if not cmd:
    print(json.dumps({"continue": True})); sys.exit(0)

# Destructive / high-risk patterns — each maps to permissionDecision ask
patterns = [
    (r"Remove-Item\s+.*-Recurse.*-Force", "Recursive force delete (PowerShell)"),
    (r"del\s+/[sfq]", "Windows del /s /f /q"),
    (r"format\s+[A-Za-z]:", "Disk format"),
    (r"git\s+reset\s+--hard", "git reset --hard (destructive)"),
    (r"git\s+clean\s+-fd", "git clean -fd (destructive)"),
    (r"rm\s+-rf\s+/", "rm -rf / (destructive)"),
    (r"rm\s+-rf\s+~", "rm -rf ~ (destructive)"),
    (r"reg\s+delete", "Registry delete"),
    (r"reg\s+add\s+.*HKLM", "HKLM registry write"),
    (r"sc\s+delete", "Service delete"),
    (r"sc\s+config\s+.*start=\s*disabled", "Service disable"),
    (r"bcdedit", "Boot config edit"),
    (r"compact\s+/compactos", "CompactOS toggle"),
    (r"Remove-Item\s+.*HKLM", "PowerShell HKLM removal"),
    (r"powershell.*EncodedCommand", "Encoded PowerShell"),
    (r"Invoke-Expression.*http", "Remote code invoke"),
    (r"curl.*\|\s*sh", "Pipe curl to shell"),
    (r"wget.*\|\s*sh", "Pipe wget to shell"),
]

matched = []
for pat, desc in patterns:
    if re.search(pat, cmd, re.I):
        matched.append(desc)

# Bulk file operation guard: >10 files via wildcard delete
if re.search(r"rm\s+.*\*", cmd) and "node_modules" not in cmd:
    matched.append("Wildcard rm")

if matched:
    print(json.dumps({
        "hookSpecificOutput": {"permissionDecision": "ask"},
        "systemMessage": "Sage safety gate: potentially destructive/high-risk command detected: " + "; ".join(matched) + ". Verify scope before execution."
    }))
else:
    print(json.dumps({"continue": True}))
