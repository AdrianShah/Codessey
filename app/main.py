"""FastAPI application entry point."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.routes import router

app = FastAPI(title="Codessey", version="1.0.0")
app.include_router(router, prefix="/api")

@app.get("/index.html")
async def index_html_redirect() -> RedirectResponse:
    return RedirectResponse("/", status_code=301)


if not os.environ.get("VERCEL") and Path("public").is_dir():
    app.mount("/", StaticFiles(directory="public", html=True), name="static")
