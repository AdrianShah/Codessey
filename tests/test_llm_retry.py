"""Tests for LLM retry helpers."""

from unittest.mock import patch

import pytest

from agents.llm_client import (
    is_retryable_error,
    parse_retry_delay,
    retry_call,
)


class TestParseRetryDelay:
    def test_try_again_in_seconds(self):
        exc = RuntimeError('429 rate limit: try again in 6.24s')
        assert parse_retry_delay(exc) == pytest.approx(6.24)

    def test_gemini_retry_delay(self):
        exc = RuntimeError("{'retryDelay': '9s'}")
        assert parse_retry_delay(exc) == 9.0

    def test_no_hint_returns_none(self):
        assert parse_retry_delay(RuntimeError("something else")) is None


class TestIsRetryableError:
    def test_429_retryable(self):
        assert is_retryable_error(RuntimeError("429 rate limit exceeded"))

    def test_503_retryable(self):
        assert is_retryable_error(RuntimeError("503 UNAVAILABLE"))

    def test_401_not_retryable(self):
        assert not is_retryable_error(RuntimeError("401 invalid API key"))

    def test_gemini_resource_exhausted_retryable(self):
        assert is_retryable_error(RuntimeError("429 RESOURCE_EXHAUSTED quota"))

    def test_timeout_retryable(self):
        assert is_retryable_error(TimeoutError("Gemini exceeded 15s"))


class TestRetryCall:
    def test_succeeds_without_retry(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            return "ok"

        assert retry_call(fn, max_attempts=3) == "ok"
        assert calls["n"] == 1

    def test_retries_then_succeeds(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            if calls["n"] < 2:
                raise RuntimeError("429 rate limit: try again in 0.01s")
            return "ok"

        with patch("agents.llm_client.time.sleep"):
            assert retry_call(fn, max_attempts=3) == "ok"
        assert calls["n"] == 2

    def test_non_retryable_raises_immediately(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise RuntimeError("401 invalid API key")

        with pytest.raises(RuntimeError, match="401"):
            retry_call(fn, max_attempts=3)
        assert calls["n"] == 1

    def test_exhausts_max_attempts(self):
        calls = {"n": 0}

        def fn():
            calls["n"] += 1
            raise RuntimeError("503 UNAVAILABLE")

        with patch("agents.llm_client.time.sleep"):
            with pytest.raises(RuntimeError, match="503"):
                retry_call(fn, max_attempts=3)
        assert calls["n"] == 3

    def test_uses_parsed_delay(self):
        delays: list[float] = []

        def fn():
            raise RuntimeError("429 rate limit: try again in 0.05s")

        def capture_sleep(seconds: float) -> None:
            delays.append(seconds)

        with patch("agents.llm_client.time.sleep", side_effect=capture_sleep):
            with pytest.raises(RuntimeError):
                retry_call(fn, max_attempts=2)

        assert len(delays) == 1
        assert delays[0] >= 0.05
