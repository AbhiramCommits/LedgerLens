import time
from collections.abc import AsyncGenerator, AsyncIterator

import pytest_asyncio
from fakes import FakeCategorizer
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app import models  # noqa: F401
from app.config import settings
from app.db import Base
from app.deps import get_categorizer, get_session
from app.main import app

TEST_DB_NAME = "ledgerlens_test"

_TRUNCATE = text(
    "TRUNCATE TABLE import_batches, transactions, category_overrides, accounts, users "
    "RESTART IDENTITY CASCADE"
)


def _database_url(database: str) -> str:
    return make_url(settings.database_url).set(database=database).render_as_string(
        hide_password=False
    )


async def _wait_for_database(engine: AsyncEngine, attempts: int = 30) -> None:
    for _ in range(attempts):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("database not reachable")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _test_database() -> AsyncIterator[None]:
    admin_engine = create_async_engine(
        _database_url("postgres"), isolation_level="AUTOCOMMIT"
    )
    await _wait_for_database(admin_engine)
    async with admin_engine.connect() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_NAME}
        )
        if not exists:
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
    await admin_engine.dispose()

    engine = create_async_engine(_database_url(TEST_DB_NAME), poolclass=NullPool)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(_test_database: None) -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(_database_url(TEST_DB_NAME), poolclass=NullPool)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.execute(_TRUNCATE)
    await engine.dispose()


@pytest_asyncio.fixture
async def fake_categorizer() -> AsyncIterator[FakeCategorizer]:
    fake = FakeCategorizer()
    app.dependency_overrides[get_categorizer] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_categorizer, None)


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession, fake_categorizer: FakeCategorizer
) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_session, None)
