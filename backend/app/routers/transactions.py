import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.llm import CategorizerClient
from app.categorize.pipeline import run_categorization
from app.categorize.taxonomy import Category
from app.deps import get_categorizer, get_current_user, get_session
from app.models import Account, CategoryOverride, CategorySource, Transaction, User
from app.schemas import (
    CategorizeResponse,
    TransactionCategoryUpdate,
    TransactionPage,
    TransactionRead,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionPage)
async def list_transactions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: str = Query(
        default="posted_date",
        pattern=r"^(posted_date|merchant_raw|amount|category)$",
    ),
    sort_order: str = Query(default="desc", pattern=r"^(asc|desc)$"),
    category: Category | None = Query(default=None),
    max_confidence: float | None = Query(default=None, ge=0.0, le=1.0),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TransactionPage:
    conditions = [Account.user_id == user.id]
    if category is not None:
        conditions.append(Transaction.category == category.value)
    if max_confidence is not None:
        conditions.append(
            or_(Transaction.confidence.is_(None), Transaction.confidence <= max_confidence)
        )

    total = await session.scalar(
        select(func.count())
        .select_from(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .where(*conditions)
    )

    column = _sort_column(sort_by)
    order_column = column.asc() if sort_order == "asc" else column.desc()
    items = (
        await session.scalars(
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(*conditions)
            .order_by(order_column, Transaction.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    return TransactionPage(
        items=cast(list[TransactionRead], list(items)),
        total=total or 0,
        page=page,
        page_size=page_size,
    )


@router.post("/categorize", response_model=CategorizeResponse)
async def categorize_transactions(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    client: CategorizerClient = Depends(get_categorizer),
) -> CategorizeResponse:
    result = await run_categorization(session, user.id, client)
    return CategorizeResponse(
        categorized=result.categorized,
        by_source=result.by_source,
        fallback_reasons=result.fallback_reasons,
        transactions=cast(list[TransactionRead], result.transactions),
    )


@router.patch("/{transaction_id}", response_model=TransactionRead)
async def update_transaction_category(
    transaction_id: uuid.UUID,
    body: TransactionCategoryUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Transaction:
    result = await session.scalars(
        select(Transaction)
        .join(Account, Transaction.account_id == Account.id)
        .where(Transaction.id == transaction_id, Account.user_id == user.id)
    )
    transaction = result.first()
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="transaction not found")

    transaction.category = body.category.value
    transaction.category_source = CategorySource.user
    transaction.confidence = 1.0

    if transaction.merchant_raw:
        stmt = (
            pg_insert(CategoryOverride)
            .values(
                user_id=user.id,
                merchant_pattern=transaction.merchant_raw,
                category=body.category.value,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "merchant_pattern"],
                set_={"category": body.category.value},
            )
        )
        await session.execute(stmt)

    await session.commit()
    await session.refresh(transaction)
    return transaction


def _sort_column(name: str) -> Any:
    if name == "merchant_raw":
        return Transaction.merchant_raw
    if name == "amount":
        return Transaction.amount
    if name == "category":
        return Transaction.category
    return Transaction.posted_date
