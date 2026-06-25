"""FastAPI application entry point."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.routes import router

app = FastAPI(title="Codessey", version="1.0.0")
app.include_router(router, prefix="/api")

# ponytail: local dev only — Vercel serves public/ from CDN; no app.mount there
if not os.environ.get("VERCEL") and Path("public").is_dir():
    app.mount("/", StaticFiles(directory="public", html=True), name="static")
