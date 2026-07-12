from pydantic import BaseModel, ConfigDict, field_validator
from uuid import UUID
from datetime import datetime


class AssistantCreateSchema(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str = "You are a helpful assistant."

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Assistant name cannot be empty.")

        if len(value) > 128:
            raise ValueError("Assistant name cannot exceed 128 characters.")

        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None) -> str | None:
        if value is None:
            return value

        value = value.strip()

        if len(value) > 512:
            raise ValueError("Description cannot exceed 512 characters.")

        return value

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("System prompt cannot be empty.")

        return value


class AssistantUpdateSchema(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("Assistant name cannot be empty.")

        if len(value) > 128:
            raise ValueError("Assistant name cannot exceed 128 characters.")

        return value

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        if len(value) > 512:
            raise ValueError("Description cannot exceed 512 characters.")

        return value

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt(cls, value: str | None):
        if value is None:
            return value

        value = value.strip()

        if not value:
            raise ValueError("System prompt cannot be empty.")

        return value


class AssistantResponseSchema(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    description: str | None
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
