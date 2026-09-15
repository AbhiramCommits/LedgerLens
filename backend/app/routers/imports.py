import uuid
from collections.abc import Iterator
from pathlib import PurePath
from typing import Any, cast

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_session
from app.ingest.parser import ColumnMappingError, ParsedRow, ParseResult, parse_csv
from app.models import Account, ImportBatch, ImportStatus, Transaction, User
from app.schemas import ImportBatchStatus, ImportResponse, RowError

router = APIRouter(prefix="/imports", tags=["imports"])

_INSERT_CHUNK_SIZE = 2000


@router.post("", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
async def import_transactions(
    account_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ImportResponse:
    account_result = await session.scalars(
        select(Account).where(Account.id == account_id, Account.user_id == user.id)
    )
    account = account_result.first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")

    data = await file.read()
    filename = PurePath(file.filename or "upload.csv").name

    batch = ImportBatch(
        user_id=user.id,
        filename=filename,
        row_count=0,
        status=ImportStatus.processing,
    )
    session.add(batch)
    await session.commit()
    await session.refresh(batch)

    try:
        parsed: ParseResult = parse_csv(data)
    except ColumnMappingError as exc:
        batch.status = ImportStatus.failed
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None

    try:
        values = [_transaction_values(account.id, row) for row in parsed.rows]
        inserted = 0
        for chunk in _chunks(values, _INSERT_CHUNK_SIZE):
            stmt = (
                pg_insert(Transaction)
                .values(chunk)
                .on_conflict_do_nothing(
                    index_elements=["account_id", "posted_date", "amount", "merchant_raw"]
                )
            )
            outcome = cast(CursorResult[Any], await session.execute(stmt))
            inserted += outcome.rowcount or 0
        skipped = len(values) - inserted

        batch.row_count = len(values) + len(parsed.errors)
        batch.status = ImportStatus.complete
        await session.commit()
    except Exception:
        batch.status = ImportStatus.failed
        await session.commit()
        raise

    return ImportResponse(
        batch_id=batch.id,
        inserted=inserted,
        skipped=skipped,
        errors=[RowError(row_number=e.row_number, reason=e.reason) for e in parsed.errors],
    )


@router.get("/{batch_id}", response_model=ImportBatchStatus)
async def get_import_batch(
    batch_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ImportBatch:
    batch = await session.get(ImportBatch, batch_id)
    if batch is None or batch.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="import batch not found")
    return batch


def _transaction_values(account_id: uuid.UUID, row: ParsedRow) -> dict[str, object]:
    return {
        "account_id": account_id,
        "posted_date": row.posted_date,
        "description": row.description,
        "merchant_raw": row.merchant_raw,
        "amount": row.amount,
    }


def _chunks(values: list[dict[str, object]], size: int) -> Iterator[list[dict[str, object]]]:
    for start in range(0, len(values), size):
        yield values[start : start + size]
