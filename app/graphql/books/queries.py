import strawberry

from app.graphql.books.types import BookType
from app.graphql.context import get_session
from app.repositories import BookRepository
from app.schemas import BookFilters


@strawberry.type
class BookQuery:
    @strawberry.field
    async def books(
        self,
        info: strawberry.Info,
        title: str | None = None,
        year: int | None = None,
        author_id: int | None = None,
        genre_id: int | None = None,
    ) -> list[BookType]:
        repo = BookRepository(get_session(info))
        rows = await repo.get_all(
            BookFilters(
                title=title,
                year=year,
                author_id=author_id,
                genre_id=genre_id,
            )
        )
        return [BookType.from_model(book) for book in rows]

    @strawberry.field
    async def book(self, info: strawberry.Info, id: int) -> BookType | None:
        repo = BookRepository(get_session(info))
        book = await repo.get(id)
        return BookType.from_model(book)
