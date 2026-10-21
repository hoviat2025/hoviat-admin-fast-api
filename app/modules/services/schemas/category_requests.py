from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator


class CategoryCreateRequest(BaseModel):
    """
    Create a root or a child of one or more roots. parent_id selects the primary
    root; parent_ids is the complete membership list. level is inferred when
    omitted. Slug is the stable unique identifier.
    """
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=200)
    parent_id: Optional[PositiveInt] = None
    parent_ids: Optional[list[PositiveInt]] = None
    level: Optional[Literal[1, 2]] = None
    description: Optional[str] = None
    display_order: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def reject_null_hierarchy(self):
        for field in ("parent_ids", "level"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class CategoryUpdateRequest(BaseModel):
    """
    Partial update. Omitted hierarchy fields preserve memberships. parent_ids
    replaces the full set; parent_id chooses its primary root. A legacy
    parent_id-only update selects that sole parent, or becomes a root when null.
    """
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=200)
    parent_id: Optional[PositiveInt] = None
    parent_ids: Optional[list[PositiveInt]] = None
    level: Optional[Literal[1, 2]] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for field in ("name", "slug", "display_order", "is_active", "parent_ids", "level"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self
