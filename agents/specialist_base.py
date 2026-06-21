"""Shared specialist agent invocation pattern.

Every specialist agent follows the same contract:
- Takes a CodeChunk
- Calls Gemini 2.5 Flash with a structured JSON schema
- Returns an AnalysisResult (always — even on failure)
"""

import asyncio
import json
import os
import secrets

from google import genai
from google.genai import types

from schemas.code_chunk import CodeChunk
from schemas.analysis_result import AnalysisResult, Finding

SPECIALIST_MODEL = "gemini-2.5-flash"
SPECIALIST_TIMEOUT_SECONDS = 8
SPECIALIST_TEMPERATURE = 0.1

# Per-request random delimiter for prompt-injection defense (PRD Section 6.1)
def _make_delimiter() -> str:
    return f"CODE_INPUT_{secrets.token_hex(8)}"


def _build_user_message(chunk: CodeChunk) -> str:
    delimiter = _make_delimiter()
    return (
        f"Analyze the following code. The code is enclosed between {delimiter} markers.\n\n"
        f"<{delimiter}>\n{chunk.content}\n</{delimiter}>\n\n"
        f"File: {chunk.filename} (lines {chunk.line_start}-{chunk.line_end})\n"
        f"Language: {chunk.language}\n"
    )


ANALYSIS_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "warning", "info"]},
                    "line_ref": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "line_ref", "title", "description", "suggestion"],
            },
        },
        "overall_score": {"type": "number"},
    },
    "required": ["findings", "overall_score"],
}


async def run_specialist(
    agent_name: str,
    system_prompt: str,
    chunk: CodeChunk,
) -> AnalysisResult:
    """Run a specialist agent. Always returns an AnalysisResult — never raises."""
    try:
        result = await asyncio.wait_for(
            _call_gemini(agent_name, system_prompt, chunk),
            timeout=SPECIALIST_TIMEOUT_SECONDS,
        )
        return result
    except asyncio.TimeoutError:
        return AnalysisResult(
            agent=agent_name,  # type: ignore[arg-type]
            chunk_id=chunk.chunk_id,
            status="timeout",
            findings=[],
            overall_score=0.5,
            token_usage=0,
        )
    except Exception:
        return AnalysisResult(
            agent=agent_name,  # type: ignore[arg-type]
            chunk_id=chunk.chunk_id,
            status="error",
            findings=[],
            overall_score=0.5,
            token_usage=0,
        )


async def _call_gemini(
    agent_name: str,
    system_prompt: str,
    chunk: CodeChunk,
) -> AnalysisResult:
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    user_message = _build_user_message(chunk)

    response = await client.aio.models.generate_content(
        model=SPECIALIST_MODEL,
        contents=user_message,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=SPECIALIST_TEMPERATURE,
            response_mime_type="application/json",
            response_schema=ANALYSIS_RESULT_SCHEMA,
        ),
    )

    text = response.text
    if not text:
        raise ValueError("Empty response from model")

    data = json.loads(text)
    findings = []
    for f in data.get("findings", [])[:25]:
        try:
            findings.append(Finding(**f))
        except Exception:
            continue

    return AnalysisResult(
        agent=agent_name,  # type: ignore[arg-type]
        chunk_id=chunk.chunk_id,
        status="ok",
        findings=findings,
        overall_score=max(0.0, min(1.0, float(data.get("overall_score", 0.5)))),
        token_usage=response.usage_metadata.total_token_count if response.usage_metadata else 0,
    )
