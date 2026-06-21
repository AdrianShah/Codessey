"""Secret redaction — mask detected secrets before display (PRD FR-17)."""

import re

# Common secret patterns
SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),                       # AWS access key
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),                 # Google API key
    re.compile(r"sk-[0-9a-zA-Z]{20,}"),                    # OpenAI / Stripe secret key
    re.compile(r"ghp_[0-9a-zA-Z]{36}"),                    # GitHub personal access token
    re.compile(r"glpat-[0-9a-zA-Z\-_]{20,}"),              # GitLab PAT
    re.compile(r"xox[baprs]-[0-9a-zA-Z\-]{10,}"),         # Slack token
    re.compile(r"-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----"),  # PEM key
    re.compile(r"[0-9a-f]{40}", re.IGNORECASE),            # generic 40-char hex (SHA-like tokens)
]

# More conservative: only redact things that look like actual keys (not git SHAs in line refs)
HIGH_CONFIDENCE_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{35}"),
    re.compile(r"sk-[0-9a-zA-Z]{20,}"),
    re.compile(r"ghp_[0-9a-zA-Z]{36}"),
    re.compile(r"glpat-[0-9a-zA-Z\-_]{20,}"),
    re.compile(r"xox[baprs]-[0-9a-zA-Z\-]{10,}"),
]


def redact_secrets(text: str) -> str:
    """Replace detected secrets with masked versions (first 4 + last 4 chars visible)."""
    for pattern in HIGH_CONFIDENCE_PATTERNS:
        text = pattern.sub(_mask_match, text)
    return text


def _mask_match(match: re.Match) -> str:
    secret = match.group(0)
    if len(secret) <= 8:
        return "*" * len(secret)
    return secret[:4] + "*" * (len(secret) - 8) + secret[-4:]


def contains_secret(text: str) -> bool:
    """Check if text likely contains a secret/API key."""
    return any(p.search(text) for p in HIGH_CONFIDENCE_PATTERNS)
