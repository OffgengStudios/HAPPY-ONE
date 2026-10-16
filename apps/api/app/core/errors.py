from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": {},
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        headers={"Cache-Control": "no-store"},
    )


def register_errors(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def conflict(request: Request, exception: IntegrityError) -> JSONResponse:
        return error_response(
            request, 409, "RECORD_CONFLICT", "This record conflicts with an existing record."
        )

    @app.exception_handler(ApiError)
    async def api_error(request: Request, exception: ApiError) -> JSONResponse:
        return error_response(request, exception.status, exception.code, exception.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exception: RequestValidationError) -> JSONResponse:
        # Never echo submitted passwords, tokens, or sensitive input in errors.
        return error_response(request, 422, "VALIDATION_ERROR", "Check the submitted fields.")
