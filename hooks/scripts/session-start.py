import json, sys, os
from pathlib import Path

try:
    data = json.load(sys.stdin)
except:
    data = {}

# Find plugin root via env or file location
plugin_root = Path(__file__).resolve().parents[2]
repo = Path(os.getcwd())

# Load repo map if present
arch = plugin_root / "references" / "sage-architecture.md"
wolf_map = repo / ".wolf" / "sage-map.json"

msg_parts = ["SageTweaks plugin active (v1.0.0)."]

if arch.exists():
    # show first line of arch for context
    first = arch.read_text(encoding="utf-8", errors="ignore").splitlines()[0:2]
    msg_parts.append("Repo map: " + " ".join(first).strip()[:200])

if wolf_map.exists():
    msg_parts.append("Cached intelligence: .wolf/sage-map.json")

msg_parts.append("Workflow: /sage (primary) → classify → risk assess → load skill → implement → verify → review if risky.")
msg_parts.append("Keep changes minimal, evidence-based. Claim performance only with measured baseline→compare.")

# Output as system message — Claude will see this
print(" ".join(msg_parts))
# Also emit JSON continue
# Hooks that output text directly are shown as system reminders; ensure JSON also
try:
    print(json.dumps({"continue": True, "systemMessage": " ".join(msg_parts)}))
except:
    pass
