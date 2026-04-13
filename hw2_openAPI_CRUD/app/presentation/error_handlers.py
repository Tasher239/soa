from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.domain.exceptions import DomainException
from generated.models import ErrorResponse


async def domain_exception_handler(request: Request, exc: DomainException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=ErrorResponse(
            error_code=exc.error_code,
            message=exc.message,
            details=exc.details,
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors = []
    for error in exc.errors():
        loc = error.get("loc", [])
        field_path = ".".join(str(part) for part in loc if part != "body")
        field_errors.append(
            {
                "field": field_path,
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error_code="VALIDATION_ERROR",
            message="Request validation failed",
            details={"fields": field_errors},
        ).model_dump(),
    )
