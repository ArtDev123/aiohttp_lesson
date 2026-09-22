from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import NotFoundError
from app.models import Book
from app.repositories import BaseRepository
from app.schemas import BookFilters


class BookRepository(BaseRepository[Book]):
    model = Book

    def __init__(self, session: AsyncSession) -> None:
        from app.repositories import AuthorRepository, GenreRepository
        self._session = session
        self._author_repo = AuthorRepository(session)
        self._genre_repo = GenreRepository(session)

    async def _validate_create_update(self, **fields: Any) -> None:
        if "author_id" in fields:
            author_id = cast(int, fields.get("author_id"))
            await self._author_repo.get(author_id)


        if "genre_id" in fields:
            genre_id = fields.get("genre_id")
            await self._genre_repo.get(genre_id)



    def _with_relations(self):
        return select(Book).options(
            selectinload(Book.author),
            selectinload(Book.genre),
        )

    async def get_all(self, filters: BookFilters) -> Sequence[Book]:
        stmt = self._with_relations()
        if filters.title is not None:
            stmt = stmt.where(Book.title.ilike(f"%{filters.title}%"))
        if filters.year is not None:
            stmt = stmt.where(Book.year == filters.year)
        if filters.author_id is not None:
            stmt = stmt.where(Book.author_id == filters.author_id)
        if filters.genre_id is not None:
            stmt = stmt.where(Book.genre_id == filters.genre_id)
        result = await self._session.execute(stmt.order_by(Book.id))
        return result.scalars().all()

    async def get(self, book_id: int) -> Book:
        result = await self._session.execute(
            self._with_relations().where(Book.id == book_id)
        )
        result = result.scalars().first()
        if result is None:
            raise NotFoundError("Book not found")
        return result

    async def add(self, **fields: Any) -> Book:
        await self._validate_create_update(**fields)
        return await super().add(**fields)

    async def update(self, book_id: int, **fields: Any) -> Book:
        await self._validate_create_update(**fields)
        return await super().update(**fields)
