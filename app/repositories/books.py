from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.errors import NotFoundError
from app.models import Book


class BookRepository:
    def __init__(self, session: AsyncSession) -> None:
        from app.repositories import AuthorRepository, GenreRepository
        self._session = session
        self._author_repo = AuthorRepository(session)
        self._genre_repo = GenreRepository(session)

    async def _validate_create_update(self, **fields: Any) -> None:
        if "author_id" in fields:
            author_id = cast(int, fields.get("author_id"))
            author = await self._author_repo.get(author_id)
            if author is None:
                raise NotFoundError("Автор не найден")

        if "genre_id" in fields:
            genre_id = fields.get("genre_id")
            genre = await self._genre_repo.get(genre_id)
            if genre is None:
                raise NotFoundError("Жанр не найден")


    def _with_relations(self):
        return select(Book).options(
            selectinload(Book.author),
            selectinload(Book.genre),
        )

    async def get_all(self) -> Sequence[Book]:
        result = await self._session.execute(self._with_relations().order_by(Book.id))
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
        book = Book(**fields)
        self._session.add(book)
        await self._session.commit()
        created = await self.get(book.id)
        assert created is not None
        return created

    async def update(self, book_id: int, **fields: Any) -> Book:
        book = await self.get(book_id)

        if book is None:
            raise NotFoundError("Book not found")

        await self._validate_create_update(**fields)

        for key, value in fields.items():
            setattr(book, key, value)

        await self._session.commit()

        return await self.get(book.id)