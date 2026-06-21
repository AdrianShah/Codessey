"""ReviewReport schema — final Conductor output."""

from typing import Literal
from pydantic import BaseModel, Field
from schemas.analysis_result import Finding


class ReviewReport(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    findings_count: int = Field(ge=0, default=0)
    overall_health: int = Field(ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"]
    agents_unavailable: list[str] = Field(default_factory=list)
    executive_summary: str = ""
    markdown_report: str = ""

    @staticmethod
    def compute_health(critical: int, warning: int, info: int) -> tuple[int, str]:
        """Deterministic scoring formula (PRD Section 6.5)."""
        penalty = critical * 15 + warning * 5 + info * 1
        score = max(0, 100 - penalty)
        if score >= 90:
            grade = "A"
        elif score >= 75:
            grade = "B"
        elif score >= 60:
            grade = "C"
        elif score >= 40:
            grade = "D"
        else:
            grade = "F"
        return score, grade
