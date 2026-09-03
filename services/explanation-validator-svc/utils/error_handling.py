"""Production-grade error handling and logging for Explanation Validator."""

from __future__ import annotations

import logging
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union
from enum import Enum

from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from config import get_config

config = get_config()
logger = logging.getLogger(__name__)


# ============================================
# Custom Exceptions
# ============================================

class ErrorSeverity(str, Enum):
    """Error severity levels for classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BaseValidatorException(Exception):
    """Base exception for all validator errors."""

    def __init__(
        self,
        message: str,
        error_code: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.error_code = error_code
        self.severity = severity
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)
        self.error_id = str(uuid.uuid4())
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            "severity": self.severity.value,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


# ============================================
# Specific Exceptions
# ============================================

class ValidationError(BaseValidatorException):
    """Raised when validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            severity=ErrorSeverity.HIGH,
            details=details,
        )


class GroundingError(BaseValidatorException):
    """Raised when grounding check fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="GROUNDING_ERROR",
            severity=ErrorSeverity.CRITICAL,
            details=details,
        )


class CitationError(BaseValidatorException):
    """Raised when citation validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CITATION_ERROR",
            severity=ErrorSeverity.HIGH,
            details=details,
        )


class SchemaError(BaseValidatorException):
    """Raised when schema validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="SCHEMA_ERROR",
            severity=ErrorSeverity.HIGH,
            details=details,
        )


class DatabaseError(BaseValidatorException):
    """Raised when database operation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            severity=ErrorSeverity.CRITICAL,
            details=details,
        )


class LLMError(BaseValidatorException):
    """Raised when LLM service fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            severity=ErrorSeverity.MEDIUM,
            details=details,
        )


class AuthenticationError(BaseValidatorException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            severity=ErrorSeverity.HIGH,
        )


class AuthorizationError(BaseValidatorException):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            severity=ErrorSeverity.HIGH,
        )


class RateLimitError(BaseValidatorException):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            severity=ErrorSeverity.MEDIUM,
        )


class ServiceUnavailableError(BaseValidatorException):
    """Raised when a required service is unavailable."""

    def __init__(self, message: str, service_name: str):
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            severity=ErrorSeverity.CRITICAL,
            details={"service_name": service_name},
        )


# ============================================
# Error Handlers
# ============================================

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for all unhandled exceptions."""

    error_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    # Log the error
    logger.error(
        f"Unhandled exception: {str(exc)}",
        extra={
            "error_id": error_id,
            "path": request.url.path,
            "method": request.method,
            "client_ip": request.client.host if request.client else None,
        },
        exc_info=True,
    )

    # Determine status code
    if isinstance(exc, BaseValidatorException):
        status_code = _get_status_code_for_exception(exc)
        error_response = exc.to_dict()
    elif isinstance(exc, PydanticValidationError):
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        error_response = {
            "error_id": error_id,
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "severity": ErrorSeverity.HIGH.value,
            "timestamp": timestamp.isoformat(),
            "details": {
                "errors": [
                    {
                        "field": ".".join(str(err["loc"]) for err in errs),
                        "message": err["msg"],
                        "type": err["type"],
                    }
                    for err in exc.errors()
                ]
            },
        }
    else:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_response = {
            "error_id": error_id,
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred" if config.is_production else str(exc),
            "severity": ErrorSeverity.CRITICAL.value,
            "timestamp": timestamp.isoformat(),
            "details": {},
        }

    return JSONResponse(
        status_code=status_code,
        content={
            "error": error_response,
            "meta": {
                "request_id": request.headers.get("X-Request-ID", error_id),
                "timestamp": timestamp.isoformat(),
            },
        },
    )


async def validation_exception_handler(
    request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle validation errors specifically."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": exc.to_dict(),
            "meta": {
                "request_id": request.headers.get("X-Request-ID"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def grounding_error_handler(
    request: Request, exc: GroundingError
) -> JSONResponse:
    """Handle grounding errors."""
    logger.error(
        f"Grounding error: {exc.message}",
        extra={"error_id": exc.error_id, "details": exc.details},
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "meta": {
                "request_id": request.headers.get("X-Request-ID"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


async def citation_error_handler(
    request: Request, exc: CitationError
) -> JSONResponse:
    """Handle citation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.to_dict(),
            "meta": {
                "request_id": request.headers.get("X-Request-ID"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    )


def _get_status_code_for_exception(exc: BaseValidatorException) -> int:
    """Map exception type to HTTP status code."""
    if isinstance(exc, AuthenticationError):
        return status.HTTP_401_UNAUTHORIZED
    elif isinstance(exc, AuthorizationError):
        return status.HTTP_403_FORBIDDEN
    elif isinstance(exc, ValidationError):
        return status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, RateLimitError):
        return status.HTTP_429_TOO_MANY_REQUESTS
    elif isinstance(exc, ServiceUnavailableError):
        return status.HTTP_503_SERVICE_UNAVAILABLE
    elif isinstance(exc, (GroundingError, CitationError, SchemaError)):
        return status.HTTP_400_BAD_REQUEST
    else:
        return status.HTTP_500_INTERNAL_SERVER_ERROR


# ============================================
# Audit Logging
# ============================================

class AuditLogger:
    """Structured audit logger for compliance and monitoring."""

    def __init__(self):
        self.logger = logging.getLogger("audit")

    def log_validation(
        self,
        explanation_id: str,
        case_id: str,
        user_id: Optional[str],
        validation_result: Dict[str, Any],
        duration_ms: float,
    ) -> None:
        """Log validation event for audit trail."""
        self.logger.info(
            "Validation completed",
            extra={
                "audit_event": "validation_completed",
                "explanation_id": explanation_id,
                "case_id": case_id,
                "user_id": user_id,
                "result": validation_result,
                "duration_ms": duration_ms,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def log_grounding_check(
        self,
        explanation_id: str,
        grounding_score: float,
        ungrounded_claims: int,
        masked: bool,
        user_id: Optional[str],
    ) -> None:
        """Log grounding check event."""
        self.logger.info(
            "Grounding check completed",
            extra={
                "audit_event": "grounding_check",
                "explanation_id": explanation_id,
                "grounding_score": grounding_score,
                "ungrounded_claims": ungrounded_claims,
                "masked": masked,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def log_citation_validation(
        self,
        explanation_id: str,
        total_citations: int,
        valid_citations: int,
        invalid_citations: int,
        user_id: Optional[str],
    ) -> None:
        """Log citation validation event."""
        self.logger.info(
            "Citation validation completed",
            extra={
                "audit_event": "citation_validation",
                "explanation_id": explanation_id,
                "total_citations": total_citations,
                "valid_citations": valid_citations,
                "invalid_citations": invalid_citations,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    def log_error(
        self,
        error: Exception,
        context: Dict[str, Any],
        user_id: Optional[str] = None,
    ) -> None:
        """Log error for audit trail."""
        self.logger.error(
            f"Error occurred: {str(error)}",
            extra={
                "audit_event": "error",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "traceback": traceback.format_exc(),
            },
            exc_info=True,
        )


# Global audit logger instance
audit_logger = AuditLogger()