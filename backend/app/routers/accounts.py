from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_session
from app.models import Account, User
from app.schemas import AccountCreate, AccountRead

router = APIRouter(prefix="/accounts", tags=["accounts"])


@router.post("", response_model=AccountRead, status_code=status.HTTP_201_CREATED)
async def create_account(
    body: AccountCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Account:
    account = Account(
        user_id=user.id,
        name=body.name,
        institution=body.institution,
        currency=body.currency.upper(),
    )
    session.add(account)
    await session.commit()
    await session.refresh(account)
    return account


@router.get("", response_model=list[AccountRead])
async def list_accounts(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[Account]:
    result = await session.scalars(
        select(Account).where(Account.user_id == user.id).order_by(Account.id)
    )
    return list(result)
