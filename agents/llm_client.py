"""LLM client — Gemini first, Groq fallback."""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from functools import lru_cache

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_SPECIALIST_MODEL = "gemini-2.5-flash"
GEMINI_CONDUCTOR_MODEL = "gemini-2.5-pro"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_SPECIALIST_MODEL = "llama-3.1-8b-instant"
GROQ_CONDUCTOR_MODEL = "llama-3.1-8b-instant"
GEMINI_ATTEMPT_TIMEOUT_SECONDS = 5

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

JSON_SCHEMA_HINT = """Respond with JSON only, no markdown fences:
{
  "findings": [
    {
      "severity": "critical" | "warning" | "info",
      "line_ref": "line N" or "line N-M",
      "title": "short title",
      "description": "what is wrong",
      "suggestion": "how to fix"
    }
  ],
  "overall_score": 0.0 to 1.0
}"""


def get_gemini_key() -> str | None:
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    return key.strip() if key and key.strip() else None


def get_groq_key() -> str | None:
    # Support GROQ_API_KEY and common typo QROK_API_KEY.
    for name in ("GROQ_API_KEY", "QROK_API_KEY", "qrok_API_KEY", "GROK_API_KEY"):
        key = os.environ.get(name)
        if key and key.strip():
            return key.strip()
    return None


def require_llm_key() -> None:
    if not get_gemini_key() and not get_groq_key():
        raise RuntimeError(
            "No LLM API key configured. Add to .env in the project root:\n"
            "  GEMINI_API_KEY=your_gemini_key\n"
            "  GROQ_API_KEY=your_groq_key   # used if Gemini fails"
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


def _gemini_structured_json(
    system_prompt: str,
    user_message: str,
    temperature: float,
) -> tuple[dict, int]:
    client = _gemini_client()
    response = client.models.generate_content(
        model=GEMINI_SPECIALIST_MODEL,
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


def _groq_chat(
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float,
    json_mode: bool,
) -> tuple[str, int]:
    key = get_groq_key()
    if not key:
        raise RuntimeError("GROQ_API_KEY not set")

    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"Groq HTTP {response.status_code}: {response.text[:300]}")
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Empty Groq response")
    text = choices[0].get("message", {}).get("content", "")
    if not text:
        raise ValueError("Empty Groq message content")
    usage = data.get("usage", {})
    tokens = int(usage.get("total_tokens", 0))
    return text, tokens


def _groq_structured_json(
    system_prompt: str,
    user_message: str,
    temperature: float,
) -> tuple[dict, int]:
    full_system = f"{system_prompt}\n\n{JSON_SCHEMA_HINT}"
    text, tokens = _groq_chat(
        full_system, user_message, GROQ_SPECIALIST_MODEL, temperature, json_mode=True
    )
    return _extract_json(text), tokens


def generate_structured_analysis(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.1,
) -> tuple[dict, int, str]:
    """Try Gemini (short timeout), then Groq. Returns (json_dict, token_usage, provider)."""
    gemini_error: Exception | None = None
    if get_gemini_key():
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    _gemini_structured_json, system_prompt, user_message, temperature
                )
                data, tokens = future.result(timeout=GEMINI_ATTEMPT_TIMEOUT_SECONDS)
            return data, tokens, "gemini"
        except FuturesTimeout:
            gemini_error = TimeoutError(
                f"Gemini exceeded {GEMINI_ATTEMPT_TIMEOUT_SECONDS}s"
            )
            logger.warning("Gemini timed out, trying Groq")
        except Exception as exc:
            gemini_error = exc
            logger.warning("Gemini structured call failed, trying Groq: %s", exc)

    if get_groq_key():
        try:
            data, tokens = _groq_structured_json(system_prompt, user_message, temperature)
            if gemini_error:
                logger.info("Using Groq fallback after Gemini failure")
            return data, tokens, "groq"
        except Exception as groq_exc:
            logger.warning("Groq structured call also failed: %s", groq_exc)
            if gemini_error:
                raise groq_exc from gemini_error
            raise

    if gemini_error:
        logger.error(
            "Gemini failed and no GROQ_API_KEY set for fallback. Add GROQ_API_KEY to .env"
        )
        raise gemini_error
    raise RuntimeError("No LLM provider available")


def _gemini_text(prompt: str, temperature: float) -> str:
    client = _gemini_client()
    response = client.models.generate_content(
        model=GEMINI_CONDUCTOR_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=temperature),
    )
    if not response.text:
        raise ValueError("Empty Gemini response")
    return response.text


def generate_text(prompt: str, temperature: float = 0.3) -> tuple[str, str]:
    """Try Gemini, then Groq for plain text. Returns (text, provider)."""
    gemini_error: Exception | None = None
    if get_gemini_key():
        try:
            return _gemini_text(prompt, temperature), "gemini"
        except Exception as exc:
            gemini_error = exc
            logger.warning("Gemini text call failed, trying Groq: %s", exc)

    if get_groq_key():
        text, _ = _groq_chat(
            "You are a concise technical writer.",
            prompt,
            GROQ_CONDUCTOR_MODEL,
            temperature,
            json_mode=False,
        )
        return text, "groq"

    if gemini_error:
        raise gemini_error
    raise RuntimeError("No LLM provider available")
