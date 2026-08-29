import json, sys, re
try:
    d = json.load(sys.stdin)
except:
    print(json.dumps({"continue": True})); sys.exit(0)

p = (d.get("tool_input") or {}).get("file_path", "")
if not p:
    print(json.dumps({"continue": True})); sys.exit(0)

pl = p.lower().replace("\\", "/")

sensitive_substrings = [
    ".env", ".pem", ".key", "credentials", "secrets",
    "license.dat", "license_hwm.dat", "hwid.dat",
    "audit_signing.key", "applied_tweaks.json",
    "supabase/service_role", "stripe_secret",
]

# Also match exact sensitive filenames at end of path
sensitive_exact = ["secrets.toml", "credentials.json"]

matched = []
for s in sensitive_substrings:
    if s.lower() in pl:
        matched.append(s)

for e in sensitive_exact:
    if pl.endswith(e):
        matched.append(e)

# Check for writing into Roaming/Local SageTweaks state dirs
if "sagetweaks" in pl and any(x in pl for x in ["appdata/roaming", "appdata/local"]):
    matched.append("SageTweaks app data dir")

if matched:
    print(json.dumps({
        "hookSpecificOutput": {"permissionDecision": "ask"},
        "systemMessage": "Sage safety gate: sensitive file write detected (" + ", ".join(matched) + "). Verify this is intentional; never commit secrets. Path: " + p
    }))
else:
    print(json.dumps({"continue": True}))
