from aiohttp import web

from app.routes.authors import create_author, get_author, list_authors
from app.routes.books import create_book, get_book, list_books
from app.routes.genres import create_genre, get_genre, list_genres


async def health(request: web.Request) -> web.Response:
    """
    ---
    summary: Проверка, что сервер жив
    tags:
      - health
    responses:
      "200":
        description: ok
        content:
          application/json:
            schema:
              type: object
              properties:
                status:
                  type: string
    """
    return web.json_response({"status": "ok"})


def routes() -> list[web.RouteDef]:
    return [
        web.get("/health", health),
        web.get("/genres", list_genres),
        web.get("/genres/{genre_id}", get_genre),
        web.post("/genres", create_genre),
        web.get("/authors", list_authors),
        web.get("/authors/{author_id}", get_author),
        web.post("/authors", create_author),
        web.get("/books", list_books),
        web.get("/books/{book_id}", get_book),
        web.post("/books", create_book),
    ]