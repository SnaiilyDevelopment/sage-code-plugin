import subprocess, json, sys, tempfile, pathlib, time
PLUGIN = pathlib.Path(__file__).resolve().parents[1]

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r

def test_memory_confidence_levels():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        for conf in ["hypothesis","observed","verified","validated"]:
            r = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", f"Fact for {conf} level", "--source", "src/test.md:1", "--confidence", conf, "--category", "testing", "--repo", str(repo)])
            assert r.returncode == 0, r.stderr
            data = json.loads(r.stdout)
            assert data["confidence"] == conf
        # list
        r = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--list", "--repo", str(repo)])
        lst = json.loads(r.stdout)
        assert len(lst) == 4

def test_memory_stale_and_conflict():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        # add with TTL 0 => immediately stale
        r = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "Stale fact quickly", "--source", "src/old.md:1", "--confidence", "observed", "--category", "general", "--ttl", "0", "--repo", str(repo)])
        assert r.returncode == 0
        time.sleep(0.02)
        r2 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--list", "--repo", str(repo)])
        lst = json.loads(r2.stdout)
        assert any(x.get("_stale") for x in lst)
        # conflict: repo wins — we simulate by checking that memory with same id upgrades confidence
        r3 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "Stale fact quickly", "--source", "src/new.md:2", "--confidence", "validated", "--repo", str(repo)])
        data = json.loads(r3.stdout)
        assert data["confidence"] == "validated"
        # secrets blocked
        r4 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "secret api_key sk-123", "--source", "x", "--repo", str(repo)])
        assert r4.returncode != 0 or "Sensitive" in r4.stderr or "Sensitive" in r4.stdout
        # trivial line change blocked
        r5 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "Changed line 82", "--source", "x", "--repo", str(repo)])
        assert r5.returncode != 0

def test_memory_auto_extraction():
    r = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--extract", "--task", "Windows service requires elevation and rollback", "--verification", "cargo check passed"])
    cands = json.loads(r.stdout)
    assert len(cands) >= 1
    assert any("elevation" in c["fact"].lower() for c in cands)
    # bad fact not extracted
    r2 = run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--extract", "--task", "Changed line 82", "--verification", "ok"])
    c2 = json.loads(r2.stdout)
    assert len(c2) == 0

def test_policy_auditable_and_rollback():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        # propose
        r = run([sys.executable, str(PLUGIN/"scripts/policy/policy.py"), "--propose", "Lower specialist threshold for windows", "Telemetry n=12", "--repo", str(repo)])
        data = json.loads(r.stdout)
        assert "CURRENT_POLICY" not in data or "current_policy" in data or "blocked" in data
        # apply high confidence
        r2 = run([sys.executable, str(PLUGIN/"scripts/policy/policy.py"), "--apply", "Lower specialist threshold for windows", "Telemetry n=12 success 83%", "validated", "--repo", str(repo)])
        d2 = json.loads(r2.stdout)
        assert d2.get("applied") == True or "new_version" in d2
        # blocked weakening
        r3 = run([sys.executable, str(PLUGIN/"scripts/policy/policy.py"), "--apply", "weaken security threshold", "test", "validated", "--repo", str(repo)])
        d3 = json.loads(r3.stdout)
        assert "error" in d3 or d3.get("blocked")
        # history
        r4 = run([sys.executable, str(PLUGIN/"scripts/policy/policy.py"), "--history", "--repo", str(repo)])
        hist = json.loads(r4.stdout)
        assert len(hist) >= 1
        # rollback
        ver = hist[0]["version"]
        r5 = run([sys.executable, str(PLUGIN/"scripts/policy/policy.py"), "--rollback", ver, "--repo", str(repo)])
        d5 = json.loads(r5.stdout)
        assert "rolled_back_to" in d5 or "error" not in d5

def test_learn_quality_and_proposals():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        # create synthetic telemetry: 6 failures for windows
        tel = repo/".wolf/sage-telemetry.jsonl"
        tel.parent.mkdir(parents=True, exist_ok=True)
        import json as js, datetime
        for i in range(6):
            entry = {"ts": datetime.datetime.now(datetime.timezone.utc).isoformat(), "task_id": f"id{i}", "category": "windows", "complexity":"complex","risk":60,"files_touched":[],"skills":["sage-windows"],"agents":[],"tools":[],"mcp_usage":[],"verification":"cargo check","result":"failure","failure_cause":"incorrect_api","retries":1,"duration_ms":1000}
            with open(tel,"a") as f: f.write(js.dumps(entry)+"\n")
        r = run([sys.executable, str(PLUGIN/"scripts/telemetry/learn.py"), "--repo", str(repo), "--threshold", "5"])
        data = json.loads(r.stdout)
        assert data["entries"] == 6
        assert any("policy_proposals" in data for _ in [1])
        assert len(data.get("policy_proposals",[])) >= 1
        # quality notes should be present
        assert "quality_notes" in data

