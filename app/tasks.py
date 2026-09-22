import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.db import make_sync_engine, make_sync_session_factory
from app.models import Book

EXPORT_DIR = Path("exports")
EXPORT_BATCH_SIZE = 1_000


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


def _book_row(book: Book) -> dict:
    return {
        "id": book.id,
        "title": book.title,
        "year": book.year,
        "author": book.author.name,
        "genre": book.genre.name,
    }


@celery_app.task(bind=True, name="export_catalog")
def export_catalog(self) -> dict:
    EXPORT_DIR.mkdir(exist_ok=True)
    path = EXPORT_DIR / f"{self.request.id}.json"

    engine = make_sync_engine()
    factory = make_sync_session_factory(engine)
    book_count = 0
    last_id = 0

    try:
        with factory() as session, path.open("w", encoding="utf-8") as fh:
            fh.write("[\n")
            first = True

            while True:
                rows = session.execute(
                    select(Book)
                    .options(
                        selectinload(Book.author),
                        selectinload(Book.genre),
                    )
                    .where(Book.id > last_id)
                    .order_by(Book.id)
                    .limit(EXPORT_BATCH_SIZE)
                ).scalars().all()
                if not rows:
                    break

                for book in rows:
                    if not first:
                        fh.write(",\n")
                    first = False
                    json.dump(_book_row(book), fh, ensure_ascii=False)
                    book_count += 1

                last_id = rows[-1].id
                session.expire_all()

            fh.write("\n]\n")
    finally:
        engine.dispose()

    return {"book_count": book_count, "filename": path.name}