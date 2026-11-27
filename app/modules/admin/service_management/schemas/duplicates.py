from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class DuplicateGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    keep_id: int = Field(gt=0)
    remove_ids: list[int] = Field(min_length=1, max_length=19)
    reason: str = Field(min_length=1, max_length=2000)
    confidence: Literal["likely", "possible"] = "likely"
    preview_token: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def unique_members(self):
        ids = [self.keep_id, *self.remove_ids]
        if any(i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("Use distinct positive record IDs in each group")
        return self


class DuplicateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    preview: bool = True
    groups: list[DuplicateGroup] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def no_overlap(self):
        ids = [i for g in self.groups for i in [g.keep_id, *g.remove_ids]]
        if len(set(ids)) != len(ids):
            raise ValueError("A record may belong to only one group")
        return self
