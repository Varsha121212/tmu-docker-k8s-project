from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Common error envelope per SDD 7.6: timestamp, status, code, message, path, correlation_id.


def _envelope(request: Request, status_code: int, code: str, message: str) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status_code,
        "code": code,
        "message": message,
        "path": request.url.path,
        "correlation_id": getattr(request.state, "correlation_id", None),
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = getattr(exc, "code", None) or f"HTTP_{exc.status_code}"
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(request, exc.status_code, code, str(exc.detail)),
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                request,
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "VALIDATION_ERROR",
                "Request validation failed",
            ),
        )
