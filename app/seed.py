import asyncio

from sqlalchemy import select

from app.db import make_engine, make_session_factory
from app.models import Author, Book, Genre

GENRES = ["фантастика", "детектив", "поэзия"]
AUTHORS = [
    {"name": "Аркадий Стругацкий", "bio": "Советский писатель-фантаст"},
    {"name": "Агата Кристи", "bio": "Детективы"},
    {"name": "Анна Ахматова", "bio": "Поэт"},
]
BOOKS = [
    {
        "title": "Пикник на обочине",
        "year": 1972,
        "author": "Аркадий Стругацкий",
        "genre": "фантастика",
    },
    {
        "title": "Убийство в «Восточном экспрессе»",
        "year": 1934,
        "author": "Агата Кристи",
        "genre": "детектив",
    },
    {
        "title": "Реквием",
        "year": 1963,
        "author": "Анна Ахматова",
        "genre": "поэзия",
    },
]


async def seed() -> None:
    engine = make_engine()
    session_factory = make_session_factory(engine)
    async with session_factory() as session:
        already = await session.scalar(select(Genre.id).limit(1))
        if already is not None:
            print("Сиды уже есть, пропускаем.")
            await engine.dispose()
            return

        genres = {name: Genre(name=name) for name in GENRES}
        session.add_all(genres.values())

        authors = {
            item["name"]: Author(name=item["name"], bio=item["bio"])
            for item in AUTHORS
        }
        session.add_all(authors.values())
        await session.flush()

        books = [
            Book(
                title=item["title"],
                year=item["year"],
                author_id=authors[item["author"]].id,
                genre_id=genres[item["genre"]].id,
            )
            for item in BOOKS
        ]
        session.add_all(books)
        await session.commit()
        print(
            f"Добавлено: {len(genres)} жанра, {len(authors)} автора, {len(books)} книги."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())