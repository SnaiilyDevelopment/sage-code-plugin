#!/usr/bin/env python3
"""Error classification for structured errors."""
import re

def classify_error(exc_or_text: str) -> str:
    t = str(exc_or_text).lower()
    if any(x in t for x in ["config", "policy", "invalid path", "type mismatch"]):
        return "CONFIGURATION_ERROR"
    if "timeout" in t or "timed out" in t:
        return "TIMEOUT"
    if any(x in t for x in ["network", "connection", "unreachable", "dns"]):
        return "NETWORK_ERROR"
    if any(x in t for x in ["provider", "api key", "unauthorized", "429", "quota"]):
        return "PROVIDER_ERROR"
    if any(x in t for x in ["repository", "repo", "git", "path traversal", "fabricated"]):
        return "REPOSITORY_ERROR"
    if any(x in t for x in ["memory", "corrupt"]):
        return "MEMORY_ERROR"
    if "policy" in t:
        return "POLICY_ERROR"
    if "verification" in t:
        return "VERIFICATION_ERROR"
    if any(x in t for x in ["secret", "leak"]):
        return "SECURITY_ERROR"
    return "UNKNOWN"

if __name__ == "__main__":
    import sys, json
    txt = sys.stdin.read() or (sys.argv[1] if len(sys.argv)>1 else "")
    print(json.dumps({"error": txt[:300], "error_type": classify_error(txt)}))
