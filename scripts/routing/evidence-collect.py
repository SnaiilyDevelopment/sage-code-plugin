#!/usr/bin/env python3
"""Two-stage deterministic evidence collection: locate symbols/files then collect snippets. Bounded."""
import json, re, subprocess, hashlib
from pathlib import Path

# Patterns for symbol discovery
SYMBOL_PATTERNS = [
    r"\b(fn|function|def|class|struct|impl|pub\s+fn|export\s+(function|class|const))\b",
    r"\b(Invoke|Command|State|invoke|register|Tauri)\b",
]
INJECTION_RE = re.compile(r"^\s*(ignore\s+previous|system\s*:|assistant\s*:|jailbreak|disable\s+security|run\s+this\s+command|upload\s+secrets|change\s+the\s+policy)", re.I)

def _safe_read(fp: Path, max_chars=800) -> str:
    try:
        txt = fp.read_text(encoding="utf-8", errors="ignore")[:max_chars]
        # sanitize prompt injection: prefix untrusted lines
        lines = []
        for line in txt.splitlines()[:60]:
            if INJECTION_RE.match(line):
                lines.append("> [UNTRUSTED filtered] " + line[:120])
            else:
                lines.append(line)
        return "\n".join(lines)
    except (OSError, UnicodeError) as e:
        return f"[read error: {type(e).__name__}]"

def _rg_search(pattern: str, repo: Path, glob="") -> list:
    """Run ripgrep if available, else fallback to python grep. Returns [{file, line, text}]"""
    try:
        cmd = ["rg", "-n", "--no-heading", "--max-count", "8", pattern]
        if glob:
            cmd += ["-g", glob]
        # use cwd to get relative paths, avoid Windows drive colon split
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=2, cwd=str(repo))
        hits = []
        for line in r.stdout.splitlines()[:12]:
            parts = line.split(":", 2)
            if len(parts) >= 3:
                # handle possible drive colon already stripped via cwd relative, so parts[0] is file
                f = parts[0].replace("\\","/")
                hits.append({"file": f, "line": parts[1], "text": parts[2][:180]})
        return hits
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # fallback: python walk
        hits = []
        try:
            for p in repo.rglob("*"):
                if len(hits) >= 8: break
                if p.is_file() and p.suffix in (".ts",".tsx",".js",".rs",".py",".json",".md"):
                    try:
                        txt = p.read_text(encoding="utf-8", errors="ignore")
                        for i, l in enumerate(txt.splitlines(), 1):
                            if re.search(pattern, l):
                                hits.append({"file": str(p.relative_to(repo)), "line": str(i), "text": l.strip()[:180]})
                                if len(hits) >= 8: break
                    except (OSError, UnicodeError): continue
        except (OSError, RecursionError): pass
        return hits

def _validate_path(repo: Path, fp: str) -> bool:
    try:
        p = (repo / fp).resolve()
        r = repo.resolve()
        return p.is_relative_to(r)  # py3.9+
    except (OSError, ValueError, RuntimeError):
        return False

