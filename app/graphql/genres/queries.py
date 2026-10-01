import strawberry

from app.graphql.context import get_session
from app.graphql.genres.types import GenreType
from app.repositories import GenreRepository


@strawberry.type
class GenreQuery:
    @strawberry.field
    async def genres(self, info: strawberry.Info) -> list[GenreType]:
        repo = GenreRepository(get_session(info))
        rows = await repo.get_all()
        return [GenreType.from_model(row) for row in rows]

    @strawberry.field
    async def genre(self, info: strawberry.Info, id: int) -> GenreType | None:
        repo = GenreRepository(get_session(info))
        row = await repo.get(id)
        return GenreType.from_model(row)
