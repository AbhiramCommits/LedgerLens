import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.llm import CategorizerClient
from app.categorize.pipeline import run_categorization
from app.deps import get_categorizer, get_current_user, get_session
from app.models import Account, CategoryOverride, CategorySource, Transaction, User
from app.schemas import CategorizeResponse, TransactionCategoryUpdate, TransactionRead

router = APIRouter(prefix="/transactions", tags=["transactions"])


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
