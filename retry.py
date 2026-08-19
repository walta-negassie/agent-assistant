"""
retry.py — retry logic for transient failures.

Wraps a function call with automatic retries and exponential backoff,
but only for errors that are actually worth retrying. Permanent errors
(bad input, auth failure, not found) should fail immediately instead
of wasting time retrying something that will never succeed.
"""

import time
import requests
from googleapiclient.errors import HttpError

class PermanentError(Exception):
    """Raised for errors that retrying will never fix."""
    pass


class TransientError(Exception):
    """Raised for errors that might succeed if retried."""
    pass


def classify_http_error(exc: requests.exceptions.HTTPError) -> Exception:
    """Turn a raw HTTP error into a PermanentError or TransientError."""
    status = exc.response.status_code if exc.response is not None else None

    # 429 = rate limited, 500/502/503/504 = server-side, worth retrying
    if status in (429, 500, 502, 503, 504):
        return TransientError(f"HTTP {status}: {exc}")

    # 400/401/403/404 = our fault or permission issue, retrying won't help
    if status in (400, 401, 403, 404):
        return PermanentError(f"HTTP {status}: {exc}")

    # Unknown status — treat cautiously as permanent so we don't loop forever
    return PermanentError(f"HTTP {status}: {exc}")


def classify_google_error(exc: HttpError) -> Exception:
    """Turn a Google API client error into a PermanentError or TransientError."""
    status = exc.resp.status if exc.resp is not None else None

    if status in (429, 500, 502, 503, 504):
        return TransientError(f"Google API HTTP {status}: {exc}")

    if status in (400, 401, 403, 404):
        return PermanentError(f"Google API HTTP {status}: {exc}")

    return PermanentError(f"Google API HTTP {status}: {exc}")
    

def with_retry(func, *args, max_attempts: int = 3, base_delay: float = 1.0, **kwargs):
    """
    Calls func(*args, **kwargs). Retries on TransientError / rate limits /
    network issues, up to max_attempts, with exponential backoff.
    Raises immediately on PermanentError — no point retrying those.
    """
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return func(*args, **kwargs)

        except requests.exceptions.HTTPError as e:
            classified = classify_http_error(e)
            if isinstance(classified, PermanentError):
                raise classified
            last_exception = classified

        except HttpError as e:
            classified = classify_google_error(e)
            if isinstance(classified, PermanentError):
                raise classified
            last_exception = classified

        except requests.exceptions.ConnectionError as e:
            last_exception = TransientError(f"Connection error: {e}")

        except requests.exceptions.Timeout as e:
            last_exception = TransientError(f"Timeout: {e}")

        except TransientError as e:
            last_exception = e

        if attempt < max_attempts:
            delay = base_delay * (2 ** (attempt - 1))  # 1s, 2s, 4s...
            print(f"[RETRY] Attempt {attempt} failed ({last_exception}). Retrying in {delay}s...")
            time.sleep(delay)

    # All attempts exhausted
    raise last_exception