#!/usr/bin/env python3
"""Strip secrets from text before logging/telemetry."""
import re, sys

PATTERNS = [
    (re.compile(r"supabase.*service_role.*['\"][^'\"]+['\"]", re.I), "[REDACTED supabase service_role]"),
    (re.compile(r"stripe_secret[^\\n]*", re.I), "[REDACTED stripe_secret]"),
    (re.compile(r"api[_-]?key\s*[:=]\s*['\"][^'\"]+['\"]", re.I), "api_key=[REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+", re.I), "Bearer [REDACTED]"),
    (re.compile(r"license\.dat[^\\n]*", re.I), "license.dat [REDACTED]"),
    (re.compile(r"hwid\.dat[^\\n]*", re.I), "hwid.dat [REDACTED]"),
    (re.compile(r"audit_signing\.key[^\\n]*", re.I), "audit_signing.key [REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED sk-...]"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}", re.I), "[REDACTED ghp_]"),
    (re.compile(r"-----BEGIN (PRIVATE|RSA) KEY-----", re.I), "[REDACTED PRIVATE KEY]"),
]

def strip(text: str) -> str:
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    return text

if __name__ == "__main__":
    data = sys.stdin.read()
    sys.stdout.write(strip(data))
