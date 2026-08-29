import json, sys, subprocess, re
from pathlib import Path

try:
    d = json.load(sys.stdin)
except:
    print(json.dumps({"continue": True})); sys.exit(0)

tool = d.get("tool_name", "") or d.get("tool", "")
inp = d.get("tool_input") or {}
file_path = inp.get("file_path", "")

if not file_path or not re.search(r"\.(ts|tsx|js|jsx|rs)$", file_path):
    print(json.dumps({"continue": True})); sys.exit(0)

# Lightweight: only warn if file appears to have obvious formatting issues
# We do not auto-format here; PostToolUse is advisory
# Check for trailing whitespace or missing newline via quick read (if file exists)
p = Path(file_path)
if p.exists():
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
        issues = []
        if txt and not txt.endswith("\n"):
            issues.append("missing final newline")
        if re.search(r"[ \t]+$", txt, re.M):
            issues.append("trailing whitespace")
        if issues:
            print(json.dumps({
                "continue": True,
                "systemMessage": f"Sage quality: formatting hint for {file_path}: {', '.join(issues)}. Run formatter if needed."
            }))
            sys.exit(0)
    except:
        pass

print(json.dumps({"continue": True}))
