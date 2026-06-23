"""FastAPI routes — POST /api/review, GET /api/health."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.review import review_paste, review_file, review_url
from agents.ingestion import IngestionError

router = APIRouter()


class PasteRequest(BaseModel):
    content: str
    filename: Optional[str] = None


class URLRequest(BaseModel):
    url: str


class ReviewResponse(BaseModel):
    grade: str
    overall_health: int
    findings_count: int
    agents_unavailable: list[str]
    markdown_report: str


def _to_response(report) -> ReviewResponse:
    return ReviewResponse(
        grade=report.grade,
        overall_health=report.overall_health,
        findings_count=report.findings_count,
        agents_unavailable=report.agents_unavailable,
        markdown_report=report.markdown_report,
    )


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.post("/review/paste", response_model=ReviewResponse)
async def review_paste_endpoint(request: PasteRequest):
    try:
        report = await review_paste(request.content, request.filename)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return _to_response(report)


@router.post("/review/upload", response_model=ReviewResponse)
async def review_upload_endpoint(file: UploadFile = File(...)):
    content = await file.read()
    try:
        report = await review_file(file.filename or "unknown.py", content)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return _to_response(report)


@router.post("/review/url", response_model=ReviewResponse)
async def review_url_endpoint(request: URLRequest):
    try:
        report = await review_url(request.url)
    except IngestionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return _to_response(report)
