from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class CategoryCreateRequest(BaseModel):
    """
    Create a directory category. `parent_id` is optional; a root category has
    none. `slug` is the stable, URL-safe identifier and must be unique.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    parent_id: Optional[int] = None
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True


class CategoryUpdateRequest(BaseModel):
    """
    Partial update. Only supplied fields change; an explicitly supplied null
    clears the field (which is how a category is turned back into a root by
    clearing parent_id). Omitted fields stay untouched.
    """
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=200)
    parent_id: Optional[int] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
