#!/usr/bin/env python3
"""
Cheap pre-flight router — deterministic, model-agnostic.
Decides if cheap scout should run, and invokes provider-agnostic adapter if configured.
Fallback to heuristic classify when disabled/unreachable. Never authoritative.
"""
import json, os, re, time
from pathlib import Path

# Routing thresholds from spec §3
SKIP_PATTERNS = [r"simple wording", r"tiny ui", r"one-file", r"documentation.only", r"trivial refactor", r"button text", r"copy change", r"\.md\b.*wording"]
OPTIONAL_PATTERNS = [r"medium feature", r"unfamiliar code", r"moderate debugging", r"dependency.*change"]
STRONG_PATTERNS = [r"security", r"\bwindows\b.*internals", r"registry", r"\bservices\b", r"\bprocesses\b", r"privilege", r"elevation", r"architecture", r"large refactor", r"performance", r"unfamiliar api", r"difficult debug", r"many files", r"large repos", r"current.*document", r"research.*external"]

def should_run(task: str, categories: list, files: list, complexity: str, policy: dict) -> dict:
    text = (task + " " + " ".join(categories) + " " + " ".join(files)).lower()
    preflight = policy.get("preflight", {})
    if not preflight.get("enabled", True):
        return {"decision": "NO", "reason": "preflight disabled in policy", "level": "skip"}

    # Skip checks
    for pat in SKIP_PATTERNS:
        if re.search(pat, text, re.I):
            # but strong patterns override skip if also matches security etc
            for spat in STRONG_PATTERNS:
                if re.search(spat, text, re.I):
                    return {"decision": "YES", "reason": f"strongly recommend: {spat}", "level": "strong"}
            return {"decision": "NO", "reason": f"skip: {pat}", "level": "skip"}

    for pat in STRONG_PATTERNS:
        if re.search(pat, text, re.I):
            return {"decision": "YES", "reason": f"strongly recommend: {pat}", "level": "strong"}

    # file count signals
    if len(files) >= 5:
        return {"decision": "YES", "reason": f"many files ({len(files)})", "level": "strong"}
    if re.search(r"current.*api|current.*behavior|whether.*changed|docs.*lookup", text, re.I):
        return {"decision": "YES", "reason": "research", "level": "strong"}

    for pat in OPTIONAL_PATTERNS:
        if re.search(pat, text, re.I):
            return {"decision": "OPTIONAL", "reason": f"optional: {pat}", "level": "optional"}

    if complexity == "medium":
        return {"decision": "OPTIONAL", "reason": "medium complexity", "level": "optional"}
    if complexity == "simple":
        return {"decision": "NO", "reason": "simple", "level": "skip"}
    return {"decision": "OPTIONAL", "reason": "default optional", "level": "optional"}

