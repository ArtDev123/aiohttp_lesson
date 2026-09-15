from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.models import Book


class ErrorRead(BaseModel):
    error: str


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class GenreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class AuthorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str | None = None


class AuthorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bio: str | None


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    year: int | None = Field(default=None, ge=1, le=2100)
    author_id: int = Field(ge=1)
    genre_id: int = Field(ge=1)


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


def parse_body(model_cls, data: dict):
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise web.HTTPUnprocessableEntity(
            text=exc.json(),
            content_type="application/json",
        ) from exc
