"""ADK 2.2 Workflow — orchestrates parallel specialist agents via JoinNode fan-out/fan-in.

Verified against google-adk==2.2.0 installed API:
- google.adk.workflow exposes: Workflow, FunctionNode, JoinNode, Edge, START
- edges accept tuples: 2-element (from, to) for sequential, 3-element (from, to, join) for fan-out
- FunctionNode with parameter_binding='state' binds params from state fields

Reference: https://google.github.io/adk-docs/workflows/graph-routes/
"""

import asyncio
import os
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from google.adk.workflow import Workflow, FunctionNode, JoinNode, START

from schemas.code_chunk import CodeChunk
from schemas.analysis_result import AnalysisResult
from schemas.review_report import ReviewReport
from agents.logic_agent import run_logic_agent
from agents.security_agent import run_security_agent
from agents.readability_agent import run_readability_agent
from agents.performance_agent import run_performance_agent
from agents.conductor import synthesize_report


# --- State schema for the ADK workflow ---

class ReviewState(BaseModel):
    chunks: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    report: dict[str, Any] | None = None


# --- Node functions: parameters must match state field names ---

async def ingest(chunks: list[dict[str, Any]]) -> dict[str, Any]:
    """Pass-through: chunks are pre-loaded into state before workflow starts."""
    return {"results": []}


async def logic(chunks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Run logic agent on all chunks."""
    new_results = []
    for chunk_data in chunks:
        chunk = CodeChunk(**chunk_data)
        result = await run_logic_agent(chunk)
        new_results.append(result.model_dump())
    return {"results": results + new_results}


async def security(chunks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Run security agent on all chunks."""
    new_results = []
    for chunk_data in chunks:
        chunk = CodeChunk(**chunk_data)
        result = await run_security_agent(chunk)
        new_results.append(result.model_dump())
    return {"results": results + new_results}


async def readability(chunks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Run readability agent on all chunks."""
    new_results = []
    for chunk_data in chunks:
        chunk = CodeChunk(**chunk_data)
        result = await run_readability_agent(chunk)
        new_results.append(result.model_dump())
    return {"results": results + new_results}


async def performance(chunks: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    """Run performance agent on all chunks."""
    new_results = []
    for chunk_data in chunks:
        chunk = CodeChunk(**chunk_data)
        result = await run_performance_agent(chunk)
        new_results.append(result.model_dump())
    return {"results": results + new_results}


async def conductor(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Synthesize all results into final report."""
    analysis_results = [AnalysisResult(**r) for r in results]
    report = await synthesize_report(analysis_results)
    return {"report": report.model_dump()}


# --- Build the ADK Workflow graph ---

_ingest = FunctionNode(func=ingest, name="ingest", timeout=5.0)
_logic = FunctionNode(func=logic, name="logic", timeout=10.0)
_security = FunctionNode(func=security, name="security", timeout=10.0)
_readability = FunctionNode(func=readability, name="readability", timeout=10.0)
_performance = FunctionNode(func=performance, name="performance", timeout=10.0)
_conductor = FunctionNode(func=conductor, name="conductor", timeout=10.0)
_join = JoinNode(name="collect_results")

review_workflow = Workflow(
    name="codessey_review",
    description="Parallel multi-agent code review with fan-out/fan-in",
    state_schema=ReviewState,
    edges=[
        (START, _ingest),
        (_ingest, _logic, _join),
        (_ingest, _security, _join),
        (_ingest, _readability, _join),
        (_ingest, _performance, _join),
        (_join, _conductor),
    ],
)


# --- Simple asyncio.gather fallback (used by CLI, tests, and if ADK overhead exceeds budget) ---

SPECIALIST_RUNNERS: dict[str, Callable[[CodeChunk], Awaitable[AnalysisResult]]] = {
    "logic": run_logic_agent,
    "security": run_security_agent,
    "readability": run_readability_agent,
    "performance": run_performance_agent,
}

SPECIALIST_RETRY_ROUNDS = int(os.environ.get("SPECIALIST_RETRY_ROUNDS", "2"))
SPECIALIST_RETRY_DELAY_SECONDS = float(os.environ.get("SPECIALIST_RETRY_DELAY", "3"))


async def _run_chunk_with_retries(chunk: CodeChunk) -> list[AnalysisResult]:
    """Parallel first pass; sequentially retry only failed specialists."""
    results: list[AnalysisResult] = list(
        await asyncio.gather(
            run_logic_agent(chunk),
            run_security_agent(chunk),
            run_readability_agent(chunk),
            run_performance_agent(chunk),
        )
    )

    for _ in range(SPECIALIST_RETRY_ROUNDS):
        failed_indices = [i for i, r in enumerate(results) if r.status != "ok"]
        if not failed_indices:
            break
        for idx in failed_indices:
            agent = results[idx].agent
            await asyncio.sleep(SPECIALIST_RETRY_DELAY_SECONDS)
            results[idx] = await SPECIALIST_RUNNERS[agent](chunk)

    return results


async def run_review_pipeline(chunks: list[CodeChunk]) -> ReviewReport:
    """Run the full review pipeline using plain asyncio.gather for parallel dispatch."""
    all_results: list[AnalysisResult] = []

    for chunk in chunks:
        all_results.extend(await _run_chunk_with_retries(chunk))

    return await synthesize_report(all_results)
