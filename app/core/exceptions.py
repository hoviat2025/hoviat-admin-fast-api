from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import IntegrityError

class ServiceError(Exception):
    """
    Base exception for application-specific business logic errors.
    
    Attributes:
        code: A short string identifier for the error (e.g., 'INSUFFICIENT_FUNDS').
        message: A descriptive error message for the client.
        status_code: The HTTP status code to return.
    """
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global catch-all for exceptions to ensure a unified JSON response format.
    Maps internal exceptions to the standard API error schema.
    """
    # Default values for unhandled/generic exceptions
    error_code = "INTERNAL_SERVER_ERROR"
    message = str(exc)
    status_code = 500
    
    # Custom business logic errors
    if isinstance(exc, ServiceError):
        error_code = exc.code
        message = exc.message
        status_code = exc.status_code

    # Standard FastAPI/Starlette HTTP errors (401, 403, 404, etc.)
    elif isinstance(exc, StarletteHTTPException):
        status_code = exc.status_code
        message = exc.detail
        
        # Map common status codes to semantic error strings
        error_mapping = {
            404: "NOT_FOUND",
            401: "UNAUTHORIZED",
            403: "FORBIDDEN",
            429: "RATE_LIMITED"
        }
        error_code = error_mapping.get(exc.status_code, "HTTP_ERROR")
        
    # Database integrity violations (e.g., unique constraint failures)
    elif isinstance(exc, IntegrityError):
        error_code = "CONFLICT_OCCURRED"
        # Extract the underlying DB error message if available
        message = str(exc.orig) if exc.orig else "Database constraint violation"
        status_code = status.HTTP_409_CONFLICT
        
    # Pydantic validation errors (invalid request body or parameters)
    elif isinstance(exc, RequestValidationError):
        error_code = "INVALID_INPUT"
        message = "Invalid parameters provided in the request"
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content={
            "data": {},
            "meta": {},
            "error": {
                "code": error_code, 
                "message": message
            }
        }
    )

def register_exception_handlers(app: FastAPI):
    """
    Attaches standardized exception handlers to the FastAPI application.
    Handlers are evaluated in order; generic 'Exception' should be registered last.
    """
    app.add_exception_handler(ServiceError, global_exception_handler)
    app.add_exception_handler(IntegrityError, global_exception_handler)
    app.add_exception_handler(RequestValidationError, global_exception_handler)
    app.add_exception_handler(StarletteHTTPException, global_exception_handler)
    app.add_exception_handler(Exception, global_exception_handler)