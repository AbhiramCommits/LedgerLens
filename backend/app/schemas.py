import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ImportStatus


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    institution: str | None = Field(default=None, max_length=255)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    institution: str | None
    currency: str


class RowError(BaseModel):
    row_number: int
    reason: str


class ImportResponse(BaseModel):
    batch_id: uuid.UUID
    inserted: int
    skipped: int
    errors: list[RowError]


class ImportBatchStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    row_count: int
    status: ImportStatus
    created_at: datetime
