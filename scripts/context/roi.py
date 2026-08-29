#!/usr/bin/env python3
"""Context ROI mechanism: ROI = relevance * confidence * freshness / token_cost. Prefer high-ROI, discard low-ROI."""
import math, re
from datetime import datetime, timezone

def freshness_score(iso_date: str, half_life_days: int = 30) -> float:
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z","+00:00"))
        age_days = (datetime.now(timezone.utc) - dt).total_seconds()/86400
        return 0.5 ** (max(0, age_days) / half_life_days)
    except:
        return 0.5

def relevance_score(text: str, task_keywords: list) -> float:
    if not task_keywords:
        return 0.5
    text_l = text.lower()
    hits = sum(1 for kw in task_keywords if kw.lower() in text_l)
    return min(1.0, hits / max(1, len(task_keywords)) * 1.5 + 0.2)

def token_cost(text: str) -> int:
    try:
        from scripts.routing.tokens import estimate_tokens
        return max(1, estimate_tokens(text))
    except:
        return max(1, int(len(text)/4 * 1.25))

def roi(relevance: float, confidence: float, freshness: float, cost: int) -> float:
    return (relevance * confidence * freshness) / max(1, cost)

def score_item(item_text: str, task: str, confidence: float = 0.7, iso_date: str = None, half_life: int = 30) -> dict:
    kws = list(dict.fromkeys(re.findall(r"[A-Za-z]{4,}", task.lower())))[:6]
    rel = relevance_score(item_text, kws)
    fresh = freshness_score(iso_date, half_life) if iso_date else 1.0
    cost = token_cost(item_text)
    val = roi(rel, confidence, fresh, cost)
    return {"relevance": round(rel,2), "confidence": round(confidence,2), "freshness": round(fresh,2), "token_cost": cost, "roi": round(val,4)}

def filter_by_roi(items: list, task: str, threshold: float = 0.001, top_n: int = None) -> list:
    """items: [{text, confidence, date}] -> sorted high ROI first, filtered"""
    scored = []
    for it in items:
        txt = it.get("text") or it.get("fact") or str(it)
        conf_map = {"hypothesis":0.3,"observed":0.6,"verified":0.8,"validated":0.95,"low":0.3,"medium":0.6,"high":0.8}
        conf = it.get("confidence", 0.6)
        if isinstance(conf, str):
            conf = conf_map.get(conf.lower(), 0.6)
        s = score_item(txt, task, float(conf), it.get("date") or it.get("last_validated"))
        s["item"] = it
        scored.append(s)
    scored.sort(key=lambda x: x["roi"], reverse=True)
    filtered = [s for s in scored if s["roi"] >= threshold]
    if top_n:
        filtered = filtered[:top_n]
    return filtered
