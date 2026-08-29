#!/usr/bin/env python3
"""Controlled read-only evidence collection for scout — bounded, no huge dumps."""
import json, re, subprocess
from pathlib import Path

def collect(task: str, categories: list, files: list, repo: Path, max_chars: int = 4000) -> str:
    parts = []
    # repo map snippet
    arch = Path(__file__).resolve().parents[2] / "references" / "sage-architecture.md"
    map_json = repo / ".wolf" / "sage-map.json"
    if map_json.exists():
        try:
            data = json.loads(map_json.read_text(encoding="utf-8", errors="ignore"))
            parts.append(f"Repo map: product {data.get('product','')} entry_points {str(data.get('entry_points',{}))[:300]}")
        except: pass
    elif arch.exists():
        try:
            txt = arch.read_text(encoding="utf-8", errors="ignore")[:1500]
            parts.append(f"Architecture:\n{txt[:1000]}")
        except: pass
    # relevant file snippets (read-only, capped)
    uniq = list(dict.fromkeys(files or []))[:5]
    for fp in uniq:
        p = repo / fp
        if p.exists() and p.is_file():
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")[:800]
                parts.append(f"File {fp}:\n{txt[:600]}")
            except: pass
        # also search for symbols if file is dir-like
    # git summary
    try:
        r = subprocess.run(["git","-C",str(repo),"diff","--stat"], capture_output=True, text=True, timeout=3)
        if r.stdout.strip():
            parts.append(f"Git diff stat:\n{r.stdout[:600]}")
    except: pass
    # category hints
    if categories:
        parts.append(f"Categories: {', '.join(categories)}")
    out = "\n---\n".join(parts)
    # truncate to max_chars conservatively
    if len(out) > max_chars:
        out = out[:max_chars] + "\n[truncated]"
    return out
