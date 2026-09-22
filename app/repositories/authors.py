from app.models import Author
from app.repositories import BaseRepository


class AuthorRepository(BaseRepository[Author]):
    model = Author
