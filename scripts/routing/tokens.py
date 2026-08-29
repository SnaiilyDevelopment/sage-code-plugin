#!/usr/bin/env python3
"""Token estimation and cost accounting — conservative, no silent fake pricing."""
import json

# Cache tiktoken encoding (cold start ~50ms)
_ENC = None
def _get_enc():
    global _ENC
    if _ENC is not None:
        return _ENC
    try:
        import tiktoken
        _ENC = tiktoken.get_encoding("cl100k_base")
        return _ENC
    except (ImportError, OSError, ValueError):
        return None

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    enc = _get_enc()
    if enc is not None:
        try:
            c = len(enc.encode(text))
            return max(1, int(c * 1.1))
        except (ValueError, TypeError, OSError):
            pass
    return max(1, int(len(text) / 4 * 1.25))

def estimate_tokens_obj(obj) -> int:
    return estimate_tokens(json.dumps(obj, ensure_ascii=False))

def calc_cost(tokens_in: int, tokens_out: int, provider: dict) -> dict:
    """Returns {cost_usd, cost_status, source} - UNKNOWN/PRICING_STALE if pricing missing/stale."""
    try:
        pin = provider.get("cost_per_1k_in")
        pout = provider.get("cost_per_1k_out")
        if pin is None or pout is None:
            return {"cost_usd": None, "cost_status": "UNKNOWN", "reason": "pricing unknown for provider/model"}
        cost = round(tokens_in/1000*float(pin) + tokens_out/1000*float(pout), 6)
        # provenance + staleness (90 days)
        from datetime import datetime, timezone
        verified_at = provider.get("verified_at") or provider.get("effective_date") or ""
        has_provenance = bool(provider.get("source") and provider.get("effective_date"))
        stale = False
        if verified_at:
            try:
                dt = datetime.fromisoformat(str(verified_at).replace("Z","+00:00"))
                # ensure tz aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age_days = (datetime.now(timezone.utc) - dt).total_seconds()/86400
                if age_days > 90:
                    stale = True
            except (ValueError, TypeError, OSError):
                stale = False
        if stale:
            return {"cost_usd": cost, "cost_status": "PRICING_STALE", "source": provider.get("source",""), "currency": provider.get("currency","USD"), "verified_at": verified_at, "reason": "pricing >90 days old"}
        status = "OK" if has_provenance else "OK_NO_PROVENANCE"
        # PRICING_STALE without provenance also not authoritative
        if not has_provenance:
            status = "PRICING_STALE"
        return {"cost_usd": cost, "cost_status": status, "source": provider.get("source",""), "currency": provider.get("currency","USD"), "verified_at": verified_at}
    except (ValueError, TypeError, KeyError) as e:
        return {"cost_usd": None, "cost_status": "UNKNOWN", "reason": str(e)[:200]}

def pricing_valid(provider: dict) -> bool:
    return provider.get("cost_per_1k_in") is not None and provider.get("cost_per_1k_out") is not None

def is_pricing_stale(provider: dict, max_age_days: int = 90) -> bool:
    from datetime import datetime, timezone
    v = provider.get("verified_at") or provider.get("effective_date")
    if not v: return True
    try:
        dt = datetime.fromisoformat(str(v).replace("Z","+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc)-dt).total_seconds()/86400 > max_age_days
    except (ValueError, TypeError, OSError):
        return True
