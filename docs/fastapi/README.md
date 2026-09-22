# Мини-библиотека на FastAPI — документация

Продолжение aiohttp-урока: то же REST API библиотеки (жанры, авторы, книги), но на **FastAPI** с **dependency injection**. Клиент из задачи 1 (`task_1_client`) не трогаем — он по-прежнему на aiohttp.

Материал разбит на этапы: теория → код → разбор → проверка.

## Как читать

1. Сначала [guide.md](guide.md) — что оставляем, что меняется, две фазы переписывания.
2. Затем строго по порядку шаги ниже — не переходите дальше, пока не отметили «✅ Готово».

Каждый технический блок устроен одинаково:

1. **Задача** — что должно получиться и зачем шаг нужен.
2. **Теория** — концепции, без которых код «магия».
3. **Код** — что пишем в файлы.
4. **Разбор** — зачем каждая конструкция.
5. **✅ Проверка** — команды / `curl` / Swagger: что должно работать **сейчас**.

## Две фазы

| Фаза | Шаги | Что делаете |
|------|------|-------------|
| 1. Как есть | 1–3 | aiohttp-хендлеры → FastAPI-роуты, сессию берём через `Depends`, плюс PATCH |
| 2. Репозитории | 4–5 | SQL в репозитории → общий `BaseRepository`, роуты остаются тонкими |
| 3. Фильтры | 6 | query на `GET /books` через `BookFilters` + `Depends()` |

## Порядок шагов

| # | Файл | Что делаете | Теория |
|---|------|-------------|--------|
| 0 | *(этот файл)* | Обзор | — |
| 1 | [step-01-setup.md](step-01-setup.md) | пакеты FastAPI / Uvicorn | что переиспользуем |
| 2 | [step-02-app.md](step-02-app.md) | `FastAPI`, lifespan, `/health` | **DI, Depends, yield-зависимость** |
| 3 | [step-03-routes.md](step-03-routes.md) | CRUD «как есть» + PATCH | **APIRouter, body как Pydantic** |
| 4 | [step-04-repos.md](step-04-repos.md) | слой репозиториев | вложенный `Depends`, кэш на запрос |
| 5 | [step-05-base.md](step-05-base.md) | `BaseRepository` | Generic, классовый `model` |
| 6 | [step-06-filters.md](step-06-filters.md) | query-фильтры `GET /books` | **Query, BookFilters, Depends()** |
| 7 | [step-07-final.md](step-07-final.md) | чеклист | aiohttp vs FastAPI |

> **Правило:** не пишите код «вперёд гайда». Сначала каркас и DI сессии, потом те же CRUD, потом репозитории, потом база, потом фильтры.

## Стек после переписывания

| Компонент | Зачем |
|-----------|--------|
| FastAPI | async-сервер, роуты, встроенный OpenAPI |
| Uvicorn | ASGI-сервер |
| PostgreSQL | та же БД |
| SQLAlchemy 2.x (async) | те же модели |
| Alembic | те же миграции |
| Pydantic 2 | Create / Read / Update, FastAPI сам валидирует body |
| pydantic-settings | тот же `Settings` |
| aiohttp | только клиент (`task_1_client`) |

**Старт:** [step-01-setup.md](step-01-setup.md)

Когда чеклист FastAPI закрыт — то же API в контейнерах: [../docker/README.md](../docker/README.md).