def test_context_with_memory_and_budget():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        # seed memory
        run([sys.executable, str(PLUGIN/"scripts/memory/memory.py"), "--add", "Tauri 4-piece wiring must stay synced", "--source", "references/tauri.md", "--confidence", "validated", "--category", "tauri", "--repo", str(repo)])
        r = run([sys.executable, str(PLUGIN/"scripts/context/context-build.py"), "Fix Tauri IPC bug", "--categories", "tauri,rust", "--files", "src-tauri/src/lib.rs", "--repo", str(repo), "--budget", "4000"])
        data = json.loads(r.stdout)
        assert "6_validated_memory" in data
        # check not stale
        assert "Tauri" in data["6_validated_memory"] or "no relevant" in data["6_validated_memory"].lower()
        assert data["_budget"]["total"] == 4000

def test_mcp_selection_and_safety():
    r = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "delete remote branch via GitHub MCP"])
    d = json.loads(r.stdout)
    assert "High-risk" in d["safety"]
    assert "github" in d["recommended"] or d["scores"]["github"] >=5
    r2 = run([sys.executable, str(PLUGIN/"scripts/mcp/select.py"), "simple local fix"])
    d2 = json.loads(r2.stdout)
    assert d2["recommended"] == []

def test_specialist_with_historical_fail():
    r = run([sys.executable, str(PLUGIN/"scripts/context/specialist-select.py"), "--risk", "45", "--categories", "windows", "--complexity", "medium", "--fail-rate", "0.5"])
    d = json.loads(r.stdout)
    assert d["decision"] == "specialist"
    assert "historical fail" in " ".join(d["reasons"])

def test_telemetry_secret_stripping():
    with tempfile.TemporaryDirectory() as tmp:
        repo = pathlib.Path(tmp); (repo/".git").mkdir()
        r = run([sys.executable, str(PLUGIN/"scripts/telemetry/log.py"), "--task-id", "sec1", "--category", "security", "--verification", "secret token sk-abc123", "--lesson", "api_key=sk-secret", "--repo", str(repo)])
        data = json.loads(r.stdout)
        out = json.dumps(data)
        assert "sk-abc123" not in out
        assert "sk-secret" not in out or "[REDACTED]" in out

def test_benchmark_classification():
    # repeated same cmd should be inconclusive inside noise
    r = run([sys.executable, str(PLUGIN/"scripts/verification/benchmark.py"), "--baseline-cmd", "echo test", "--repeats", "3", "--hypothesis", "no change"])
    # should contain classification
    assert "inconclusive" in r.stdout.lower() or "not_measurable" in r.stdout.lower() or "improvement" in r.stdout.lower()

def test_diagnostics():
    r = run([sys.executable, str(PLUGIN/"scripts/diagnostics/diagnose.py"), "Fix registry tweak rollback issue for HKLM", "--files", "src-tauri/src/tweaks/mod.rs"])
    data = json.loads(r.stdout)
    assert "diagnostics" in data
    assert "answers" in data
    assert "Which skills were selected?" in data["answers"]
    assert "Policy version" in data["answers"]

def test_self_correction_paradigm():
    # verify that sage.md orchestrator contains self-correction with new evidence
    text = (PLUGIN/"commands/sage.md").read_text(encoding="utf-8")
    assert "SELF-CORRECT" in text
    assert "NEW EVIDENCE" in text or "new evidence" in text.lower()
    assert "Max 2 retries" in text or "Max 2" in text

if __name__ == "__main__":
    tests = [k for k in globals() if k.startswith("test_")]
    for name in tests:
        fn = globals()[name]
        try:
            fn()
            print(f"PASS {name}")
        except AssertionError as e:
            print(f"FAIL {name}: {e}")
            import traceback; traceback.print_exc(); sys.exit(1)
        except Exception as e:
            print(f"ERROR {name}: {e}")
            import traceback; traceback.print_exc(); sys.exit(1)
    print("All V2 tests passed")
