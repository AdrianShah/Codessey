"""Shared review pipeline — used by both FastAPI routes and CLI."""

from agents.llm_client import require_llm_key
from schemas.review_report import ReviewReport
from agents.ingestion import ingest_paste, ingest_file, ingest_github_url, IngestionError
from agents.workflow import run_review_pipeline


def _ensure_api_key() -> None:
    require_llm_key()


async def review_paste(text: str, filename: str | None = None) -> ReviewReport:
    """Run full review on pasted code."""
    _ensure_api_key()
    chunks = await ingest_paste(text, filename)
    return await run_review_pipeline(chunks)


async def review_file(filename: str, content: bytes) -> ReviewReport:
    """Run full review on uploaded file."""
    _ensure_api_key()
    chunks = await ingest_file(filename, content)
    return await run_review_pipeline(chunks)


async def review_url(url: str) -> ReviewReport:
    """Run full review on code fetched from a GitHub URL."""
    _ensure_api_key()
    chunks = await ingest_github_url(url)
    return await run_review_pipeline(chunks)
