import strawberry

from app.models import Author


@strawberry.type(name="Author")
class AuthorType:
    id: int
    name: str
    bio: str | None

    @classmethod
    def from_model(cls, author: Author) -> "AuthorType":
        return cls(id=author.id, name=author.name, bio=author.bio)
