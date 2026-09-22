from app.repositories.base import BaseRepository
from app.repositories.authors import AuthorRepository
from app.repositories.books import BookRepository
from app.repositories.genres import GenreRepository

__all__ = ["BaseRepository", "AuthorRepository", "BookRepository", "GenreRepository"]