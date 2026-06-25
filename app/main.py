"""FastAPI application entry point."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.routes import router

app = FastAPI(title="Codessey", version="1.0.0")
app.include_router(router, prefix="/api")

PUBLIC = Path(__file__).resolve().parent.parent / "public"
INDEX = PUBLIC / "index.html"


@app.get("/", include_in_schema=False, response_model=None)
async def read_root():
    """Serve homepage — FastAPI owns / on Vercel; CDN serves other public/ assets."""
    if INDEX.is_file():
        return FileResponse(INDEX, media_type="text/html")
    return RedirectResponse("/index.html", status_code=302)


# ponytail: local dev only — Vercel serves public/ assets from CDN; no app.mount there
if not os.environ.get("VERCEL") and PUBLIC.is_dir():
    app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="static")
