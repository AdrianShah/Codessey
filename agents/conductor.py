"""Conductor agent — deduplication, scoring, redaction, synthesis."""

import os
import json
import asyncio
from collections import defaultdict

from google import genai
from google.genai import types

from schemas.analysis_result import AnalysisResult, Finding
from schemas.review_report import ReviewReport
from security.redactor import redact_secrets
from utils.report_renderer import render_report

CONDUCTOR_MODEL = "gemini-2.5-pro"
CONDUCTOR_TIMEOUT_SECONDS = 5


async def synthesize_report(results: list[AnalysisResult]) -> ReviewReport:
    """Combine specialist results into a final ReviewReport."""
    available = [r for r in results if r.status == "ok"]
    unavailable_agents = [r.agent for r in results if r.status != "ok"]

    all_findings = _dedupe_findings(available)

    critical = sum(1 for f in all_findings if f.severity == "critical")
    warning = sum(1 for f in all_findings if f.severity == "warning")
    info = sum(1 for f in all_findings if f.severity == "info")

    health_score, grade = ReviewReport.compute_health(critical, warning, info)

    # Generate executive summary via LLM (best-effort)
    summary = await _generate_summary(all_findings, health_score, grade)

    report = ReviewReport(
        findings=all_findings,
        findings_count=len(all_findings),
        overall_health=health_score,
        grade=grade,
        agents_unavailable=unavailable_agents,
        executive_summary=summary,
    )

    # Redact secrets in the rendered markdown
    report.markdown_report = redact_secrets(render_report(report))
    return report


def _dedupe_findings(results: list[AnalysisResult]) -> list[Finding]:
    """Deduplicate findings across agents — same line+title keeps higher severity."""
    severity_rank = {"critical": 3, "warning": 2, "info": 1}
    seen: dict[str, Finding] = {}

    for result in results:
        for finding in result.findings:
            key = f"{finding.line_ref}:{finding.title.lower().strip()}"
            if key in seen:
                existing = seen[key]
                if severity_rank[finding.severity] > severity_rank[existing.severity]:
                    seen[key] = finding
            else:
                seen[key] = finding

    # Sort by severity (critical first), then by line ref
    findings = list(seen.values())
    findings.sort(key=lambda f: (-severity_rank[f.severity], f.line_ref))
    return findings


async def _generate_summary(findings: list[Finding], score: int, grade: str) -> str:
    """Generate executive summary using Gemini Pro. Falls back to template on failure."""
    try:
        return await asyncio.wait_for(
            _call_summary_llm(findings, score, grade),
            timeout=CONDUCTOR_TIMEOUT_SECONDS,
        )
    except Exception:
        return _fallback_summary(findings, score, grade)


async def _call_summary_llm(findings: list[Finding], score: int, grade: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _fallback_summary(findings, score, grade)

    client = genai.Client(api_key=api_key)

    findings_text = "\n".join(
        f"- [{f.severity}] {f.title} ({f.line_ref})" for f in findings[:15]
    )

    prompt = (
        f"Write a 2-3 sentence executive summary for a code review.\n"
        f"Health score: {score}/100 (Grade {grade})\n"
        f"Key findings:\n{findings_text}\n\n"
        f"Be concise and actionable. Focus on the most important issues."
    )

    response = await client.aio.models.generate_content(
        model=CONDUCTOR_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )

    return response.text or _fallback_summary(findings, score, grade)


def _fallback_summary(findings: list[Finding], score: int, grade: str) -> str:
    critical = sum(1 for f in findings if f.severity == "critical")
    warning = sum(1 for f in findings if f.severity == "warning")
    if not findings:
        return "No issues detected. The code appears clean and well-structured."
    parts = []
    if critical:
        parts.append(f"{critical} critical issue{'s' if critical > 1 else ''}")
    if warning:
        parts.append(f"{warning} warning{'s' if warning > 1 else ''}")
    return f"Code health: {grade} ({score}/100). Found {', '.join(parts)}. Review the findings below for details."
