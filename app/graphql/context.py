import strawberry
from sqlalchemy.ext.asyncio import AsyncSession


def get_session(info: strawberry.Info) -> AsyncSession:
    return info.context["session"]