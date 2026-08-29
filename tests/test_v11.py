import subprocess, json, sys, tempfile, pathlib

PLUGIN = pathlib.Path(__file__).resolve().parents[1]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r

def test_skill_select_relevance():
    # Registry+Tauri+Rust+security => 4 skills
    r = run([sys.executable, str(PLUGIN/"scripts/context/skill-select.py"), "Registry + Tauri + Rust + security HKLM Tauri IPC", "--categories", "registry,tauri,rust,security", "--files", "src-tauri/src/tweaks/mod.rs"])
    data = json.loads(r.stdout)
    assert "skills/sage-core/SKILL.md" in data["selected"]
    assert "skills/sage-windows/SKILL.md" in data["selected"]
    assert "skills/sage-tauri/SKILL.md" in data["selected"]
    assert "skills/security/SKILL.md" in data["selected"]
    assert len(data["selected"]) == 4, f"expected 4 got {data['selected']}"

def test_skill_select_simple_frontend():
    r = run([sys.executable, str(PLUGIN/"scripts/context/skill-select.py"), "Change button text", "--categories", "frontend"])
    data = json.loads(r.stdout)
    assert data["selected"] == ["skills/sage-core/SKILL.md"]

def test_skill_select_performance_research():
    r = run([sys.executable, str(PLUGIN/"scripts/context/skill-select.py"), "Investigate whether this tweak actually improves latency", "--categories", "performance,research"])
    data = json.loads(r.stdout)
    assert "skills/sage-core/SKILL.md" in data["selected"]
    assert "skills/performance/SKILL.md" in data["selected"]
    assert "skills/sage-research/SKILL.md" in data["selected"]
    assert "skills/sage-git/SKILL.md" not in data["selected"]

def test_skill_select_budget_respected():
    # budget 1000 => only sage-core + one other max
    r = run([sys.executable, str(PLUGIN/"scripts/context/skill-select.py"), "Registry + Tauri + Rust + security", "--categories", "registry,tauri,rust,security", "--budget", "1000"])
    data = json.loads(r.stdout)
    # sage-core 800 + next 700+ exceeds 1000? Let's check: sage-core always, then budget limits others
    # With 1000 budget, only one additional skill should fit besides sage-core? Our budget is for non-core, core is separate? Check impl: budget is for non-core only, so 1000 allows only 1
    assert len(data["selected"]) <= 2

def test_context_budget():
    r = run([sys.executable, str(PLUGIN/"scripts/context/context-build.py"), "Fix registry tweak rollback issue for HKLM", "--categories", "windows,registry", "--files", "src-tauri/src/tweaks/mod.rs,src-tauri/src/tweaks/impls/power.rs", "--budget", "3000"])
    data = json.loads(r.stdout)
    assert "4_skills" in data
    assert "6_validated_memory" in data
    assert "_budget" in data
    assert data["_budget"]["total"] == 3000

def test_mcp_select():
    r = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "Investigate PR #123 on GitHub"])
    data = json.loads(r.stdout)
    assert "github" in data["recommended"]
    r2 = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "Check whether Tauri v2 API changed"])
    d2 = json.loads(r2.stdout)
    assert "documentation" in d2["recommended"]
    r3 = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "Fix button text"])
    d3 = json.loads(r3.stdout)
    assert d3["recommended"] == []

def test_mcp_safety():
    r = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "delete remote branch via GitHub"])
    data = json.loads(r.stdout)
    assert "High-risk" in data["safety"]

def test_failure_classify():
    r = run([sys.executable, str(PLUGIN/"scripts/telemetry/failure-classify.py"), "cargo check error: failed to compile"])
    data = json.loads(r.stdout)
    assert data["failure_cause"] == "build_failure"
    r2 = run([sys.executable, str(PLUGIN/"scripts/telemetry/failure-classify.py"), "FAIL test_button.test.ts AssertionError"])
    d2 = json.loads(r2.stdout)
    assert d2["failure_cause"] == "test_failure"

def test_specialist_select():
    r = run([sys.executable, str(PLUGIN/"scripts/context/specialist-select.py"), "--risk", "60", "--categories", "registry", "--complexity", "complex", "--files", "src-tauri/src/tweaks/mod.rs"])
    data = json.loads(r.stdout)
    assert data["decision"] == "specialist"
    assert "sage-windows" in data["specialist"] or "reviewer" in data["specialist"]
    r2 = run([sys.executable, str(PLUGIN/"scripts/context/specialist-select.py"), "--risk", "10", "--categories", "frontend", "--complexity", "simple"])
    d2 = json.loads(r2.stdout)
    assert d2["decision"] == "claude_alone"

def test_memory_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp)
        (repo/".git").mkdir()
        r = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "Test fact with provenance", "--source", "test.md:1", "--category", "testing", "--confidence", "high", "--repo", str(repo)])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["fact"] == "Test fact with provenance"
        assert data["source"] == "test.md:1"
        # no secrets
        r2 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "secret token abc", "--source", "x", "--repo", str(repo)])
        assert r2.returncode != 0 or "Sensitive" in r2.stdout or "Sensitive" in r2.stderr

def test_telemetry_v11():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp)
        (repo/".git").mkdir()
        r = run([sys.executable, str(PLUGIN/"scripts/telemetry/log.py"), "--task-id", "test123", "--category", "windows", "--complexity", "complex", "--risk", "50", "--files", "src-tauri/src/tweaks/mod.rs", "--skills", "sage-core,sage-windows", "--agents", "sage-windows-specialist", "--mcp", "github", "--verification", "cargo check", "--result", "success", "--failure-cause", "", "--retries", "1", "--duration-ms", "5000", "--lesson", "test lesson", "--repo", str(repo)])
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["task_id"] == "test123"
        assert data["mcp_usage"] == ["github"]
        assert data["failure_cause"] == ""
        # verify file written
        p = repo/".wolf"/"sage-telemetry.jsonl"
        assert p.exists()
        lines = p.read_text().strip().splitlines()
        assert len(lines) == 1

def test_learn():
    # learn should handle empty or few entries without crashing
    r = run([sys.executable, str(PLUGIN/"scripts/telemetry/learn.py"), "--repo", str(PLUGIN), "--threshold", "1"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    # may be no data or entries
    assert "entries" in data or "status" in data

if __name__ == "__main__":
    tests = [k for k in globals() if k.startswith("test_")]
    for name in tests:
        fn = globals()[name]
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR {name}: {e}")
            sys.exit(1)
    print("All V1.1 tests passed")
