from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, Dict, Any

# Type variable for generic data payloads
T = TypeVar("T")

class ErrorDetail(BaseModel):
    """
    Structured error information for the client.
    """
    code: str = Field(..., description="A unique string identifier for the error type.")
    message: str = Field(..., description="A human-readable explanation of the error.")

class StandardResponse(BaseModel, Generic[T]):
    """
    Unified API response envelope.
    
    Ensures a consistent JSON structure across all endpoints:
    {
        "data": { ... },
        "meta": {},
        "error": {} 
    }
    """
    # The primary response payload
    data: Optional[T] = Field(default=None)
    
    # Auxiliary information (e.g., pagination, rate limits)
    # The json_schema_extra ensures the OpenAPI documentation displays an empty object
    meta: Dict[str, Any] = Field(
        default_factory=dict, 
        json_schema_extra={"example": {}}
    )
    
    # Contains error details if the request failed; otherwise returns an empty object
    error: Dict[str, Any] | ErrorDetail = Field(
        default_factory=dict, 
        json_schema_extra={"example": {}}
    )

    @classmethod
    def success(cls, data: T, meta: dict = None):
        """
        Factory method to generate a successful response envelope.
        """
        return cls(
            data=data, 
            meta=meta or {}, 
            error={}
        )

    @classmethod
    def failure(cls, error_detail: ErrorDetail, meta: dict = None):
        """
        Factory method to generate an error response envelope.
        """
        return cls(
            data=None, 
            meta=meta or {}, 
            error=error_detail
        )