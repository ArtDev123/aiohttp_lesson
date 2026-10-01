import strawberry

from app.models import Genre


@strawberry.type(name="Genre")
class GenreType:
    id: int
    name: str

    @classmethod
    def from_model(cls, genre: Genre) -> "GenreType":
        return cls(id=genre.id, name=genre.name)
