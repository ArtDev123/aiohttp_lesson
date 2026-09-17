# Шаг 2 — FastAPI, lifespan и `Depends` на сессию

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-routes.md](step-03-routes.md)

## Задача

Заменить aiohttp-каркас на FastAPI с одним endpoint `/health`. Подключение к PostgreSQL — на старте, как раньше. Сессию в хендлер передаём **через dependency injection**, не через `request.app["..."]`.

CRUD книг ещё нет — сначала каркас, который можно дернуть `curl`.

---

## Теория: lifespan = startup + cleanup

В aiohttp:

```python
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)
```

В FastAPI один контекстный менеджер: код **до** `yield` — старт, **после** — остановка.

```text
Uvicorn стартует
        │
        ▼
lifespan: make_engine() → кладём factory в app.state
        │
        ▼
запросы (пока крутится сервер)
        │
        ▼
lifespan после yield: engine.dispose()
```

`app.state` — то же, что словарь `app["engine"]` в aiohttp, только атрибуты, не ключи.

Engine по-прежнему **не** создаём на уровне модуля: event loop должен уже существовать. Это то же правило, что на [шаге 4 aiohttp](../remaining/step-04-app.md).

---

## Теория: dependency injection

В aiohttp хендлер сам ходит за сессией:

```python
async def list_genres(request: web.Request) -> web.Response:
    factory = request.app["session_factory"]
    async with factory() as session:
        ...
```

Хендлер знает **два** дела: бизнес (список жанров) и инфраструктуру (где лежит factory). Каждый роут копирует `async with`. Чтобы подменить сессию в тесте, нужно знать ключ словаря `app`.

Это **service locator**: объект сам лезет в общий мешок (`app["..."]`) и достаёт зависимость.

**Dependency injection (DI)** — зависимость не достают, её **передают снаружи**.

```text
без DI (aiohttp)                    с DI
────────────────                    ────
хендлер:                            контейнер:
  сам берёт factory                   вызывает get_session
  сам открывает сессию                передаёт session аргументом
  делает SQL                        хендлер:
                                      только делает SQL
```

| | Locator (`app["..."]`) | Injection |
|---|------------------------|-----------|
| Кто создаёт сессию | хендлер | контейнер (FastAPI) |
| Хендлер знает про | ключ `session_factory` | тип `AsyncSession` |
| Подмена в тесте | подложить ключ в `app` | подменить провайдера |

«Инъекция» = подстановка: вы описали *что нужно*, кто-то другой решает *чем заполнить*. Хендлер перестаёт импортировать factory и не знает, настоящая это сессия или фейк.

Три роли:

1. **Потребитель** — хендлер: «мне нужна сессия».
2. **Провайдер** — функция вроде `get_session`: как её открыть и закрыть.
3. **Контейнер** — FastAPI: связал объявление с провайдером и вызвал его **до** хендлера.

На этом шаге инжектим сессию. На шаге 4 — репозиторий, которому сессия тоже придёт снаружи (вложенные зависимости). Ради этой подмены в тестах DI и затевался.

---

## Теория: что такое `Depends`

В FastAPI DI записывают в сигнатуре. `Depends(get_session)` — не «вызвать сейчас». Это декларация: «этот аргумент заполнит FastAPI».

```python
async def list_genres(session: AsyncSession = Depends(get_session)):
    ...
```

| Кто | Что делает |
|-----|------------|
| Вы | пишете `get_session` (как открыть и закрыть сессию) |
| FastAPI | перед хендлером вызывает зависимость, результат кладёт в аргумент |
| Хендлер | работает с готовым `session` |

Современная запись через `Annotated` — тип отдельно, инъекция отдельно. Так проще переиспользовать:

```python
from typing import Annotated

SessionDep = Annotated[AsyncSession, Depends(get_session)]

async def health(session: SessionDep) -> dict[str, str]:
    ...
```

Дальше в роутах пишем `session: SessionDep`, без копипасты `Depends(get_session)`.

