"""Ingestion agent — deterministic, no LLM. Validates input and produces CodeChunks."""

import httpx

from schemas.code_chunk import CodeChunk
from security.input_sanitizer import (
    validate_file_upload,
    validate_paste,
    InputValidationError,
)
from security.url_validator import (
    validate_github_url,
    github_url_to_raw,
    URLValidationError,
    FETCH_TIMEOUT_SECONDS,
    MAX_RESPONSE_BYTES,
)
from utils.language_detector import detect_language
from utils.code_chunker import chunk_code


class IngestionError(Exception):
    """User-facing ingestion error — always a clear message."""
    pass


async def ingest_paste(text: str, filename: str | None = None) -> list[CodeChunk]:
    """Ingest pasted code text."""
    try:
        validated = validate_paste(text)
    except InputValidationError as e:
        raise IngestionError(str(e))

    language, confidence = detect_language(filename, validated)
    name = filename or "paste.txt"
    return chunk_code(validated, name, language)


async def ingest_file(filename: str, content: bytes) -> list[CodeChunk]:
    """Ingest uploaded file."""
    try:
        text = validate_file_upload(filename, content)
    except InputValidationError as e:
        raise IngestionError(str(e))

    language, confidence = detect_language(filename, text)
    return chunk_code(text, filename, language)


async def ingest_github_url(url: str) -> list[CodeChunk]:
    """Fetch code from a GitHub URL and ingest it."""
    try:
        validated_url = validate_github_url(url)
    except URLValidationError as e:
        raise IngestionError(str(e))

    raw_url = github_url_to_raw(validated_url)

    try:
        async with httpx.AsyncClient(follow_redirects=False) as client:
            response = await client.get(
                raw_url,
                timeout=FETCH_TIMEOUT_SECONDS,
                headers={"Accept": "text/plain"},
            )
    except httpx.TimeoutException:
        raise IngestionError("GitHub URL fetch timed out.")
    except httpx.RequestError as e:
        raise IngestionError(f"Failed to fetch URL: {e}")

    if response.status_code == 404:
        raise IngestionError("File not found at the given GitHub URL.")
    if response.status_code == 403:
        raise IngestionError("Repository is not accessible (private or rate-limited).")
    if response.status_code != 200:
        raise IngestionError(f"GitHub returned status {response.status_code}.")

    if len(response.content) > MAX_RESPONSE_BYTES:
        raise IngestionError("Fetched file exceeds size limit.")

    # Extract filename from URL path
    filename = validated_url.rstrip("/").split("/")[-1]
    text = response.text

    try:
        validated_text = validate_paste(text)
    except InputValidationError as e:
        raise IngestionError(str(e))

    language, _ = detect_language(filename, validated_text)
    return chunk_code(validated_text, filename, language)
