#!/usr/bin/env python3
"""
Deterministic task classifier — no LLM.
Input: task text (arg or stdin) + optional --files comma list
Output: JSON with category, complexity, affected components, verification, needs_* flags
"""
import sys, json, re, argparse

CATEGORIES = {
    "frontend":    [r"react", r"component", r"\bui\b", r"tsx", r"css", r"tailwind", r"view", r"page", r"frontend", r"styling", r"button", r"\btoggle\b", r"settings.*ui"],
    "backend":     [r"api\b", r"backend", r"express", r"supabase", r"prisma", r"route", r"handler.*http", r"middleware"],
    "database":    [r"prisma", r"migration", r"schema\.prisma", r"supabase", r"sql", r"database", r"\bdb\b"],
    "rust":        [r"\brust\b", r"cargo", r"\.rs\b", r"src-tauri", r"serde", r"tokio"],
    "tauri":       [r"tauri", r"\bipc\b", r"invoke\(.*\)", r"command.*tauri", r"webview", r"capability", r"permission\.toml"],
    "windows":     [r"windows", r"win32", r"registry", r"\bHKLM\b", r"\bHKCU\b", r"powershell", r"service", r"process", r"wmi", r"winapi", r"uac", r"elevation"],
    "registry":    [r"registry", r"HKLM", r"HKCU", r"reg add", r"reg delete", r"RegSetValue", r"RegCreateKey"],
    "services":    [r"\bservice\b", r"sc config", r"sc delete", r"sc create", r"services\.msc", r"systemd"],
    "processes":   [r"process", r"taskkill", r"Get-Process", r"CreateProcess", r"sidecar", r"presentmon", r"smartctl"],
    "networking":  [r"network", r"tcp", r"udp", r"dns", r"firewall", r"netsh", r"iperf3", r"http", r"fetch"],
    "authentication": [r"auth", r"license", r"hwid", r"supabase.*auth", r"jwt", r"session", r"oauth"],
    "security":    [r"security", r"privilege", r"elevation", r"secret", r"token", r"cve", r"audit", r"permission", r"xss", r"injection"],
    "performance": [r"performance", r"\bfps\b", r"latency", r"startup", r"benchmark", r"cpu\b", r"gpu\b", r"memory", r"scheduler", r"diskspd", r"presentmon", r"profil"],
    "debugging":   [r"debug", r"fix.*bug", r"repro", r"stack trace", r"crash", r"panic", r"error.*log"],
    "testing":     [r"\btest\b", r"vitest", r"jest", r"cargo test", r"spec\.", r"qa:vm", r"e2e"],
    "refactoring": [r"refactor", r"rename", r"cleanup", r"debt", r"extract", r"simplify"],
    "architecture":[r"architecture", r"design", r"migration", r"bounded context", r"service boundary", r"queue", r"cache"],
    "documentation":[r"docs?", r"readme", r"changelog", r"comment", r"wording", r"\.md\b"],
    "deployment":  [r"deploy", r"release", r"build", r"nsis", r"installer", r"updater", r"bundle", r"ci\b", r"workflow"],
    "research":    [r"research", r"investigate", r"whether.*changed", r"current.*behavior", r"docs.*lookup", r"api.*changed"],
}

FILE_MAP = {
    "rust": [r"src-tauri/", r"\.rs$"],
    "tauri": [r"src-tauri/", r"tauri\.conf", r"capabilities/", r"permissions/"],
    "frontend": [r"^src/", r"\.tsx?$", r"\.css$"],
    "windows": [r"registry", r"system/", r"firmware/", r"tweaks/"],
    "security": [r"security/", r"auth", r"license"],
    "performance": [r"benchmark", r"gaming/", r"probe"],
    "testing": [r"\.test\.", r"__tests__", r"qa/"],
}

COMPLEXITY_HINTS = {
    "simple": [r"wording", r"typo", r"button text", r"copy change", r"isolated style", r"comment"],
    "complex": [r"migration", r"architecture", r"refactor.*module", r"state bug", r"race condition", r"rollback", r"auth flow"],
}

def classify(task: str, files: list[str]) -> dict:
    text = task.lower()
    files_text = " ".join(files).lower()
    combined = text + " " + files_text

    matched = []
    for cat, patterns in CATEGORIES.items():
        for pat in patterns:
            if re.search(pat, combined, re.I):
                matched.append(cat)
                break

    if not matched:
        matched = ["general"]

    # Complexity
    complexity = "medium"
    for pat in COMPLEXITY_HINTS["simple"]:
        if re.search(pat, combined, re.I):
            complexity = "simple"
            break
    for pat in COMPLEXITY_HINTS["complex"]:
        if re.search(pat, combined, re.I):
            complexity = "complex"
            break
    # Heuristics: many files or rust+windows combo => complex
    if len(files) > 5:
        complexity = "complex"
    if "rust" in matched and "windows" in matched:
        complexity = "complex" if complexity != "simple" else "medium"
    if any("src-tauri/src/tweaks" in f for f in files) and "registry" in matched:
        complexity = "complex"

    # Affected components
    components = []
    for comp, pats in FILE_MAP.items():
        for pat in pats:
            if any(re.search(pat, f, re.I) for f in files) or re.search(pat, combined, re.I):
                if comp not in components:
                    components.append(comp)
    if not components:
        components = matched[:3]

    # Verification requirements
    verif = []
    if any(c in matched for c in ["frontend", "backend"]):
        verif.extend(["typecheck", "lint", "relevant tests"])
    if "rust" in matched or "tauri" in matched:
        verif.extend(["cargo check", "cargo test", "wiring:check"])
    if "windows" in matched or "registry" in matched or "services" in matched:
        verif.append("windows validation + rollback check")
    if "security" in matched or "authentication" in matched:
        verif.extend(["security:policy check", "input validation review"])
    if "performance" in matched:
        verif.append("benchmark baseline→compare")
    if "testing" in matched:
        verif.append("test suite")
    if "documentation" in matched and len(matched)==1:
        verif = ["no verification (docs only)"]
    if not verif:
        verif = ["typecheck/lint if applicable", "relevant tests"]

    needs_research = bool(re.search(r"whether.*changed|current.*api|windows.*behavior|tauri.*current|docs.*check", combined, re.I) or "research" in matched)
    needs_specialist = complexity == "complex" or any(c in matched for c in ["security","windows","rust","performance"]) and len(matched) > 2

    # Risk hint (coarse)
    high_risk_keywords = ["registry","service","elevation","privilege","destructive","migration","networking","auth","security","process"]
    risk_hint = "low"
    if any(k in combined for k in high_risk_keywords):
        risk_hint = "high"
    elif complexity == "complex":
        risk_hint = "medium"

    return {
        "categories": matched,
        "primary_category": matched[0],
        "complexity": complexity,
        "risk_hint": risk_hint,
        "affected_components": components,
        "affected_files_hint": files[:10],
        "verification": verif,
        "needs_research": needs_research,
        "needs_specialist": needs_specialist,
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("task", nargs="?", help="task description")
    p.add_argument("--files", default="", help="comma-separated file list")
    p.add_argument("--json", action="store_true", help="pretty json")
    args = p.parse_args()

    task = args.task
    if not task:
        # read stdin
        task = sys.stdin.read().strip()
    if not task:
        print(json.dumps({"error": "no task provided"}))
        sys.exit(1)

    files = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []
    result = classify(task, files)
    result["task_preview"] = task[:200]
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))

if __name__ == "__main__":
    main()
