from pydantic import BaseModel, ConfigDict, Field

from app.models import Book


class ErrorRead(BaseModel):
    error: str


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class GenreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str | None


class AuthorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    bio: str | None = None


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int = Field(ge=1)
    genre_id: int = Field(ge=1)


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int | None = Field(default=None, ge=1)
    genre_id: int | None = Field(default=None, ge=1)


class BookRead(BaseModel):
    id: int
    title: str
    year: int | None
    author_id: int
    genre_id: int
    author: str
    genre: str

    @classmethod
    def from_book(cls, book: Book) -> "BookRead":
        return cls(
            id=book.id,
            title=book.title,
            year=book.year,
            author_id=book.author_id,
            genre_id=book.genre_id,
            author=book.author.name,
            genre=book.genre.name,
        )


class BookFilters(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="Подстрока в названии, без учёта регистра",
    )
    year: int | None = Field(
        default=None,
        ge=1,
        le=2100,
        description="Точный год издания",
    )
    author_id: int | None = Field(default=None, ge=1)
    genre_id: int | None = Field(default=None, ge=1)
