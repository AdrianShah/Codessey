"""AnalysisResult schema — output of each specialist agent."""

import re
from typing import Literal
from pydantic import BaseModel, Field, field_validator

LINE_REF_PATTERN = re.compile(r"^line \d+(-\d+)?$")
MAX_FINDINGS_PER_CHUNK = 25


class Finding(BaseModel):
    severity: Literal["critical", "warning", "info"]
    line_ref: str = Field(max_length=30)
    title: str = Field(max_length=120)
    description: str = Field(max_length=500)
    suggestion: str = Field(max_length=500)

    @field_validator("line_ref")
    @classmethod
    def validate_line_ref(cls, v: str) -> str:
        if not LINE_REF_PATTERN.match(v):
            raise ValueError(
                f"line_ref must match 'line N' or 'line N-M', got: {v!r}"
            )
        return v


class AnalysisResult(BaseModel):
    agent: Literal["logic", "security", "readability", "performance"]
    chunk_id: str
    status: Literal["ok", "timeout", "error"] = "ok"
    findings: list[Finding] = Field(default_factory=list, max_length=MAX_FINDINGS_PER_CHUNK)
    overall_score: float = Field(ge=0.0, le=1.0)
    token_usage: int = Field(ge=0, default=0)

    @field_validator("findings")
    @classmethod
    def cap_findings(cls, v: list[Finding]) -> list[Finding]:
        if len(v) > MAX_FINDINGS_PER_CHUNK:
            return v[:MAX_FINDINGS_PER_CHUNK]
        return v
