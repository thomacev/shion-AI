from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
import re
from uuid import UUID

class UserRegisterSchema(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str):
        pattern = r"^[A-Za-zÀ-ÿ\s'-]+$"
        if not re.match(pattern, value):
            raise ValueError("Invalid full name.")
        if len(value) > 64:
            raise ValueError("Your full name must be 64 characters maximum.")
        return value

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str):
        if len(value) < 8:
            raise ValueError("Your password must be at least 8 characters long.")
        if value.isalpha() or value.isdigit():
            raise ValueError("Password must contain both letters and numbers.")
        return value


class UserResponseSchema(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)