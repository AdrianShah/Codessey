"""Tests for security features — redaction, URL validation, SSRF."""

import pytest
from security.redactor import redact_secrets, contains_secret
from security.url_validator import validate_github_url, URLValidationError


class TestRedactor:
    def test_aws_key_redacted(self):
        text = "key = AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIA" in result
        assert "MPLE" in result
        assert "AKIAIOSFODNN7EXAMPLE" not in result

    def test_google_key_redacted(self):
        text = "AIzaSyA1234567890abcdefghijklmnopqrstuvwx"
        result = redact_secrets(text)
        assert "AIza" in result
        assert "AIzaSyA1234567890abcdefghijklmnopqrstuvwx" not in result

    def test_no_secret_unchanged(self):
        text = "hello world, just normal code"
        assert redact_secrets(text) == text

    def test_contains_secret_positive(self):
        assert contains_secret("my key is sk-1234567890abcdefghijklmnop")

    def test_contains_secret_negative(self):
        assert not contains_secret("just a normal comment")


class TestSSRFPrevention:
    def test_internal_ip_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://169.254.169.254/latest/meta-data")

    def test_localhost_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://localhost/etc/passwd/blob/x/y")

    def test_non_github_rejected(self):
        with pytest.raises(URLValidationError):
            validate_github_url("https://evil.com/user/repo/blob/main/f.py")

    def test_file_scheme_rejected(self):
        with pytest.raises(URLValidationError, match="HTTPS"):
            validate_github_url("file:///etc/passwd")
