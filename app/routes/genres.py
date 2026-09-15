from typing import Dict

from aiohttp import web
from sqlalchemy import select

from app.models import Genre


async def list_genres(request: web.Request) -> web.Response:
    """
    ---
    summary: Список жанров
    tags:
      - genres
    responses:
      "200":
        description: Все жанры
        content:
          application/json:
            schema:
              type: array
              items:
                $ref: "#/components/schemas/Genre"
    """
    async with request.app["session_factory"]() as session:
        result = await session.execute(select(Genre).order_by(Genre.id))
        genres = result.scalars().all()
        return web.json_response([genre.to_dict() for genre in genres])


async def get_genre(request: web.Request, genre_id: int) -> web.Response:
    """
    ---
    summary: Жанр по id
    tags:
      - genres
    parameters:
      - name: genre_id
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
              $ref: "#/components/schemas/Genre"
      "404":
        description: Нет такого жанра
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Error"
    """
    async with request.app["session_factory"]() as session:
        genre = await session.get(Genre, genre_id)
        if genre is None:
            return web.json_response({"error": "Жанр не найден"}, status=404)
        return web.json_response(genre.to_dict())


async def create_genre(request: web.Request, body: Dict) -> web.Response:
    """
    ---
    summary: Добавить жанр
    tags:
      - genres
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
    responses:
      "201":
        description: Создан
        content:
          application/json:
            schema:
              $ref: "#/components/schemas/Genre"
    """
    async with request.app["session_factory"]() as session:
        genre = Genre(name=body["name"])
        session.add(genre)
        await session.commit()
        await session.refresh(genre)
        return web.json_response(genre.to_dict(), status=201)
