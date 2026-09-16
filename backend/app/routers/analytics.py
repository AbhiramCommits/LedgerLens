from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.taxonomy import Category
from app.deps import get_current_user, get_session
from app.models import Account, Transaction, User
from app.schemas import ByCategoryResponse, CategoryTotal, MonthlyTrendResponse, MonthTotal

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/by-category", response_model=ByCategoryResponse)
async def totals_by_category(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ByCategoryResponse:
    year, month_number = _split_month(month)
    start = date(year, month_number, 1)
    end = _next_month(year, month_number)

    rows = (
        await session.execute(
            select(
                Transaction.category,
                func.sum(Transaction.amount),
                func.count(),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user.id,
                Transaction.posted_date >= start,
                Transaction.posted_date < end,
                Transaction.category.is_not(None),
            )
            .group_by(Transaction.category)
        )
    ).all()

    sums: dict[Category, Decimal] = {category: Decimal("0") for category in Category}
    counts: dict[Category, int] = {category: 0 for category in Category}
    for row in rows:
        try:
            category = Category(str(row[0]))
        except ValueError:
            continue
        sums[category] += Decimal(row[1] or 0)
        counts[category] += int(row[2] or 0)

    totals = [
        CategoryTotal(category=category.value, total=sums[category], count=counts[category])
        for category in Category
    ]
    totals.sort(key=lambda item: (-item.total, item.category))
    return ByCategoryResponse(month=month, totals=totals)


@router.get("/monthly-trend", response_model=MonthlyTrendResponse)
async def monthly_trend(
    months: int = Query(default=6, ge=1, le=24),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> MonthlyTrendResponse:
    month_keys, start, end = _trend_window(months)
    month_trunc = func.date_trunc(text("'month'"), Transaction.posted_date)

    rows = (
        await session.execute(
            select(
                month_trunc,
                func.sum(Transaction.amount),
                func.count(),
                func.sum(
                    case(
                        (Transaction.category == Category.income.value, Transaction.amount),
                        else_=Decimal("0"),
                    )
                ),
            )
            .join(Account, Transaction.account_id == Account.id)
            .where(
                Account.user_id == user.id,
                Transaction.posted_date >= start,
                Transaction.posted_date < end,
            )
            .group_by(month_trunc)
        )
    ).all()

    sums: dict[tuple[int, int], Decimal] = {}
    counts: dict[tuple[int, int], int] = {}
    incomes: dict[tuple[int, int], Decimal] = {}
    for row in rows:
        month_date = row[0]
        key = (month_date.year, month_date.month)
        sums[key] = Decimal(row[1] or 0)
        counts[key] = int(row[2] or 0)
        incomes[key] = Decimal(row[3] or 0)

    entries: list[MonthTotal] = []
    for year, month_number in month_keys:
        key = (year, month_number)
        total = sums.get(key, Decimal("0"))
        income = incomes.get(key, Decimal("0"))
        entries.append(
            MonthTotal(
                month=f"{year:04d}-{month_number:02d}",
                total=total,
                income=income,
                expenses=total - income,
                count=counts.get(key, 0),
            )
        )
    return MonthlyTrendResponse(months=entries)


def _split_month(value: str) -> tuple[int, int]:
    year, month_number = (int(part) for part in value.split("-"))
    if not 1 <= month_number <= 12:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"invalid month: {value}"
        )
    return year, month_number


def _next_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _trend_window(months: int) -> tuple[list[tuple[int, int]], date, date]:
    today = date.today()
    keys: list[tuple[int, int]] = []
    for offset in range(months - 1, -1, -1):
        total = today.year * 12 + (today.month - 1) - offset
        year, month_zero = divmod(total, 12)
        keys.append((year, month_zero + 1))
    start = date(keys[0][0], keys[0][1], 1)
    last_year, last_month = keys[-1]
    end = _next_month(last_year, last_month)
    return keys, start, end
