# # aiohttp.ClientSession: один клиент на много запросов.
# # Не открываем новое TCP-соединение на каждый GET — переиспользуем пул.
# import asyncio
# from time import perf_counter
#
# import aiohttp
#
# JSONPLACEHOLDER = "https://jsonplaceholder.typicode.com"
# POST_IDS = [1, 2, 3, 4, 5]
#
#
# async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict:
#     async with session.get(url) as response:
#         response.raise_for_status()
#         return await response.json()
#
#
# async def get_one_post(session: aiohttp.ClientSession) -> None:
#     post = await fetch_json(session, f"{JSONPLACEHOLDER}/posts/1")
#     print(f"GET /posts/1 → {post['title']}")
#
#
# async def get_posts_together(session: aiohttp.ClientSession) -> None:
#     # gather шлёт все запросы сразу; пока ждём сеть — event loop не стоит.
#     started = perf_counter()
#     posts = await asyncio.gather(
#         *[
#             fetch_json(session, f"{JSONPLACEHOLDER}/posts/{post_id}")
#             for post_id in POST_IDS
#         ]
#     )
#     elapsed = perf_counter() - started
#     print(f"параллельно {len(posts)} постов за {elapsed:.2f} сек.")
#
#
# async def create_post(session: aiohttp.ClientSession) -> None:
#     payload = {"title": "aiohttp client", "body": "пример POST", "userId": 1}
#     async with session.post(f"{JSONPLACEHOLDER}/posts", json=payload) as response:
#         response.raise_for_status()
#         created = await response.json()
#         print(f"POST /posts → id={created['id']}, status={response.status}")
#
#
# async def show_timeout() -> None:
#     # ClientTimeout ограничивает ожидание ответа, чтобы корутина не зависла.
#     timeout = aiohttp.ClientTimeout(total=0.001)
#     try:
#         async with aiohttp.ClientSession(timeout=timeout) as session:
#             await fetch_json(session, f"{JSONPLACEHOLDER}/posts/1")
#     except asyncio.TimeoutError:
#         print("таймаут: сервер не ответил за 0.001 сек.")
#
#
# async def main() -> None:
#     timeout = aiohttp.ClientTimeout(total=10)
#     async with aiohttp.ClientSession(timeout=timeout) as session:
#         print("=== один GET ===")
#         await get_one_post(session)
#
#         print("\n=== несколько GET сразу ===")
#         await get_posts_together(session)
#
#         print("\n=== POST JSON ===")
#         await create_post(session)
#
#     print("\n=== таймаут ===")
#     await show_timeout()
#
#
#
#
# if __name__ == "__main__":
#     asyncio.run(main())

from pydantic import BaseModel, Field, ValidationError


class GenreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


GenreCreate.model_validate({"name": "фантастика"})  # ок
GenreCreate.model_validate({"name": ""})