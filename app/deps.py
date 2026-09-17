from typing import Annotated

from fastapi import Depends

from app.db import SessionDep
from app.repositories import AuthorRepository, BookRepository, GenreRepository


def get_genre_repository(session: SessionDep) -> GenreRepository:
    return GenreRepository(session)


def get_author_repository(session: SessionDep) -> AuthorRepository:
    return AuthorRepository(session)


def get_book_repository(session: SessionDep) -> BookRepository:
    return BookRepository(session)


GenreRepoDep = Annotated[GenreRepository, Depends(get_genre_repository)]
AuthorRepoDep = Annotated[AuthorRepository, Depends(get_author_repository)]
BookRepoDep = Annotated[BookRepository, Depends(get_book_repository)]