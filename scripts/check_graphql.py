import asyncio

from app.db import make_engine, make_session_factory
from app.graphql.schema import schema

QUERY = """
{
  books {
    title
    year
    author { name bio }
    genre { name }
  }
}
"""


async def main() -> None:
    engine = make_engine()
    factory = make_session_factory(engine)
    async with factory() as session:
        result = await schema.execute(QUERY, context_value={"session": session})
    await engine.dispose()
    if result.errors:
        raise SystemExit(result.errors)
    for book in result.data["books"]:
        print(
            book["title"],
            "—",
            book["author"]["name"],
            "/",
            book["genre"]["name"],
        )


if __name__ == "__main__":
    asyncio.run(main())
