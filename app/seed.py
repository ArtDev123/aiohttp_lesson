import asyncio

from sqlalchemy import func, insert, select

from app.db import make_engine, make_session_factory
from app.models import Author, Book, Genre

TARGET_BOOKS = 150_000
BATCH_SIZE = 1_000

GENRES = ["фантастика", "детектив", "поэзия"]
AUTHORS = [
    {"name": "Аркадий Стругацкий", "bio": "Советский писатель-фантаст"},
    {"name": "Агата Кристи", "bio": "Детективы"},
    {"name": "Анна Ахматова", "bio": "Поэт"},
]
NAMED_BOOKS = [
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
        genres = {
            genre.name: genre
            for genre in (await session.scalars(select(Genre))).all()
        }
        for name in GENRES:
            if name not in genres:
                genres[name] = Genre(name=name)
                session.add(genres[name])

        authors = {
            author.name: author
            for author in (await session.scalars(select(Author))).all()
        }
        for item in AUTHORS:
            if item["name"] not in authors:
                authors[item["name"]] = Author(name=item["name"], bio=item["bio"])
                session.add(authors[item["name"]])

        await session.flush()

        book_count = await session.scalar(select(func.count()).select_from(Book)) or 0
        if book_count >= TARGET_BOOKS:
            print(f"Сиды уже есть ({book_count} книг), пропускаем.")
            await engine.dispose()
            return

        if book_count == 0:
            session.add_all(
                [
                    Book(
                        title=item["title"],
                        year=item["year"],
                        author_id=authors[item["author"]].id,
                        genre_id=genres[item["genre"]].id,
                    )
                    for item in NAMED_BOOKS
                ]
            )
            await session.flush()
            book_count = len(NAMED_BOOKS)

        author_ids = [authors[item["name"]].id for item in AUTHORS]
        genre_ids = [genres[name].id for name in GENRES]
        to_create = TARGET_BOOKS - book_count
        batch: list[dict] = []
        added = 0

        for n in range(book_count + 1, TARGET_BOOKS + 1):
            batch.append(
                {
                    "title": f"Книга {n}",
                    "year": 1900 + (n % 200),
                    "author_id": author_ids[(n - 1) % len(author_ids)],
                    "genre_id": genre_ids[(n - 1) % len(genre_ids)],
                }
            )
            if len(batch) >= BATCH_SIZE:
                await session.execute(insert(Book), batch)
                added += len(batch)
                batch.clear()
                if added % 10_000 == 0:
                    print(f"  {book_count + added} / {TARGET_BOOKS}")

        if batch:
            await session.execute(insert(Book), batch)

        await session.commit()
        print(
            f"Добавлено: {len(genres)} жанра, {len(authors)} автора, "
            f"{to_create} книг (всего {TARGET_BOOKS})."
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())