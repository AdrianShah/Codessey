"""Shared specialist agent invocation pattern."""

import asyncio
import logging
import re
import secrets

from agents.llm_client import generate_structured_analysis
from schemas.code_chunk import CodeChunk
from schemas.analysis_result import AnalysisResult, Finding

logger = logging.getLogger(__name__)

SPECIALIST_TIMEOUT_SECONDS = 25
SPECIALIST_TEMPERATURE = 0.1


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


def _normalize_line_ref(raw: str) -> str | None:
    """Normalize model line_ref to 'line N' or 'line N-M' format."""
    text = raw.strip()
    match = re.match(r"^line\s+(\d+)(?:\s*-\s*(\d+))?$", text, re.IGNORECASE)
    if match:
        start = match.group(1)
        end = match.group(2)
        return f"line {start}-{end}" if end else f"line {start}"
    match = re.match(r"^(\d+)(?:\s*-\s*(\d+))?$", text)
    if match:
        start = match.group(1)
        end = match.group(2)
        return f"line {start}-{end}" if end else f"line {start}"
    return None


def _parse_findings(data: dict) -> list[Finding]:
    findings: list[Finding] = []
    for raw in data.get("findings", [])[:25]:
        if not isinstance(raw, dict):
            continue
        line_ref = _normalize_line_ref(str(raw.get("line_ref", "")))
        if not line_ref:
            continue
        raw = {**raw, "line_ref": line_ref}
        try:
            findings.append(Finding(**raw))
        except Exception:
            continue
    return findings


def _call_specialist_sync(
    agent_name: str,
    system_prompt: str,
    chunk: CodeChunk,
) -> AnalysisResult:
    user_message = _build_user_message(chunk)
    data, tokens, provider = generate_structured_analysis(
        system_prompt, user_message, SPECIALIST_TEMPERATURE
    )
    findings = _parse_findings(data)
    logger.debug("Specialist %s used provider %s", agent_name, provider)
    return AnalysisResult(
        agent=agent_name,  # type: ignore[arg-type]
        chunk_id=chunk.chunk_id,
        status="ok",
        findings=findings,
        overall_score=max(0.0, min(1.0, float(data.get("overall_score", 0.5)))),
        token_usage=tokens,
    )


async def run_specialist(
    agent_name: str,
    system_prompt: str,
    chunk: CodeChunk,
) -> AnalysisResult:
    """Run a specialist agent. Always returns an AnalysisResult — never raises."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_call_specialist_sync, agent_name, system_prompt, chunk),
            timeout=SPECIALIST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("Specialist %s timed out on chunk %s", agent_name, chunk.chunk_id)
        return AnalysisResult(
            agent=agent_name,  # type: ignore[arg-type]
            chunk_id=chunk.chunk_id,
            status="timeout",
            findings=[],
            overall_score=0.5,
            token_usage=0,
        )
    except Exception as exc:
        logger.warning("Specialist %s failed: %s", agent_name, exc)
        return AnalysisResult(
            agent=agent_name,  # type: ignore[arg-type]
            chunk_id=chunk.chunk_id,
            status="error",
            findings=[],
            overall_score=0.5,
            token_usage=0,
        )
