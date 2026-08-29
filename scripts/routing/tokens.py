#!/usr/bin/env python3
"""Token estimation and cost accounting — conservative, no silent fake pricing."""
import json

# Conservative estimator: len//4 * 1.25, floor 1, fallback to tiktoken if available
def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # try tiktoken if installed
    try:
        import tiktoken
        # use cl100k base as generic; provider models vary but conservative
        enc = tiktoken.get_encoding("cl100k_base")
        c = len(enc.encode(text))
        # stay conservative: add 10% headroom
        return max(1, int(c * 1.1))
    except:
        return max(1, int(len(text) / 4 * 1.25))

def estimate_tokens_obj(obj) -> int:
    return estimate_tokens(json.dumps(obj, ensure_ascii=False))

def calc_cost(tokens_in: int, tokens_out: int, provider: dict) -> dict:
    """Returns {cost_usd, cost_status, source} - UNKNOWN if pricing missing."""
    try:
        pin = provider.get("cost_per_1k_in")
        pout = provider.get("cost_per_1k_out")
        if pin is None or pout is None:
            return {"cost_usd": None, "cost_status": "UNKNOWN", "reason": "pricing unknown for provider/model"}
        # check for zero pricing meaning unknown vs free — treat 0 as valid if explicitly 0
        cost = round(tokens_in/1000*float(pin) + tokens_out/1000*float(pout), 6)
        # check required provenance fields
        has_provenance = provider.get("source") and provider.get("effective_date")
        status = "OK" if has_provenance else "OK_NO_PROVENANCE"
        return {"cost_usd": cost, "cost_status": status, "source": provider.get("source",""), "currency": provider.get("currency","USD")}
    except Exception as e:
        return {"cost_usd": None, "cost_status": "UNKNOWN", "reason": str(e)[:200]}

def pricing_valid(provider: dict) -> bool:
    return provider.get("cost_per_1k_in") is not None and provider.get("cost_per_1k_out") is not None
