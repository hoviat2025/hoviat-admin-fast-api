"""Small browser-submitted batches, never a background file import."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.service import ServiceStatus
from app.modules.services.schemas.service_requests import ServiceCreateRequest
from app.modules.services.validation import normalise_slug
from app.core.exceptions import ServiceError


def canonical_key(value):
    try:
        return normalise_slug(value)
    except ServiceError as exc:
        raise ValueError(exc.message) from exc


class CategoryDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    name: str = Field(min_length=1, max_length=200)
    primary_parent_key: str | None = None
    parent_keys: list[str] = Field(default_factory=list, max_length=30)
    reason: str | None = None

    @field_validator("key", mode="before")
    @classmethod
    def normalise_key(cls, value):
        return canonical_key(value) if isinstance(value, str) else value

    @field_validator("primary_parent_key")
    @classmethod
    def normalise_primary(cls, value):
        return canonical_key(value) if value is not None else value

    @field_validator("parent_keys")
    @classmethod
    def normalise_parents(cls, value):
        return [canonical_key(key) for key in value]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError("Category name cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def hierarchy(self):
        if len(set(self.parent_keys)) != len(self.parent_keys):
            raise ValueError("Duplicate category parents")
        if bool(self.parent_keys) != bool(self.primary_parent_key):
            raise ValueError("Children need parents and a primary parent; groups have neither")
        if self.primary_parent_key and self.primary_parent_key not in self.parent_keys:
            raise ValueError("Primary parent must belong to parent_keys")
        if self.key in self.parent_keys:
            raise ValueError("A category cannot be its own parent")
        return self


def validate_definitions(definitions):
    by_key = {d.key: d for d in definitions}
    if len(by_key) != len(definitions):
        raise ValueError("Duplicate category definition keys")
    for definition in definitions:
        for key in definition.parent_keys:
            if key in by_key and by_key[key].parent_keys:
                raise ValueError("Only first-level groups can be parents; a third level is not allowed")


class CategoryImportBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preview: bool = True
    definitions: list[CategoryDefinition] = Field(min_length=1, max_length=500)
    keys: list[str] = Field(min_length=1, max_length=25)

    @field_validator("keys")
    @classmethod
    def normalise_keys(cls, value):
        return [canonical_key(key) for key in value]

    @model_validator(mode="after")
    def valid_catalogue(self):
        validate_definitions(self.definitions)
        if len(set(self.keys)) != len(self.keys):
            raise ValueError("Duplicate requested category keys")
        if not set(self.keys).issubset({d.key for d in self.definitions}):
            raise ValueError("Every requested category needs a definition")
        return self


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
    definitions: list[CategoryDefinition] = Field(default_factory=list, max_length=500)
    rows: list[BusinessImportRow] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique_definitions(self):
        validate_definitions(self.definitions)
        identities = [r.service.external_id for r in self.rows]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate entries within this batch")
        return self
