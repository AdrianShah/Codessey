"""Tests for the Conductor — scoring, deduplication, report rendering."""

import pytest
from schemas.analysis_result import AnalysisResult, Finding
from schemas.review_report import ReviewReport
from agents.conductor import _dedupe_findings
from utils.report_renderer import render_report


class TestDeterministicScoring:
    def test_perfect_score(self):
        score, grade = ReviewReport.compute_health(0, 0, 0)
        assert score == 100
        assert grade == "A"

    def test_two_critical_three_warning_one_info(self):
        score, grade = ReviewReport.compute_health(2, 3, 1)
        assert score == 54  # 100 - 30 - 15 - 1
        assert grade == "D"

    def test_many_criticals_floors_at_zero(self):
        score, grade = ReviewReport.compute_health(10, 0, 0)
        assert score == 0
        assert grade == "F"

    def test_grade_boundaries(self):
        assert ReviewReport.compute_health(0, 2, 0) == (90, "A")
        assert ReviewReport.compute_health(0, 3, 0) == (85, "B")
        assert ReviewReport.compute_health(0, 5, 4) == (71, "C")


class TestDeduplication:
    def test_same_finding_deduped(self):
        f1 = Finding(severity="warning", line_ref="line 5", title="Unused variable", description="x", suggestion="y")
        f2 = Finding(severity="critical", line_ref="line 5", title="Unused variable", description="z", suggestion="w")
        r1 = AnalysisResult(agent="logic", chunk_id="c1", findings=[f1], overall_score=0.8)
        r2 = AnalysisResult(agent="security", chunk_id="c1", findings=[f2], overall_score=0.7)
        deduped = _dedupe_findings([r1, r2])
        assert len(deduped) == 1
        assert deduped[0].severity == "critical"

    def test_different_findings_kept(self):
        f1 = Finding(severity="warning", line_ref="line 5", title="Issue A", description="x", suggestion="y")
        f2 = Finding(severity="info", line_ref="line 10", title="Issue B", description="z", suggestion="w")
        r1 = AnalysisResult(agent="logic", chunk_id="c1", findings=[f1, f2], overall_score=0.8)
        deduped = _dedupe_findings([r1])
        assert len(deduped) == 2


class TestReportRenderer:
    def test_html_escaped_in_output(self):
        report = ReviewReport(
            findings=[Finding(
                severity="critical",
                line_ref="line 1",
                title="<script>alert(1)</script>",
                description="XSS attempt",
                suggestion="Escape output",
            )],
            findings_count=1,
            overall_health=85,
            grade="B",
        )
        rendered = render_report(report)
        assert "<script>" not in rendered
        assert "&lt;script&gt;" in rendered

    def test_empty_findings_report(self):
        report = ReviewReport(
            findings=[],
            findings_count=0,
            overall_health=100,
            grade="A",
        )
        rendered = render_report(report)
        assert "No issues found" in rendered
