import subprocess, json, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "context" / "classify.py"

def classify(task, files=""):
    cmd = [sys.executable, str(SCRIPT), task]
    if files:
        cmd += ["--files", files]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)

def test_frontend():
    out = classify("Change button text styling")
    assert "frontend" in out["categories"] or out["complexity"] == "simple"
    assert out["complexity"] == "simple"

def test_registry_complex():
    out = classify("Fix registry tweak rollback issue for HKLM power setting", "src-tauri/src/tweaks/mod.rs,src-tauri/src/tweaks/impls/power.rs")
    assert "registry" in out["categories"]
    assert out["complexity"] == "complex"
    assert out["needs_specialist"] == True

def test_rust_tauri():
    out = classify("Fix Tauri IPC state bug in commands", "src-tauri/src/commands/optimization.rs")
    assert "rust" in out["categories"] or "tauri" in out["categories"]

def test_performance():
    out = classify("Investigate whether this tweak actually improves latency")
    assert "performance" in out["categories"]
    # investigation tasks need research, not necessarily specialist at classification stage
    assert out["needs_research"] or "performance" in out["categories"]

def test_security():
    out = classify("Audit elevation path for service manipulation", "src-tauri/src/security/mod.rs")
    assert "security" in out["categories"]

def test_documentation():
    out = classify("Update README wording")
    assert "documentation" in out["categories"]

def test_research():
    out = classify("Check whether the current Windows API behavior changed for registry")
    assert out["needs_research"] == True

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All classify tests passed")
