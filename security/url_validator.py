"""GitHub URL validation — SSRF prevention (PRD Section 6.2)."""

import re
from urllib.parse import urlparse

ALLOWED_HOSTS = {"github.com", "raw.githubusercontent.com"}
FETCH_TIMEOUT_SECONDS = 5
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


class URLValidationError(Exception):
    pass


def validate_github_url(url: str) -> str:
    """Validate and normalize a GitHub URL. Returns the validated URL."""
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise URLValidationError("Only HTTPS URLs are accepted.")

    host = parsed.hostname
    if host is None or host not in ALLOWED_HOSTS:
        raise URLValidationError(
            f"URL must point to github.com or raw.githubusercontent.com, got: {host}"
        )

    # Reject IP-literal hosts
    if host and re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", host):
        raise URLValidationError("IP addresses are not allowed.")

    # Reject directory URLs (must point to a file)
    path = parsed.path.rstrip("/")
    if not path or path.count("/") < 4:
        raise URLValidationError(
            "URL must point to a specific file, not a repository root or directory."
        )

    # For github.com blob URLs, validate structure
    if host == "github.com" and "/blob/" not in path and "/raw/" not in path:
        raise URLValidationError(
            "GitHub URL must point to a file (use a /blob/ or /raw/ URL)."
        )

    return url


def github_url_to_raw(url: str) -> str:
    """Convert a github.com blob URL to a raw.githubusercontent.com URL."""
    parsed = urlparse(url)
    if parsed.hostname == "raw.githubusercontent.com":
        return url
    # github.com/user/repo/blob/branch/path → raw.githubusercontent.com/user/repo/branch/path
    path = parsed.path.replace("/blob/", "/", 1).replace("/raw/", "/", 1)
    return f"https://raw.githubusercontent.com{path}"
