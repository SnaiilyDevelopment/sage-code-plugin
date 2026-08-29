import subprocess, json, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]

def test_context_build():
    script = PLUGIN / "scripts" / "context" / "context-build.py"
    cmd = [sys.executable, str(script), "Fix registry tweak", "--categories", "windows,registry,rust", "--files", "src-tauri/src/tweaks/mod.rs"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "1_task" in data
    assert "2_repo_map" in data
    assert "4_skills" in data
    # should include sage-windows
    assert any("sage-windows" in s or "windows" in s for s in data["4_skills"])

def test_git_summary():
    script = PLUGIN / "scripts" / "context" / "git-summary.py"
    # run in plugin dir (may not be git repo for tests, so check fallback)
    r = subprocess.run([sys.executable, str(script), "--cwd", str(PLUGIN)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert "branch" in data
    assert "changed_files" in data

def test_repo_map():
    script = PLUGIN / "scripts" / "context" / "repo-map.py"
    r = subprocess.run([sys.executable, str(script), "--repo", "C:/Users/SageOS/Documents/GitHub/sage-tweaks"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # stdout is JSON, stderr has paths
    # find JSON part
    out = r.stdout
    data = json.loads(out)
    assert data["product"] == "SageTweaks"
    assert "version" in data

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All context tests passed")
