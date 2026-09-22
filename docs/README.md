# Мини-библиотека на aiohttp — документация

Пошаговый гайд: **aiohttp-клиент** и учебное **REST API библиотеки** (жанры, авторы, книги).

Материал разбит на этапы в папке [`remaining/`](remaining/README.md): теория → код → разбор → проверка.

## Как читать

1. Сначала [guide.md](guide.md) — что строим, модели, карта API.
2. Затем строго по порядку [remaining/](remaining/README.md) — не переходите дальше, пока не отметили «✅ Готово».
3. Когда aiohttp-сервер готов — [fastapi/](fastapi/README.md): переписать на FastAPI и вынести репозитории.
4. Когда API работает — [docker/](docker/README.md): Docker Desktop, контейнеры, Compose.

Каждый технический блок устроен одинаково:

1. **Задача** — что должно получиться и зачем шаг нужен.
2. **Теория** — концепции, без которых код «магия».
3. **Код** — что пишем в файлы.
4. **Разбор** — зачем каждая конструкция.
5. **✅ Проверка** — команды / `curl` / Swagger: что должно работать **сейчас**.

## Стек

| Компонент | Зачем |
|-----------|--------|
| aiohttp | async HTTP: и клиент, и сервер |
| PostgreSQL | основная БД (как в остальных TMS-проектах) |
| SQLAlchemy 2.x (async) | модели и запросы |
| Alembic | миграции схемы |
| aiohttp-swagger3 | OpenAPI + Swagger UI |
| Pydantic 2 | модели JSON (вход/выход) |
| pydantic-settings | `.env` → типизированный `Settings` |
| asyncpg | async-драйвер Postgres для приложения |
| psycopg2-binary | sync-драйвер для Alembic |

## Быстрый вход

```bash
cd aiohttp_lesson
# дальше — remaining/step-01-env.md
```

**Пошаговая сборка:** [remaining/README.md](remaining/README.md)

Когда aiohttp-приложение собрано и работает, его можно переписать на FastAPI (сначала как есть, потом слой репозиториев): [fastapi/README.md](fastapi/README.md).

Когда API поднимается локально — упаковать его вместе с PostgreSQL в Docker: [docker/README.md](docker/README.md).
