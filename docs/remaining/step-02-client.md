# Шаг 2 — aiohttp-клиент (`ClientSession`)

**Предыдущий:** [step-01-env.md](step-01-env.md) · **Следующий:** [step-03-pydantic.md](step-03-pydantic.md)

## Задача

Написать учебный клиент: один GET, несколько GET сразу, POST JSON и таймаут. Сервер библиотеки для этого шага **не нужен** — ходим на [jsonplaceholder.typicode.com](https://jsonplaceholder.typicode.com).

---

## Теория: зачем `ClientSession`

Плохо: открывать новое TCP/TLS-соединение на каждый запрос.

```python
async with aiohttp.ClientSession() as session:  # один раз
    await session.get(url_a)
    await session.get(url_b)
```

`ClientSession` держит пул соединений. Его создают на «долго» (весь `main`, весь жизненный цикл приложения) и закрывают через `async with` или `await session.close()`.

### `async with session.get(...) as response`

Контекстный менеджер ответа нужно закрывать: иначе соединение не вернётся в пул.

```python
async with session.get(url) as response:
    data = await response.json()
```

### Параллельность: `asyncio.gather`

Пока один запрос ждёт сеть, event loop может крутить другие. `gather` запускает несколько корутин сразу и ждёт все.

```text
GET /posts/1  ──сеть──►
GET /posts/2  ──сеть──►   ≈ время самого медленного, не сумма
GET /posts/3  ──сеть──►
```

### Таймаут

`ClientTimeout(total=...)` ограничивает всё ожидание. Без него корутина может висеть бесконечно.

```python
timeout = aiohttp.ClientTimeout(total=10)
async with aiohttp.ClientSession(timeout=timeout) as session:
    ...
```

`asyncio.TimeoutError` — время вышло. `response.raise_for_status()` — HTTP 4xx/5xx превратить в исключение.

---

## Код — `task_1_client/main.py`

```python
# aiohttp.ClientSession: один клиент на много запросов.
# Не открываем новое TCP-соединение на каждый GET — переиспользуем пул.
import asyncio
from time import perf_counter

import aiohttp

JSONPLACEHOLDER = "https://jsonplaceholder.typicode.com"
POST_IDS = [1, 2, 3, 4, 5]


async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


async def get_one_post(session: aiohttp.ClientSession) -> None:
    post = await fetch_json(session, f"{JSONPLACEHOLDER}/posts/1")
    print(f"GET /posts/1 → {post['title']}")


async def get_posts_together(session: aiohttp.ClientSession) -> None:
    # gather шлёт все запросы сразу; пока ждём сеть — event loop не стоит.
    started = perf_counter()
    posts = await asyncio.gather(
        *[
            fetch_json(session, f"{JSONPLACEHOLDER}/posts/{post_id}")
            for post_id in POST_IDS
        ]
    )
    elapsed = perf_counter() - started
    print(f"параллельно {len(posts)} постов за {elapsed:.2f} сек.")


async def create_post(session: aiohttp.ClientSession) -> None:
    payload = {"title": "aiohttp client", "body": "пример POST", "userId": 1}
    async with session.post(f"{JSONPLACEHOLDER}/posts", json=payload) as response:
        response.raise_for_status()
        created = await response.json()
        print(f"POST /posts → id={created['id']}, status={response.status}")


async def show_timeout() -> None:
    # ClientTimeout ограничивает ожидание ответа, чтобы корутина не зависла.
    timeout = aiohttp.ClientTimeout(total=0.001)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await fetch_json(session, f"{JSONPLACEHOLDER}/posts/1")
    except asyncio.TimeoutError:
        print("таймаут: сервер не ответил за 0.001 сек.")


async def main() -> None:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        print("=== один GET ===")
        await get_one_post(session)

        print("\n=== несколько GET сразу ===")
        await get_posts_together(session)

        print("\n=== POST JSON ===")
        await create_post(session)

    print("\n=== таймаут ===")
    await show_timeout()


if __name__ == "__main__":
    asyncio.run(main())
```

**Разбор:**

| Кусок | Зачем |
|-------|--------|
| Один `ClientSession` в `main` | пул соединений на все GET/POST |
| `json=` у POST | aiohttp сам сериализует dict и ставит `Content-Type` |
| Отдельная сессия в `show_timeout` | свой `total=0.001`, чтобы демонстрация не ломала остальные запросы |
| `asyncio.run(main())` | создаёт event loop, крутит `main`, закрывает loop |

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -m task_1_client.main
# или: make client
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Один GET | строка с заголовком поста |
| ☐ | Несколько GET | `параллельно 5 постов за 0.xx сек.` (не ~сумма пяти RTT) |
| ☐ | POST | `status=201` и `id=101` (jsonplaceholder фейковый id) |
| ☐ | Таймаут | сообщение «таймаут: сервер не ответил…» |

**Все пункты отмечены?** → [step-03-pydantic.md](step-03-pydantic.md)
