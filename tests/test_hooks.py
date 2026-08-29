import subprocess, json, sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]

def run_hook(script, payload):
    cmd = [sys.executable, str(PLUGIN / script)]
    r = subprocess.run(cmd, input=json.dumps(payload), capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)

def test_validate_bash_blocks_reg_delete():
    out = run_hook("hooks/scripts/validate-bash.py", {"tool_input": {"command": "reg delete HKLM\\Software\\Test /f"}})
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "ask"

def test_validate_bash_blocks_sc_delete():
    out = run_hook("hooks/scripts/validate-bash.py", {"tool_input": {"command": "sc delete MyService"}})
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "ask"

def test_validate_bash_allows_safe():
    out = run_hook("hooks/scripts/validate-bash.py", {"tool_input": {"command": "pnpm build"}})
    assert out.get("continue") == True

def test_validate_bash_blocks_rm_rf():
    out = run_hook("hooks/scripts/validate-bash.py", {"tool_input": {"command": "rm -rf /"}})
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "ask"

def test_validate_write_blocks_env():
    out = run_hook("hooks/scripts/validate-write.py", {"tool_input": {"file_path": "C:/project/.env"}})
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "ask"

def test_validate_write_blocks_license():
    out = run_hook("hooks/scripts/validate-write.py", {"tool_input": {"file_path": "C:/Users/AppData/Roaming/SageTweaks/license.dat"}})
    assert out.get("hookSpecificOutput", {}).get("permissionDecision") == "ask"

def test_validate_write_allows_normal():
    out = run_hook("hooks/scripts/validate-write.py", {"tool_input": {"file_path": "C:/project/src/App.tsx"}})
    assert out.get("continue") == True

def test_secret_strip():
    cmd = [sys.executable, str(PLUGIN / "scripts/safety/secret-strip.py")]
    inp = "api_key: 'sk-1234-secret' and Bearer abc123.token"
    r = subprocess.run(cmd, input=inp, capture_output=True, text=True)
    assert "[REDACTED]" in r.stdout
    assert "sk-1234" not in r.stdout

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS {name}")
            except AssertionError as e:
                print(f"FAIL {name}: {e}")
                sys.exit(1)
    print("All hook tests passed")
