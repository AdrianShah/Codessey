"""Input sanitization — size/type checks, encoding handling."""

import mimetypes
from pathlib import Path

MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_LINE_COUNT = 5000
ALLOWED_EXTENSIONS = {".py", ".js", ".ts", ".java", ".go", ".cpp"}


class InputValidationError(Exception):
    """Raised when input fails validation — always a user-facing message, never a crash."""
    pass


def validate_file_upload(filename: str, content: bytes) -> str:
    """Validate uploaded file content. Returns decoded text or raises InputValidationError."""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise InputValidationError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise InputValidationError(
            f"File exceeds size limit ({MAX_FILE_SIZE_BYTES // (1024*1024)} MB)."
        )

    if _is_binary(content):
        raise InputValidationError(
            "File appears to be binary content, not source code."
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception:
            raise InputValidationError("File contains non-decodable content.")

    return _validate_text(text)


def validate_paste(text: str) -> str:
    """Validate pasted code text."""
    if not text or not text.strip():
        raise InputValidationError("No code detected to review.")

    if len(text.encode("utf-8")) > MAX_FILE_SIZE_BYTES:
        raise InputValidationError(
            f"Input exceeds size limit ({MAX_FILE_SIZE_BYTES // (1024*1024)} MB)."
        )

    return _validate_text(text)


def _validate_text(text: str) -> str:
    lines = text.splitlines()
    if len(lines) > MAX_LINE_COUNT:
        raise InputValidationError(
            f"Input exceeds {MAX_LINE_COUNT} lines. Please submit a smaller file."
        )
    if not text.strip():
        raise InputValidationError("No code detected to review.")
    return text


def _is_binary(content: bytes) -> bool:
    """Heuristic: if the first 8KB contain null bytes, treat as binary."""
    chunk = content[:8192]
    return b"\x00" in chunk
