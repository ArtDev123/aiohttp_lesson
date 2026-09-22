from app.models import Genre
from app.repositories import BaseRepository


class GenreRepository(BaseRepository[Genre]):
    model = Genre
