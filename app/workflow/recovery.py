"""Deterministic failure classification, retry policy, and controlled failure injection."""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel


class FailureCategory(str, Enum):
    """Deterministic failure taxonomy for operations workflow tasks."""

    TRANSIENT = "TRANSIENT"
    VALIDATION = "VALIDATION"
    NOT_FOUND = "NOT_FOUND"
    PERMISSION = "PERMISSION"
    UNKNOWN = "UNKNOWN"


class OperationsWorkflowError(Exception):
    """Base exception for workflow operations."""


class TransientFailureError(OperationsWorkflowError):
    """Temporary failure that may succeed if retried (e.g. timeout, service unavailable)."""


class ValidationFailureError(OperationsWorkflowError):
    """Input or output payload violates schema or business invariants."""


class NotFoundFailureError(OperationsWorkflowError):
    """Target entity or resource could not be found."""


class PermissionFailureError(OperationsWorkflowError):
    """Operation lacks sufficient authorization."""


def classify_failure(exc: Any) -> tuple[FailureCategory, bool]:
    """Deterministically classify an exception or error string and determine retryability.

    Returns:
        tuple[FailureCategory, bool]: (Category, is_retryable)
    """
    if isinstance(exc, TransientFailureError):
        return FailureCategory.TRANSIENT, True
    if isinstance(exc, ValidationFailureError):
        return FailureCategory.VALIDATION, False
    if isinstance(exc, NotFoundFailureError):
        return FailureCategory.NOT_FOUND, False
    if isinstance(exc, PermissionFailureError):
        return FailureCategory.PERMISSION, False

    msg = str(exc).lower()
    exc_type = type(exc).__name__ if isinstance(exc, Exception) else ""

    # Transient triggers: timeout, temporary, unavailable, connection reset, 503, 429
    if any(k in msg for k in ["timeout", "timed out", "temporarily unavailable", "connection reset", "rate limit", "busy", "transient"]) or exc_type in ["TimeoutError", "ConnectionResetError"]:
        return FailureCategory.TRANSIENT, True

    # Validation triggers: validation, schema, invalid, mismatch
    if any(k in msg for k in ["validation", "invalid input", "schema", "contract violation", "valueerror"]) or "validation" in exc_type.lower():
        return FailureCategory.VALIDATION, False

    # Not found triggers: not found, does not exist, missing
    if any(k in msg for k in ["not found", "does not exist", "missing"]) or exc_type in ["KeyError", "FileNotFoundError"]:
        return FailureCategory.NOT_FOUND, False

    # Permission triggers: permission, unauthorized, forbidden, unapproved
    if any(k in msg for k in ["permission denied", "unauthorized", "forbidden", "access denied"]) or exc_type in ["PermissionError"]:
        return FailureCategory.PERMISSION, False

    return FailureCategory.UNKNOWN, False


class RetryPolicy(BaseModel):
    """Deterministic bounded retry policy."""

    max_retries: int = 2

    def should_retry(self, category: FailureCategory, current_retry_count: int) -> bool:
        """Evaluate if a task failure is allowed to retry."""
        if category == FailureCategory.TRANSIENT and current_retry_count < self.max_retries:
            return True
        return False


class FailureInjector:
    """Controlled deterministic failure injection seam for testing and demos.

    When inactive (no failures configured), operations execute with zero alteration.
    """

    def __init__(self) -> None:
        self._injections: dict[str, dict[str, Any]] = {}

    def inject_transient_failure(self, tool_name: str, count: int = 1, message: str = "Simulated transient timeout") -> None:
        """Configure transient failures that succeed after count attempts."""
        self._injections[tool_name] = {
            "category": FailureCategory.TRANSIENT,
            "count": count,
            "message": message,
            "exception_cls": TransientFailureError,
        }

    def inject_permanent_failure(
        self,
        tool_name: str,
        category: FailureCategory = FailureCategory.UNKNOWN,
        message: str = "Simulated permanent failure",
    ) -> None:
        """Configure a permanent failure that will not recover."""
        exc_cls: type[Exception] = RuntimeError
        if category == FailureCategory.VALIDATION:
            exc_cls = ValidationFailureError
        elif category == FailureCategory.NOT_FOUND:
            exc_cls = NotFoundFailureError
        elif category == FailureCategory.PERMISSION:
            exc_cls = PermissionFailureError
        elif category == FailureCategory.TRANSIENT:
            exc_cls = TransientFailureError

        self._injections[tool_name] = {
            "category": category,
            "count": 999999,  # Permanent
            "message": message,
            "exception_cls": exc_cls,
        }

    def check_failure(self, tool_name: str) -> None:
        """Check if a failure is injected for tool_name. If configured, raise and decrement count."""
        if tool_name not in self._injections:
            return

        config = self._injections[tool_name]
        if config["count"] > 0:
            config["count"] -= 1
            if config["count"] == 0:
                del self._injections[tool_name]
            raise config["exception_cls"](config["message"])

    def clear(self) -> None:
        """Clear all active failure injections."""
        self._injections.clear()


# Global controlled failure injector seam
failure_injector = FailureInjector()
