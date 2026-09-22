from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker, Session

from app.config import settings


def make_engine():
    return create_async_engine(settings.database_url, echo=True)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def make_sync_engine():
    return create_engine(settings.database_url_sync, echo=True)


def make_sync_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