def load_policy(repo: Path) -> dict:
    # reuse policy loader
    import importlib.util
    pol_path = Path(__file__).resolve().parents[1] / "policy/policy.py"
    spec = importlib.util.spec_from_file_location("pol", str(pol_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load(repo)

def select_provider(policy: dict):
    providers = policy.get("preflight", {}).get("providers", [])
    # cheapest-first already sorted; check env availability for each, but don't require for simulation
    available = []
    for p in providers:
        key_name = p.get("api_key_env","")
        # if env not set, still considered available for routing decision but invoke will fallback
        has_key = bool(os.getenv(key_name)) if key_name else False
        available.append((p, has_key))
    return available

def invoke_provider(provider: dict, task: str, evidence_hint: str = "") -> dict:
    """Generic OpenAI-compat invoke. If no key, simulate heuristic scout."""
    import urllib.request, urllib.error
    base_env = provider.get("base_url_env","")
    key_env = provider.get("api_key_env","")
    base_url = os.getenv(base_env, "")
    api_key = os.getenv(key_env, "")
    model = provider.get("model","unknown-cheap")
    start = time.time()
    if not base_url or not api_key:
        # Simulation mode: return heuristic evidence pack without network
        latency = int((time.time() - start)*1000)
        # heuristic scout: look for known risky patterns
        findings = []
        if re.search(r"registry.*rollback|HKLM", task, re.I):
            findings.append({"claim": "Potential registry rollback mismatch for HKLM key", "status": "HYPOTHESIS", "files": ["src-tauri/src/tweaks/mod.rs"], "evidence": "No snapshot check found in initial scan", "confidence": 0.65})
        return {
            "model": model,
            "provider": provider.get("provider","generic"),
            "status": "SIMULATED",
            "findings": findings,
            "tokens_in": len(task)//4,
            "tokens_out": 120,
            "cost_usd": round((len(task)/4000)*provider.get("cost_per_1k_in",0.01), 4),
            "latency_ms": latency,
            "simulated": True
        }
    # Real invoke (generic)
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a cheap scout for SageTweaks. Do read-only reconnaissance: find relevant files, symbols, registry paths, security issues, performance hypotheses. Return concise findings with status VERIFIED/STRONG_EVIDENCE/OBSERVATION/HYPOTHESIS/UNKNOWN. Do NOT authorize destructive actions."},
            {"role": "user", "content": f"Task: {task}\nHint: {evidence_hint}\nReturn JSON evidence pack."}
        ],
        "temperature": 0.2,
        "max_tokens": 800
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json", "Authorization": f"Bearer {api_key}"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=provider.get("timeout_ms",8000)/1000) as resp:
            body = json.loads(resp.read().decode())
            text = body["choices"][0]["message"]["content"]
            latency = int((time.time() - start)*1000)
            # try parse JSON inside
            try:
                findings = json.loads(text).get("findings", [])
            except:
                findings = [{"claim": text[:200], "status": "OBSERVATION", "confidence": 0.5}]
            usage = body.get("usage", {})
            return {
                "model": model,
                "provider": provider.get("provider","generic"),
                "status": "OK",
                "findings": findings,
                "tokens_in": usage.get("prompt_tokens", len(task)//4),
                "tokens_out": usage.get("completion_tokens", 200),
                "cost_usd": round(usage.get("prompt_tokens",0)/1000*provider.get("cost_per_1k_in",0) + usage.get("completion_tokens",0)/1000*provider.get("cost_per_1k_out",0), 4),
                "latency_ms": latency,
                "simulated": False
            }
    except Exception as e:
        latency = int((time.time() - start)*1000)
        return {"model": model, "provider": provider.get("provider","generic"), "status": "ERROR", "error": str(e)[:300], "latency_ms": latency, "tokens_in": len(task)//4, "tokens_out": 0, "cost_usd": 0, "simulated": False, "fallback": "heuristic"}

def route(task: str, categories: list = None, files: list = None, complexity: str = "medium", repo: str = ".", evidence_hint: str = "") -> dict:
    categories = categories or []
    files = files or []
    policy = load_policy(Path(repo))
    decision = should_run(task, categories, files, complexity, policy)
    result = {"task_preview": task[:200], "routing": decision, "policy_version": policy.get("version","?"), "preflight_config": policy.get("preflight",{})}
    if decision["decision"] == "NO":
        result["action"] = "CLAUDE_DIRECTLY"
        result["scout"] = None
        return result
    # YES or OPTIONAL: attempt scout if configured
    providers = select_provider(policy)
    # pick cheapest available (first with key, else first)
    chosen = None
    for p, has_key in providers:
        if has_key:
            chosen = p; break
    if not chosen and providers:
        chosen = providers[0][0]
    if not chosen:
        result["action"] = "CLAUDE_DIRECTLY (no provider configured, fallback)"
        result["scout"] = {"status": "NO_PROVIDER", "fallback": "heuristic"}
        return result
    scout_result = invoke_provider(chosen, task, evidence_hint)
    result["action"] = "SCOUT_THEN_CLAUDE"
    result["scout"] = scout_result
    result["provider"] = chosen
    return result

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task")
    p.add_argument("--categories", default="")
    p.add_argument("--files", default="")
    p.add_argument("--complexity", default="medium")
    p.add_argument("--repo", default=".")
    args = p.parse_args()
    task = args.task or ""
    cats = [c.strip() for c in args.categories.split(",") if c.strip()]
    files = [f.strip() for f in args.files.split(",") if f.strip()]
    print(json.dumps(route(task, cats, files, args.complexity, args.repo), indent=2))
