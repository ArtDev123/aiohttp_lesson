import strawberry

from app.graphql.authors.queries import AuthorQuery
from app.graphql.books.queries import BookQuery
from app.graphql.genres.queries import GenreQuery


@strawberry.type
class Query(GenreQuery, AuthorQuery, BookQuery):
    pass


schema = strawberry.Schema(query=Query)
