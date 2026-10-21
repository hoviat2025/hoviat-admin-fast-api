from pydantic import BaseModel, ConfigDict, Field, field_validator


class CityCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=150)
    aliases: list[str] = Field(default_factory=list, max_length=30)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError("City name cannot be blank")
        return value

    @field_validator("aliases")
    @classmethod
    def valid_aliases(cls, values):
        if any(not value.strip() or len(value) > 150 for value in values):
            raise ValueError("Aliases must be nonempty and at most 150 characters")
        return values
