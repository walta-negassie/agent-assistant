"""
tests/test_retry.py — tests for retry/backoff and error classification.

Uses fake functions that fail on command, instead of hitting real APIs,
so these tests run instantly and don't depend on network conditions.
"""

import pytest
import requests
from unittest.mock import Mock
from retry import (
    with_retry,
    classify_http_error,
    PermanentError,
    TransientError,
)


def make_http_error(status_code):
    """Builds a fake requests.exceptions.HTTPError with a given status code."""
    response = Mock()
    response.status_code = status_code
    error = requests.exceptions.HTTPError(response=response)
    return error


# ---- Error classification ----

@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_server_and_rate_limit_errors_classified_as_transient(status):
    error = make_http_error(status)
    classified = classify_http_error(error)
    assert isinstance(classified, TransientError)


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_classified_as_permanent(status):
    error = make_http_error(status)
    classified = classify_http_error(error)
    assert isinstance(classified, PermanentError)


# ---- Retry behavior ----

def test_succeeds_immediately_with_no_failures():
    calls = {"count": 0}

    def always_succeeds():
        calls["count"] += 1
        return "ok"

    result = with_retry(always_succeeds, max_attempts=3, base_delay=0)
    assert result == "ok"
    assert calls["count"] == 1  # should not retry if it succeeds first try


def test_retries_transient_error_then_succeeds():
    calls = {"count": 0}

    def fails_twice_then_succeeds():
        calls["count"] += 1
        if calls["count"] < 3:
            raise TransientError("simulated failure")
        return "ok"

    result = with_retry(fails_twice_then_succeeds, max_attempts=3, base_delay=0)
    assert result == "ok"
    assert calls["count"] == 3


def test_permanent_error_fails_immediately_without_retrying():
    calls = {"count": 0}

    def always_fails_permanently():
        calls["count"] += 1
        raise make_http_error(404)

    with pytest.raises(PermanentError):
        with_retry(always_fails_permanently, max_attempts=3, base_delay=0)

    # Should fail on the FIRST attempt, no retries wasted on a 404
    assert calls["count"] == 1


def test_transient_error_exhausts_all_attempts_then_raises():
    calls = {"count": 0}

    def always_fails_transiently():
        calls["count"] += 1
        raise TransientError("always fails")

    with pytest.raises(TransientError):
        with_retry(always_fails_transiently, max_attempts=3, base_delay=0)

    assert calls["count"] == 3  # used every attempt before giving up