"""Process-wide error types for Agent runtime vs LLM unavailability."""

from __future__ import annotations


class LLMUnavailableError(RuntimeError):
    """Model provider/auth/network is down. Observable fallback to understand is allowed."""


def is_llm_unavailable(exc: BaseException) -> bool:
    if isinstance(exc, LLMUnavailableError):
        return True
    names = {cls.__name__ for cls in type(exc).__mro__}
    if names & {
        "APIConnectionError",
        "AuthenticationError",
        "PermissionDeniedError",
        "RateLimitError",
        "APITimeoutError",
        "InternalServerError",
        "ServiceUnavailableError",
        "ConnectError",
        "ConnectTimeout",
        "ReadTimeout",
        "TimeoutException",
    }:
        return True
    status = getattr(exc, "status_code", None)
    if status in {401, 403, 408, 429, 500, 502, 503, 504}:
        return True
    return False
