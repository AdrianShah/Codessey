"""LLM client — Gemini API."""

import json
import logging
import os
import random
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from functools import lru_cache
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_SPECIALIST_MODEL = "gemini-2.5-flash"
GEMINI_CONDUCTOR_MODEL = "gemini-2.5-pro"
GEMINI_ATTEMPT_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_TIMEOUT", "15"))
MAX_RETRY_ATTEMPTS = 3
DEFAULT_BACKOFF_SECONDS = (2.0, 5.0, 10.0)

T = TypeVar("T")

# Gemini requires full `items` schema for array fields.
ANALYSIS_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "warning", "info"],
                    },
                    "line_ref": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": [
                    "severity",
                    "line_ref",
                    "title",
                    "description",
                    "suggestion",
                ],
            },
        },
        "overall_score": {"type": "number"},
    },
    "required": ["findings", "overall_score"],
}


def parse_retry_delay(exc: Exception) -> float | None:
    """Parse provider retry hints from error text."""
    msg = str(exc)
    match = re.search(r"try again in ([\d.]+)s", msg, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r"retryDelay['\"]:\s*['\"]?(\d+)s?", msg, re.IGNORECASE)
    if match:
        return float(match.group(1))
    return None


def is_retryable_error(exc: Exception) -> bool:
    """True for transient rate limits, overload, and timeouts."""
    if isinstance(exc, (FuturesTimeout, TimeoutError)):
        return True
    msg = str(exc)
    if re.search(r"\b(401|400)\b", msg) and re.search(
        r"api key|unauthorized|invalid", msg, re.IGNORECASE
    ):
        return False
    if "RESOURCE_EXHAUSTED" in msg or "UNAVAILABLE" in msg:
        return True
    if "429" in msg and ("quota" in msg.lower() or "rate limit" in msg.lower()):
        return True
    if re.search(r"\b503\b", msg):
        return True
    return False


def retry_call(fn: Callable[[], T], max_attempts: int = MAX_RETRY_ATTEMPTS) -> T:
    """Run fn with retries on transient LLM failures."""
    last_exc: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts - 1 or not is_retryable_error(exc):
                raise
            delay = parse_retry_delay(exc)
            if delay is None:
                delay = DEFAULT_BACKOFF_SECONDS[min(attempt, len(DEFAULT_BACKOFF_SECONDS) - 1)]
            delay += random.uniform(0, 0.5)
            logger.warning(
                "LLM call failed (attempt %d/%d), retry in %.1fs: %s",
                attempt + 1,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
    assert last_exc is not None
    raise last_exc


def get_gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return key.strip() if key and key.strip() else None


def require_llm_key() -> None:
    if not get_gemini_key():
        raise RuntimeError(
            "No LLM API key configured. Add to .env in the project root:\n"
            "  GEMINI_API_KEY=your_gemini_key"
        )


@lru_cache(maxsize=1)
def _gemini_client() -> genai.Client:
    key = get_gemini_key()
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=key)


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence:
        text = fence.group(1).strip()
    return json.loads(text)


def _gemini_generate_structured(
    system_prompt: str,
    user_message: str,
    temperature: float,
    model: str,
) -> tuple[dict, int]:
    client = _gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=ANALYSIS_RESPONSE_SCHEMA,
        ),
    )
    if not response.text:
        raise ValueError("Empty Gemini response")
    tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
    return _extract_json(response.text), tokens


def _gemini_structured_json(
    system_prompt: str,
    user_message: str,
    temperature: float,
) -> tuple[dict, int]:
    return retry_call(
        lambda: _gemini_generate_structured(
            system_prompt, user_message, temperature, GEMINI_SPECIALIST_MODEL
        )
    )


def generate_structured_analysis(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
) -> tuple[dict, int, str]:
    """Call Gemini for structured JSON. Returns (json_dict, token_usage, provider)."""
    require_llm_key()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            _gemini_structured_json, system_prompt, user_message, temperature
        )
        data, tokens = future.result(timeout=GEMINI_ATTEMPT_TIMEOUT_SECONDS)
    return data, tokens, "gemini"


def _gemini_text_once(prompt: str, temperature: float, model: str) -> str:
    client = _gemini_client()
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    if not response.text:
        raise ValueError("Empty Gemini response")
    return response.text


def _gemini_text(prompt: str, temperature: float, model: str) -> str:
    return retry_call(lambda: _gemini_text_once(prompt, temperature, model))


def generate_text(prompt: str, temperature: float = 0.3) -> tuple[str, str]:
    """Try Gemini Pro, then Flash. Returns (text, provider)."""
    require_llm_key()
    gemini_error: Exception | None = None
    for model in (GEMINI_CONDUCTOR_MODEL, GEMINI_SPECIALIST_MODEL):
        try:
            text = _gemini_text(prompt, temperature, model)
            if model != GEMINI_CONDUCTOR_MODEL:
                logger.info("Conductor summary used %s after pro failure", model)
            return text, "gemini"
        except Exception as exc:
            gemini_error = exc
            logger.warning("Gemini text call failed (%s): %s", model, exc)

    assert gemini_error is not None
    raise gemini_error
