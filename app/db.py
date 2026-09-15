from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import DATABASE_URL


def make_engine():
    # echo=False: в лог SQL не пишем, для урока хватит.
    return create_async_engine(DATABASE_URL, echo=False)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