def collect(task: str, categories: list, files: list, repo: Path, max_chars: int = 4000) -> str:
    # Enforce max_chars includes system overhead later, cap hard
    repo = Path(repo)
    parts = []
    seen = set()

    # Stage 1: locate relevant symbols/files
    located = []  # list of {file, line, symbol}

    # 1) directly referenced files (validate path)
    for fp in list(dict.fromkeys(files or []))[:6]:
        if not _validate_path(repo, fp):
            parts.append(f"[BLOCKED path traversal: {fp[:80]}]")
            continue
        p = repo / fp
        if p.exists() and p.is_file():
            snippet = _safe_read(p, 900)
            parts.append(f"<untrusted_evidence source=\"{fp}\">\n{snippet}\n</untrusted_evidence>")
            seen.add(fp)
            # also locate symbols in that file
            hits = _rg_search(re.escape(task.split()[0]) if task else r"fn |class ", repo, f"*{Path(fp).name}")
            for h in hits[:2]:
                located.append(h)

    # 2) symbol discovery based on task keywords
    task_kw = re.findall(r"[A-Za-z]{4,}", task)[:6]
    for kw in task_kw:
        hits = _rg_search(re.escape(kw), repo)
        for h in hits[:3]:
            key = f"{h['file']}:{h['line']}"
            if key not in seen:
                seen.add(key)
                located.append(h)
                # fetch snippet around hit
                try:
                    fp = repo / h["file"]
                    if _validate_path(repo, h["file"]) and fp.exists():
                        lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
                        ln = int(h["line"])
                        ctx = "\n".join(lines[max(0,ln-3):ln+3])
                        # sanitize
                        ctx = "\n".join([f"> {l[:140]}" if INJECTION_RE.match(l) else l[:140] for l in ctx.splitlines()])
                        parts.append(f"<untrusted_evidence source=\"{h['file']}:{h['line']}\" symbol=\"{kw}\">\n{ctx[:500]}\n</untrusted_evidence>")
                except (OSError, ValueError, IndexError): pass
        if len(parts) >= 8: break

    # 3) related tests
    for test_pat in ["*test*.ts", "*test*.js", "*spec*.ts", "test_*.py", "*_test.rs"]:
        hits = _rg_search(task_kw[0] if task_kw else "test", repo, test_pat)
        for h in hits[:2]:
            if h["file"] not in seen:
                parts.append(f"<untrusted_evidence source=\"{h['file']}\" kind=\"related_test\">{h['text'][:300]}</untrusted_evidence>")
                seen.add(h["file"])
        if len(parts) >= 10: break

    # 4) relevant configuration (only if task mentions config-like)
    if any(x in task.lower() for x in ["tauri", "config", "cargo", "package", "capability"]):
        for cfg in ["tauri.conf.json", "Cargo.toml", "package.json", "src-tauri/capabilities/default.json"]:
            p = repo / cfg
            if _validate_path(repo, cfg) and p.exists():
                parts.append(f"<untrusted_evidence source=\"{cfg}\" kind=\"config\">\n{_safe_read(p, 500)}\n</untrusted_evidence>")

    # 5) repository architecture (bounded)
    arch = Path(__file__).resolve().parents[2] / "references" / "sage-architecture.md"
    map_json = repo / ".wolf" / "sage-map.json"
    if map_json.exists():
        try:
            data = json.loads(map_json.read_text(encoding="utf-8", errors="ignore"))
            parts.append(f"<untrusted_evidence kind=\"repo_map\">product {data.get('product','')} hash {data.get('hash','')[:12]}</untrusted_evidence>")
        except (OSError, json.JSONDecodeError, UnicodeError): pass
    elif arch.exists():
        try:
            txt = arch.read_text(encoding="utf-8", errors="ignore")[:900]
            txt = "\n".join([f"> {l}" if INJECTION_RE.match(l) else l for l in txt.splitlines()[:40]])
            parts.append(f"<untrusted_evidence kind=\"architecture\">\n{txt[:700]}\n</untrusted_evidence>")
        except (OSError, UnicodeError): pass

    # 6) recent git changes when relevant
    if any(x in task.lower() for x in ["change", "recent", "regress", "fix"]):
        try:
            r = subprocess.run(["git", "-C", str(repo), "log", "--oneline", "-5"], capture_output=True, text=True, timeout=2)
            if r.stdout.strip():
                parts.append(f"<untrusted_evidence kind=\"git_recent\">\n{r.stdout[:500]}\n</untrusted_evidence>")
            r2 = subprocess.run(["git", "-C", str(repo), "diff", "--stat"], capture_output=True, text=True, timeout=2)
            if r2.stdout.strip():
                parts.append(f"<untrusted_evidence kind=\"git_diff\">\n{r2.stdout[:500]}\n</untrusted_evidence>")
        except (OSError, subprocess.TimeoutExpired): pass

    # 7) categories hint
    if categories:
        parts.append(f"<untrusted_evidence kind=\"categories\">{', '.join(categories[:6])}</untrusted_evidence>")

    out = "\n---\n".join(parts)
    # Bounded: truncate to max_chars but keep tag integrity (cut at boundary)
    if len(out) > max_chars:
        out = out[:max_chars].rsplit("\n", 1)[0] + "\n[truncated evidence]"
    return out