---

## Теория: `yield` в зависимости

Обычный `return` не подходит: сессию нужно **закрыть после** ответа.

```python
async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory = request.app.state.session_factory
    async with factory() as session:
        yield session
```

```text
запрос пришёл
    → get_session дошёл до yield  (сессия открыта)
    → отработал хендлер
    → FastAPI продолжает генератор
    → async with выходит  (сессия закрыта, rollback если не было commit)
```

`Request` в зависимости FastAPI подставит сам. В `/health` `Request` в сигнатуре хендлера **не нужен**.

---

## 1. `app/errors.py`

Пока один тип ошибки — «строка не найдена». Обработчик повесим на приложение, чтобы JSON 404 остался `{"error": "..."}`, как в aiohttp.

```python
class NotFoundError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
```

На шаге 3 роуты будут делать `raise NotFoundError("Жанр не найден")` вместо `web.json_response(..., status=404)`.

---

## 2. `app/db.py`

Функции `make_engine` / `make_session_factory` оставьте. Добавьте зависимость сессии.

```python
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def make_engine():
    return create_async_engine(settings.database_url, echo=True)


def make_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    session_factory = request.app.state.session_factory
    async with session_factory() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

`expire_on_commit=False` — как раньше: после `commit` можно читать атрибуты без нового SELECT.

---

## 3. `app/main.py`

Полностью заменяет aiohttp-версию.

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionDep, make_engine, make_session_factory
from app.errors import NotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = make_engine()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mini Library API",
        version="1.0.0",
        description="Учебное API библиотеки на FastAPI.",
        lifespan=lifespan,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": exc.message})

    @app.get("/health")
    async def health(session: SessionDep) -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
```

Почему `health` принимает `session`, хотя БД не использует: так мы **сразу проверяем**, что цепочка `lifespan → app.state → Depends(get_session)` живая. Если factory не положили в `state`, `/health` упадёт — лучше узнать на каркасе, чем на `POST /books`.

`uvicorn.run("app.main:app", ...)` — строка импорта, не объект. Так Uvicorn сам загружает приложение (удобно, если позже включите `reload=True`).

`create_app()` + глобальный `app = create_app()` нужны и Uvicorn (`app.main:app`), и нам — фабрика, как `create_app()` в aiohttp.

---

## 4. Makefile (опционально)

Цель `run` можно оставить: `python -m app.main` по-прежнему работает. Либо явно:

```makefile
run:
	$(BIN)/uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Оба варианта должны попадать в тот же `settings.app_host` / `settings.app_port`, что в `.env`. Если зовёте `uvicorn` руками — пропишите хост и порт, иначе будет `127.0.0.1:8000` (дефолт Uvicorn).

---

## Разбор: чего больше нет

| aiohttp | FastAPI |
|---------|---------|
| `web.Request` в каждом хендлере | только если сами попросили |
| `web.json_response({"status": "ok"})` | `return {"status": "ok"}` |
| swagger, чтобы UI увидел роут | любой `@app.get` сразу в `/docs` |
| параметр обязан называться `request` | имена свободные |

Откройте [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) — там уже `/health`. Отдельный шаг «подключить Swagger» больше не нужен.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -m app.main
```

В другом терминале:

```bash
curl -s http://127.0.0.1:8080/health
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/docs
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | Старт сервера | в логе Uvicorn `Uvicorn running on http://127.0.0.1:8080` |
| ☐ | `GET /health` | `{"status":"ok"}` |
| ☐ | `GET /docs` | `200`, в браузере Swagger UI |
| ☐ | Остановка Ctrl+C | без traceback про незакрытый engine |
| ☐ | Импорт `from aiohttp import web` в `main.py` | **не должно остаться** |

Если `/health` падает с ошибкой `state` / `session_factory` — lifespan не отработал или смотрите не тот объект `app`.

**Все пункты отмечены?** → [step-03-routes.md](step-03-routes.md)
