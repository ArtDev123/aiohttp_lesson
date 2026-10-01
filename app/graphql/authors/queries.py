import strawberry

from app.graphql.authors.types import AuthorType
from app.graphql.context import get_session
from app.repositories import AuthorRepository


@strawberry.type
class AuthorQuery:
    @strawberry.field
    async def authors(self, info: strawberry.Info) -> list[AuthorType]:
        repo = AuthorRepository(get_session(info))
        rows = await repo.get_all()
        return [AuthorType.from_model(row) for row in rows]

    @strawberry.field
    async def author(self, info: strawberry.Info, id: int) -> AuthorType | None:
        repo = AuthorRepository(get_session(info))
        row = await repo.get(id)
        return AuthorType.from_model(row)
