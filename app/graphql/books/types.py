import strawberry

from app.graphql.authors.types import AuthorType
from app.graphql.genres.types import GenreType
from app.models import Book


@strawberry.type(name="Book")
class BookType:
    id: int
    title: str
    year: int | None
    author: AuthorType
    genre: GenreType

    @classmethod
    def from_model(cls, book: Book) -> "BookType":
        return cls(
            id=book.id,
            title=book.title,
            year=book.year,
            author=AuthorType.from_model(book.author),
            genre=GenreType.from_model(book.genre),
        )
