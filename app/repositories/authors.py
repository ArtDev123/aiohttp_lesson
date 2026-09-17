from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Author


class AuthorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Author]:
        result = await self._session.execute(select(Author).order_by(Author.id))
        return result.scalars().all()

    async def get(self, author_id: int) -> Author | None:
        return await self._session.get(Author, author_id)

    async def add(self, **fields: Any) -> Author:
        author = Author(**fields)
        self._session.add(author)
        await self._session.commit()
        await self._session.refresh(author)
        return author

    async def update(self, author_id: int, **fields: Any) -> Author | None:
        author = await self.get(author_id)
        if author is None:
            return None
        for key, value in fields.items():
            setattr(author, key, value)
        await self._session.commit()
        await self._session.refresh(author)
        return author