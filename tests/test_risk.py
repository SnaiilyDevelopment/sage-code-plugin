import subprocess, json, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN / "scripts" / "safety" / "risk-score.py"

def score(task, files="", complexity="medium"):
    cmd = [sys.executable, str(SCRIPT), task]
    if files: cmd += ["--files", files]
    cmd += ["--complexity", complexity]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)

def test_low_risk():
    out = score("Change button text wording")
    assert out["risk_score"] <= 24, f"expected low, got {out['risk_score']}"
    assert out["tier"] == "low"

def test_registry_high():
    out = score("Apply registry change to HKLM System power service", "src-tauri/src/tweaks/impls/power.rs", "complex")
    assert out["risk_score"] >= 25
    assert out["dimensions"]["system_impact"] >= 7

def test_destructive_critical():
    out = score("Delete registry keys and reset services with bcdedit and format", "src-tauri/src/tweaks/mod.rs", "complex")
    # destructive + system_impact high
    assert out["risk_score"] >= 50

def test_security_high():
    out = score("Audit privilege escalation and elevation path", "", "complex")
    assert out["dimensions"]["security"] >= 7

def test_thresholds():
    out = score("Update docs", "", "simple")
    assert out["risk_score"] <= 24
    out2 = score("Refactor architecture for queue and service boundary", "a.rs,b.rs,c.rs,d.rs,e.rs,f.rs", "complex")
    assert out2["dimensions"]["architecture"] >= 5

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All risk tests passed")
