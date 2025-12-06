from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional

T = TypeVar("T")

class ErrorDetail(BaseModel):
    code: str
    message: str

class StandardResponse(BaseModel, Generic[T]):
    """
    Matches your legacy format:
    {
        "data": { ... },
        "meta": {},
        "error": {} 
    }
    """
    data: Optional[T] = Field(default=None)
    meta: dict = Field(default_factory=dict)
    # We default to empty dict instead of None to match your legacy example
    error: dict | ErrorDetail = Field(default_factory=dict) 

    @classmethod
    def success(cls, data: T, meta: dict = None):
        return cls(data=data, meta=meta or {}, error={})