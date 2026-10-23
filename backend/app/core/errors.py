"""One error envelope for the whole API.

Every non-2xx response has the shape:
    {"error": {"code": "TICKET_NOT_FOUND", "message": "...", "details": [...]?, "request_id": "..."}}
so the frontend (and the evaluator) never sees a bare 500 or an unstructured FastAPI default.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class AppError(Exception):
    """Domain error with a stable machine-readable code."""

    status_code = 400
    code = "BAD_REQUEST"

    def __init__(self, message: str, *, details: Any = None, status_code: int | None = None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class ValidationFailed(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class AiUnavailableError(AppError):
    """Raised by the AI layer when the model can't be used right now (down, rate-limited, no key)."""

    status_code = 503
    code = "AI_UNAVAILABLE"


def _envelope(request: Request, *, code: str, message: str, status: int, details: Any = None) -> JSONResponse:
    body: dict[str, Any] = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details is not None:
        body["details"] = details
    return JSONResponse(status_code=status, content={"error": body})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _envelope(request, code=exc.code, message=exc.message, status=exc.status_code, details=exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")),
                "message": e.get("msg"),
            }
            for e in exc.errors()
        ]
        return _envelope(
            request, code="VALIDATION_ERROR", message="Request validation failed.", status=422, details=details
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return _envelope(request, code=code, message=str(exc.detail), status=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled error on %s %s", request.method, request.url.path)
        return _envelope(
            request,
            code="INTERNAL_ERROR",
            message="Something went wrong on our side. Please retry; if it persists, quote the request id.",
            status=500,
        )
