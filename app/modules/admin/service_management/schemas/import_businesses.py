"""Small browser-submitted batches, never a background file import."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.service import ServiceStatus
from app.modules.services.schemas.service_requests import ServiceCreateRequest


class CategoryDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    primary_parent_key: str | None = None
    parent_keys: list[str] = Field(default_factory=list, max_length=30)
    reason: str | None = None


class ImportAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_key: str = Field(min_length=1, max_length=200)
    is_primary: bool = False


class BusinessImportRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    service: ServiceCreateRequest
    description_original: str | None = None
    google_maps_url: str | None = Field(default=None, max_length=4096)
    category_assignments: list[ImportAssignment] = Field(min_length=1, max_length=30)
    metadata: dict
    # Only the exact source posts needed by this record/context travel with it.
    sources: list[dict] = Field(min_length=1, max_length=50)
    expected_updated_at: datetime | None = None

    @model_validator(mode="after")
    def stable_identity(self):
        if self.service.source != "telegram" or not self.service.external_id:
            raise ValueError("Import requires a known Telegram source and external_id; fix unmatched sources first")
        if self.service.owner_user_id is not None:
            raise ValueError("Imported owner accounts must be assigned separately")
        if self.service.categories:
            raise ValueError("Use category_assignments with catalogue keys")
        keys = [a.category_key.lower() for a in self.category_assignments]
        if len(set(keys)) != len(keys) or sum(a.is_primary for a in self.category_assignments) != 1:
            raise ValueError("Use unique leaf categories and exactly one primary")
        ref = self.metadata.get("source_ref")
        context = self.metadata.get("batch_context") or {}
        if not isinstance(ref, str) or not isinstance(context, dict) or not isinstance(context.get("source_refs", []), list):
            raise ValueError("Source references and batch context must use the extraction format")
        sources = {s.get("source_ref"): s for s in self.sources}
        if len(sources) != len(self.sources) or any(not isinstance(key, str) for key in sources):
            raise ValueError("Each source needs a unique source_ref")
        if ref not in sources or not all(isinstance(s.get("raw_text"), str) for s in self.sources):
            raise ValueError("The record needs its original source text")
        if any(not isinstance(r, str) or r not in sources for r in context.get("source_refs", [])):
            raise ValueError("A batch-context source is missing")
        source = sources[ref]
        channel = source.get("channel_id") or source.get("channel_username")
        message = source.get("message_id")
        index = self.metadata.get("source_item_index")
        if channel is None or message is None or index is None:
            raise ValueError("Source identifiers must be resolved before import")
        identity = f"{str(channel).lower()}:{message}:{index}"
        subindex = self.metadata.get("source_subitem_index")
        if subindex is not None:
            identity += f":{subindex}"
        if self.service.external_id != identity:
            raise ValueError("external_id does not match its source metadata")
        return self


class BusinessImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["add", "update"] = "add"
    preview: bool = True
    status: ServiceStatus = ServiceStatus.published
    definitions: list[CategoryDefinition] = Field(default_factory=list, max_length=250)
    rows: list[BusinessImportRow] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_definitions(self):
        keys = [d.key.lower() for d in self.definitions]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate category definition keys")
        identities = [r.service.external_id for r in self.rows]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate entries within this batch")
        return self
