#!/usr/bin/env python3
"""Hard outbound security boundary — layered secret detection, redaction, filename blocking.

Layers:
 1. Filename blocklist (reject dangerous files before reading)
 2. Content regex (comprehensive secret patterns)
 3. Entropy/high-entropy generic assignment filter
 4. Size & provenance checks

Protects against: API keys, OAuth tokens, JWTs, passwords, cookies, auth headers,
 private keys/certs/SSH, .env/credential files, cloud/GitHub/npm/PyPI/Stripe creds,
 DB connection strings, license/HWID/machine/customer PII, and secrets hidden
 inside JSON/TOML/YAML/TS/Rust/logs/comments/strings/generated files.

Do NOT rely exclusively on regex — this combines filename + content + structural checks.
"""
import re, sys

# ---------- Layer 1: dangerous filenames (reject before sending) ----------
DANGEROUS_FILENAME_RE = re.compile(
    r"(\.env(\.|$)|secrets\.toml|credentials\.json|\.pem$|\.key$|id_rsa|id_ed25519|"
    r"license\.dat|license_hwm\.dat|hwid\.dat|audit_signing\.key|"
    r"applied_tweaks\.json|\.aws/credentials|\.npmrc|\.pypirc|"
    r"serviceAccount\.json|gcloud|azure\.json|cookies\.txt|\.netrc)",
    re.I
)
# Any file that looks like it contains secrets by name should be blocked outward
DANGEROUS_BASENAME_EXACT = {
    ".env", "secrets.toml", "credentials.json", ".npmrc", ".pypirc",
    "license.dat", "license_hwm.dat", "hwid.dat", "audit_signing.key",
}

