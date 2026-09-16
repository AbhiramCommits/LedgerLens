from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.categorize.llm import AnthropicCategorizerClient, CategorizerClient
from app.db import SessionLocal
from app.models import User
from app.security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


@lru_cache(maxsize=1)
def get_categorizer() -> CategorizerClient:
    return AnthropicCategorizerClient()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None:
        raise _unauthorized("not authenticated")

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthorized("invalid or expired token")

    user = await session.get(User, user_id)
    if user is None:
        raise _unauthorized("user not found")

    return user
