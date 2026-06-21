"""CodeChunk schema — output of the Ingestion Agent."""

import re
import os
from typing import Literal
from pydantic import BaseModel, Field, field_validator

SUPPORTED_LANGUAGES = Literal[
    "python", "javascript", "typescript", "java", "go", "cpp", "unknown"
]


class ChunkMetadata(BaseModel):
    total_lines: int = Field(ge=1)
    functions: list[str] = Field(default_factory=list)
    imports: list[str] = Field(default_factory=list)


class CodeChunk(BaseModel):
    chunk_id: str
    language: SUPPORTED_LANGUAGES
    filename: str = Field(max_length=255)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    content: str
    metadata: ChunkMetadata

    @field_validator("filename")
    @classmethod
    def sanitize_filename(cls, v: str) -> str:
        base = os.path.basename(v)
        if not base or ".." in v or "\x00" in v:
            raise ValueError("filename must not contain path traversal sequences")
        return base

    @field_validator("line_end")
    @classmethod
    def end_gte_start(cls, v: int, info) -> int:
        if "line_start" in info.data and v < info.data["line_start"]:
            raise ValueError("line_end must be >= line_start")
        return v

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("content must not be empty or whitespace-only")
        return v
