# Шаг 4 — Сервер: `web.Application` и `/health`

**Предыдущий:** [step-03-pydantic.md](step-03-pydantic.md) · **Следующий:** [step-05-models.md](step-05-models.md)

## Задача

Поднять aiohttp-сервер с одним endpoint `/health` и подключением к PostgreSQL на старте. CRUD книг ещё нет — сначала каркас, который можно дернуть `curl`. Настройки уже есть: `settings` с шага 3.

---

## Теория: Application, handler, жизненный цикл

```text
web.run_app(app)
        │
        ▼
on_startup  →  создаём engine + session_factory, кладём в app["..."]
        │
        ▼
запрос GET /health → router → async def health(request) → JSON
        │
        ▼
on_cleanup  →  engine.dispose()
```

**Handler** — `async def name(request: web.Request) -> web.Response`. Это view aiohttp.

**`app["ключ"]`** — словарь приложения: сюда кладут engine, чтобы handlers не создавали подключение каждый раз.

**`on_startup` / `on_cleanup`** — список корутин. Не открывайте engine на уровне модуля: event loop ещё может не существовать.

Клиент с шага 2 *ходил наружу*. Здесь aiohttp — *принимающая* сторона: `web.Application` + `router`.

Пока регистрируем роут так:

```python
app.router.add_get("/health", health)
```

На шаге 8 переключим регистрацию на `swagger.add_routes(...)` — иначе Swagger UI не увидит методы.

---

## 1. `app/db.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def make_engine():
    return create_async_engine(settings.database_url, echo=False)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

`expire_on_commit=False` — после `commit` можно читать атрибуты объекта без нового SELECT.

---

## 2. `app/main.py`

```python
from aiohttp import web

from app.config import settings
from app.db import make_engine, make_session_factory


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def on_startup(app: web.Application) -> None:
    engine = make_engine()
    app["engine"] = engine
    app["session_factory"] = make_session_factory(engine)


async def on_cleanup(app: web.Application) -> None:
    await app["engine"].dispose()


def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    app.router.add_get("/health", health)
    return app


def main() -> None:
    web.run_app(create_app(), host=settings.app_host, port=settings.app_port)


if __name__ == "__main__":
    main()
```

Параметр handler **должен называться `request`**. На шаге 8 swagger3 прокидывает его по имени; `_request` даст `TypeError: missing argument`.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -m app.main
```

В другом терминале:

```bash
curl -s http://127.0.0.1:8080/health
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Старт сервера | в логе `Running on http://127.0.0.1:8080` |
| ☐ | `GET /health` | `{"status": "ok"}` |
| ☐ | Остановка Ctrl+C | без traceback про незакрытый engine |

**Все пункты отмечены?** → [step-05-models.md](step-05-models.md)
