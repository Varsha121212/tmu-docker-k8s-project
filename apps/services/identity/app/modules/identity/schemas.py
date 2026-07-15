import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    # 8 chars is a baseline floor, not a BRD-specified policy - BRD only requires
    # "securely hashed password" (BRULE-02). Revisit if the BRD is amended.
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    created_at: datetime
    active: bool

    model_config = {"from_attributes": True}
