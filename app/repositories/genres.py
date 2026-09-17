from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Genre


class GenreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> Sequence[Genre]:
        result = await self._session.execute(select(Genre).order_by(Genre.id))
        return result.scalars().all()

    async def get(self, genre_id: int) -> Genre | None:
        return await self._session.get(Genre, genre_id)

    async def add(self, **fields: Any) -> Genre:
        genre = Genre(**fields)
        self._session.add(genre)
        await self._session.commit()
        await self._session.refresh(genre)
        return genre

    async def update(self, genre_id: int, **fields: Any) -> Genre | None:
        genre = await self.get(genre_id)
        if genre is None:
            return None
        for key, value in fields.items():
            setattr(genre, key, value)
        await self._session.commit()
        await self._session.refresh(genre)
        return genre