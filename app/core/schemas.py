from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, Dict, Any # Added Dict, Any for explicit type hinting

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str

class StandardResponse(BaseModel, Generic[T]):
    """
    Standard API response wrapper for consistent output format.
    {
        "data": { ... },
        "meta": {},
        "error": {} 
    }
    """
    data: Optional[T] = Field(default=None)
    # Explicitly provide an empty dict as an example for Swagger UI to prevent "additionalProp1"
    meta: Dict[str, Any] = Field(default_factory=dict, json_schema_extra={"example": {}})
    # For error, if it's an empty dict, ensure Swagger UI shows "{}"
    error: Dict[str, Any] | ErrorDetail = Field(default_factory=dict, json_schema_extra={"example": {}})

    @classmethod
    def success(cls, data: T, meta: dict = None):
        """
        Factory method for creating a successful response.
        """
        return cls(data=data, meta=meta or {}, error={})

    @classmethod
    def failure(cls, error_detail: ErrorDetail, meta: dict = None):
        """
        Factory method for creating an error response.
        """
        return cls(data=None, meta=meta or {}, error=error_detail)