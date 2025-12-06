from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException # <--- NEEDED FOR AUTH ERRORS
from sqlalchemy.exc import IntegrityError

# 1. Custom Exception
class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code

# 2. The Logic
async def global_exception_handler(request: Request, exc: Exception):
    error_code = "INTERNAL_SERVER_ERROR"
    message = str(exc)
    status_code = 500
    
    if isinstance(exc, ServiceError):
        error_code = exc.code
        message = exc.message
        status_code = exc.status_code

    # --- THIS WAS MISSING ---
    # Catches the 401/403 errors from your Auth dependencies
    elif isinstance(exc, StarletteHTTPException):
        if exc.status_code == 404:
            error_code = "NOT_FOUND"
        elif exc.status_code == 401:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            error_code = "FORBIDDEN"
        else:
            error_code = "HTTP_ERROR"
            
        # Use the detail provided in the raise HTTPException(...)
        message = exc.detail 
        status_code = exc.status_code
    # ------------------------
        
    elif isinstance(exc, IntegrityError):
        error_code = "CONFLICT_OCCURRED"
        # Keep this as you requested to see exact DB error
        message = str(exc.orig) if exc.orig else "Database constraint violation"
        status_code = status.HTTP_409_CONFLICT
        
    elif isinstance(exc, RequestValidationError):
        error_code = "INVALID_INPUT"
        message = "Invalid parameters" # Keeping this exact as per your request
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY

    return JSONResponse(
        status_code=status_code,
        content={
            "data": {},
            "meta": {},
            "error": {"code": error_code, "message": message}
        }
    )

# 3. The Registrar
def register_exception_handlers(app: FastAPI):
    app.add_exception_handler(ServiceError, global_exception_handler)
    app.add_exception_handler(IntegrityError, global_exception_handler)
    app.add_exception_handler(RequestValidationError, global_exception_handler)
    app.add_exception_handler(StarletteHTTPException, global_exception_handler) # <--- ADD THIS
    app.add_exception_handler(Exception, global_exception_handler)