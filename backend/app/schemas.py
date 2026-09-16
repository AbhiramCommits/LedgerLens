import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.categorize.taxonomy import Category
from app.models import CategorySource, ImportStatus


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


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    posted_date: date
    description: str | None
    merchant_raw: str
    amount: Decimal
    category: str | None
    category_source: CategorySource | None
    confidence: float | None
    created_at: datetime


class TransactionCategoryUpdate(BaseModel):
    category: Category


class CategorizeResponse(BaseModel):
    categorized: int
    by_source: dict[str, int]
    fallback_reasons: list[str]
    transactions: list[TransactionRead]


class CategoryTotal(BaseModel):
    category: str
    total: Decimal
    count: int


class ByCategoryResponse(BaseModel):
    month: str
    totals: list[CategoryTotal]


class MonthTotal(BaseModel):
    month: str
    total: Decimal
    income: Decimal
    expenses: Decimal
    count: int


class MonthlyTrendResponse(BaseModel):
    months: list[MonthTotal]
