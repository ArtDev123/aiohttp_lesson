from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Author, Book, Genre
from app.schemas import BookCreate, BookRead, ErrorRead, parse_body


async def list_books(request: web.Request) -> web.Response:
    """
    ---
    summary: Список книг
    tags:
      - books
    responses:
      "200":
        description: Все книги
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Book"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .order_by(Book.id)
        )
        books = result.scalars().all()
        return web.json_response([BookRead.from_book(book).model_dump() for book in books])


async def get_book(request: web.Request, book_id: int) -> web.Response:
    """
    ---
    summary: Книга по id
    tags:
      - books
    parameters:
      - name: book_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      "200":
        description: Найдена
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Book"
      "404":
        description: Нет такой книги
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .where(Book.id == book_id)
        )
        book = result.scalar_one_or_none()
        if book is None:
            return web.json_response(ErrorRead(error="Книга не найдена").model_dump(), status=404)
        return web.json_response(BookRead.from_book(book).model_dump())


async def create_book(request: web.Request, body: dict) -> web.Response:
    """
    ---
    summary: Добавить книгу
    tags:
      - books
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - title
              - author_id
              - genre_id
            properties:
              title:
                type: string
              year:
                type: integer
              author_id:
                type: integer
              genre_id:
                type: integer
    responses:
      "201":
        description: Создана
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Book"
      "404":
        description: Автор или жанр не найдены
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    payload = parse_body(BookCreate, body)
    async with request.app["session_factory"]() as session:
        author = await session.get(Author, payload.author_id)
        genre = await session.get(Genre, payload.genre_id)
        if author is None:
            return web.json_response(ErrorRead(error="Автор не найден").model_dump(), status=404)
        if genre is None:
            return web.json_response(ErrorRead(error="Жанр не найден").model_dump(), status=404)

        book = Book(
            title=payload.title,
            year=payload.year,
            author_id=author.id,
            genre_id=genre.id,
        )
        session.add(book)
        await session.commit()

        result = await session.execute(
            select(Book)
            .options(selectinload(Book.author), selectinload(Book.genre))
            .where(Book.id == book.id)
        )
        created = result.scalar_one()
        return web.json_response(BookRead.from_book(created).model_dump(), status=201)