from typing import Dict

from aiohttp import web
from sqlalchemy import select

from app.models import Author


async def list_authors(request: web.Request) -> web.Response:
    """
    ---
    summary: Список авторов
    tags:
      - authors
    responses:
      "200":
        description: Все авторы
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Author"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(select(Author).order_by(Author.id))
        authors = result.scalars().all()
        return web.json_response([author.to_dict() for author in authors])


async def get_author(request: web.Request, author_id: int) -> web.Response:
    """
    ---
    summary: Автор по id
    tags:
      - authors
    parameters:
      - name: author_id
        in: path
        required: true
        schema:
          type: integer
    responses:
      "200":
        description: Найден
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Author"
      "404":
        description: Нет такого автора
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        author = await session.get(Author, author_id)
        if author is None:
            return web.json_response({"error": "Автор не найден"}, status=404)
        return web.json_response(author.to_dict())


async def create_author(request: web.Request, body: Dict) -> web.Response:
    """
    ---
    summary: Добавить автора
    tags:
      - authors
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required:
              - name
            properties:
              name:
                type: string
              bio:
                type: string
    responses:
      "201":
        description: Создан
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Author"
    """
    async with request.app["session_factory"]() as session:
        author = Author(name=body["name"], bio=body.get("bio"))
        session.add(author)
        await session.commit()
        await session.refresh(author)
        return web.json_response(author.to_dict(), status=201)
