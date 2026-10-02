from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    parent_id: Optional[int] = None
    name: str
    slug: str
    description: Optional[str] = None
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CategoryTreeResponse(CategoryResponse):
    """A category together with its direct children, for admin tree views."""
    children: List["CategoryTreeResponse"] = []


CategoryTreeResponse.model_rebuild()


class CategorySummaryResponse(BaseModel):
    """Just enough category to render a label or a chip."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