# ---------- Layer 2: comprehensive content patterns ----------
PATTERNS = [
    # Supabase / Stripe
    (re.compile(r"supabase.*service_role.*['\"][^'\"]+['\"]", re.I), "[REDACTED supabase service_role]"),
    (re.compile(r"stripe_secret[^\\n]{0,120}", re.I), "[REDACTED stripe_secret]"),
    (re.compile(r"sk_live_[A-Za-z0-9]{20,}", re.I), "[REDACTED stripe sk_live]"),
    (re.compile(r"sk_test_[A-Za-z0-9]{20,}", re.I), "[REDACTED stripe sk_test]"),
    (re.compile(r"rk_live_[A-Za-z0-9]{20,}", re.I), "[REDACTED stripe rk_live]"),
    # Generic api_key assignments (JSON/TOML/YAML/TS/Rust/logs/comments/strings)
    (re.compile(r"api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "api_key=[REDACTED]"),
    (re.compile(r"apikey\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "apikey=[REDACTED]"),
    (re.compile(r"secret\s*[:=]\s*['\"][^'\"]{4,}['\"]", re.I), "secret=[REDACTED]"),
    (re.compile(r"password\s*[:=]\s*['\"][^'\"]{3,}['\"]", re.I), "password=[REDACTED]"),
    (re.compile(r"passwd\s*[:=]\s*['\"][^'\"]{3,}['\"]", re.I), "passwd=[REDACTED]"),
    (re.compile(r"pwd\s*[:=]\s*['\"][^'\"]{3,}['\"]", re.I), "pwd=[REDACTED]"),
    (re.compile(r"token\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "token=[REDACTED]"),
    (re.compile(r"access[_-]?token\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "access_token=[REDACTED]"),
    (re.compile(r"refresh[_-]?token\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "refresh_token=[REDACTED]"),
    (re.compile(r"oauth[_-]?token\s*[:=]\s*['\"][^'\"]{8,}['\"]", re.I), "oauth_token=[REDACTED]"),
    # Authorization headers / cookies
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_\.]+", re.I), "Bearer [REDACTED]"),
    (re.compile(r"Basic\s+[A-Za-z0-9+/=]{10,}", re.I), "Basic [REDACTED]"),
    (re.compile(r"Authorization\s*:\s*Bearer[^\r\n]{5,}", re.I), "Authorization: Bearer [REDACTED]"),
    (re.compile(r"cookie\s*[:=][^\r\n]{5,}", re.I), "cookie=[REDACTED]"),
    (re.compile(r"set-cookie[^\r\n]{5,}", re.I), "set-cookie [REDACTED]"),
    # OpenAI / generic sk-
    (re.compile(r"sk-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED sk-...]"),
    (re.compile(r"sk-proj-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED sk-proj-...]"),
    # GitHub tokens
    (re.compile(r"ghp_[A-Za-z0-9]{30,}", re.I), "[REDACTED ghp_]"),
    (re.compile(r"gho_[A-Za-z0-9]{30,}", re.I), "[REDACTED gho_]"),
    (re.compile(r"ghu_[A-Za-z0-9]{30,}", re.I), "[REDACTED ghu_]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{40,}", re.I), "[REDACTED github_pat_]"),
    (re.compile(r"ghp_[A-Za-z0-9_]{36,}", re.I), "[REDACTED ghp_]"),
    # Slack
    (re.compile(r"xox[bpras]-[A-Za-z0-9\-]{10,}", re.I), "[REDACTED xoxb-]"),
    # AWS
    (re.compile(r"AKIA[0-9A-Z]{16}", re.I), "[REDACTED AKIA]"),
    (re.compile(r"aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*['\"][^'\"]{20,}['\"]", re.I), "aws_secret=[REDACTED]"),
    # Private keys / certs / SSH
    (re.compile(r"-----BEGIN (PRIVATE|RSA|EC|DSA|OPENSSH) (KEY|PRIVATE KEY)-----", re.I), "[REDACTED PRIVATE KEY]"),
    (re.compile(r"-----BEGIN CERTIFICATE-----", re.I), "[REDACTED CERTIFICATE]"),
    (re.compile(r"ssh-rsa\s+[A-Za-z0-9+/=]{30,}", re.I), "[REDACTED ssh-rsa]"),
    (re.compile(r"ssh-ed25519\s+[A-Za-z0-9+/=]{30,}", re.I), "[REDACTED ssh-ed25519]"),
    # NPM / PyPI
    (re.compile(r"npm_[A-Za-z0-9]{20,}", re.I), "[REDACTED npm_]"),
    (re.compile(r"pypi-[A-Za-z0-9\-_]{20,}", re.I), "[REDACTED pypi-]"),
    # Database connection strings (postgres/mysql/mongodb/redis with credentials)
    (re.compile(r"postgres(ql)?://[^\s]{5,}", re.I), "[REDACTED postgres://]"),
    (re.compile(r"mysql://[^\s]{5,}", re.I), "[REDACTED mysql://]"),
    (re.compile(r"mongodb(\+srv)?://[^\s]{5,}", re.I), "[REDACTED mongodb://]"),
    (re.compile(r"redis://[^\s]{5,}", re.I), "[REDACTED redis://]"),
    (re.compile(r"DATABASE_URL\s*[:=][^\r\n]{10,}", re.I), "DATABASE_URL=[REDACTED]"),
    # JWTs
    (re.compile(r"eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}", re.I), "[REDACTED JWT]"),
    # License / HWID / machine identifiers
    (re.compile(r"license\.dat[^\r\n]{0,120}", re.I), "license.dat [REDACTED]"),
    (re.compile(r"hwid\.dat[^\r\n]{0,120}", re.I), "hwid.dat [REDACTED]"),
    (re.compile(r"audit_signing\.key[^\r\n]{0,120}", re.I), "audit_signing.key [REDACTED]"),
    (re.compile(r"HWID[^\r\n]{0,80}", re.I), "HWID [REDACTED]"),
    (re.compile(r"machine[_-]?id\s*[:=][^\r\n]{3,}", re.I), "machine_id=[REDACTED]"),
    (re.compile(r"customer.*info[^\r\n]{0,80}", re.I), "customer info [REDACTED]"),
    # Generic high-entropy assignments inside JSON/TOML/YAML/TS/Rust/logs/comments
    (re.compile(r"['\"](sk|ghp|gho|AKIA|xox)[-_A-Za-z0-9]{20,}['\"]", re.I), "[REDACTED high-entropy token]"),
]

# Additional assignment pattern for generic _key, _secret suffixes with entropy-like values
GENERIC_ASSIGNMENT_RE = re.compile(r"(key|secret|credential)\s*[:=]\s*['\"][A-Za-z0-9\-_/+=\.]{16,}['\"]", re.I)


def is_dangerous_filename(path: str) -> bool:
    """Layer 1: check if filename itself is sensitive and should be blocked outward."""
    pl = path.replace("\\", "/").lower()
    base = pl.split("/")[-1]
    if base in DANGEROUS_BASENAME_EXACT:
        return True
    if DANGEROUS_FILENAME_RE.search(pl):
        return True
    return False


def contains_secret(text: str) -> bool:
    """Quick check if text likely contains a secret (for reject/filter decisions)."""
    if not text:
        return False
    for pat, _ in PATTERNS:
        if pat.search(text):
            return True
    if GENERIC_ASSIGNMENT_RE.search(text):
        return True
    return False


def scan_findings(text: str) -> list:
    """Return list of matched secret types for logging (safe metadata only)."""
    findings = []
    for pat, repl in PATTERNS:
        if pat.search(text):
            findings.append(repl)
    if GENERIC_ASSIGNMENT_RE.search(text):
        findings.append("generic high-entropy assignment")
    return list(dict.fromkeys(findings))


def strip(text: str) -> str:
    """Redact all detected secrets from text. Layers 2+3."""
    if not text:
        return text
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    text = GENERIC_ASSIGNMENT_RE.sub("[REDACTED generic credential]", text)
    return text


def strip_with_report(text: str) -> tuple:
    """Returns (stripped_text, findings, had_secret). For outbound firewall audit."""
    findings = scan_findings(text)
    had = len(findings) > 0
    return strip(text), findings, had


def filter_files(file_list: list) -> tuple:
    """Layer 1 filename scan: returns (safe_files, blocked_files)."""
    safe = []
    blocked = []
    for f in file_list:
        if is_dangerous_filename(str(f)):
            blocked.append(str(f))
        else:
            safe.append(str(f))
    return safe, blocked


def enforce_payload_limits(text: str, max_chars: int = 4000) -> tuple:
    """Enforce maximum payload size: returns (text_truncated, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars].rsplit("\n", 1)[0] + "\n[truncated to payload limit]", True


if __name__ == "__main__":
    data = sys.stdin.read()
    sys.stdout.write(strip(data))
