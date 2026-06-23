"""Report renderer — Markdown output with HTML escaping (PRD FR-18)."""

import html
from schemas.review_report import ReviewReport
from schemas.analysis_result import Finding


def render_report(report: ReviewReport, review_incomplete: bool = False) -> str:
    """Render a ReviewReport as safe Markdown."""
    sections: list[str] = []

    sections.append(f"# Code Review Report — Grade: {report.grade} ({report.overall_health}/100)\n")

    if report.agents_unavailable:
        agents_str = ", ".join(report.agents_unavailable)
        sections.append(f"> **Note:** The following checks were unavailable: {agents_str}\n")

    if report.executive_summary:
        sections.append(f"## Executive Summary\n\n{_escape(report.executive_summary)}\n")

    criticals = [f for f in report.findings if f.severity == "critical"]
    warnings = [f for f in report.findings if f.severity == "warning"]
    infos = [f for f in report.findings if f.severity == "info"]

    if criticals:
        sections.append("## 🔴 Critical Issues\n")
        for f in criticals:
            sections.append(_render_finding(f))

    if warnings:
        sections.append("## 🟡 Warnings\n")
        for f in warnings:
            sections.append(_render_finding(f))

    if infos:
        sections.append("## 🟢 Info\n")
        for f in infos:
            sections.append(_render_finding(f))

    if not report.findings:
        if review_incomplete:
            sections.append("## Results\n\nReview incomplete — no agent results were received.\n")
        else:
            sections.append("## Results\n\nNo issues found. Code looks good!\n")

    return "\n".join(sections)


def _render_finding(finding: Finding) -> str:
    return (
        f"### {_escape(finding.title)} ({finding.line_ref})\n\n"
        f"{_escape(finding.description)}\n\n"
        f"**Suggestion:** {_escape(finding.suggestion)}\n\n"
        "---\n"
    )


def _escape(text: str) -> str:
    """HTML-escape text to prevent XSS when rendered in HTML contexts."""
    return html.escape(text, quote=False)
