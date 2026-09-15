# aiohttp — пошаговая сборка

Дополнение к [guide.md](../guide.md). Каждый файл — **один этап**: теория + код + проверка в конце.

> **Правило:** не открывайте следующий шаг, пока не отметили все пункты «✅ Готово» в текущем.

## Порядок шагов

| # | Файл | Что делаете | Теория |
|---|------|-------------|--------|
| 0 | *(этот файл)* | Обзор и команды | — |
| 1 | [step-01-env.md](step-01-env.md) | venv, requirements, PostgreSQL | окружение |
| 2 | [step-02-client.md](step-02-client.md) | HTTP-клиент | **ClientSession, gather, timeout** |
| 3 | [step-03-pydantic.md](step-03-pydantic.md) | Настройки и мини-гайд | **BaseModel, Field, BaseSettings** |
| 4 | [step-04-app.md](step-04-app.md) | Первый endpoint сервера | Application, handler, startup |
| 5 | [step-05-models.md](step-05-models.md) | Три модели | SQLAlchemy 2 mapped_column |
| 6 | [step-06-alembic.md](step-06-alembic.md) | Миграции | `alembic init` + autogenerate |
| 7 | [step-07-routes.md](step-07-routes.md) | CRUD API | handler + AsyncSession + Pydantic |
| 8 | [step-08-swagger.md](step-08-swagger.md) | Документация API | aiohttp-swagger3 |
| 9 | [step-09-final.md](step-09-final.md) | Сиды, чеклист | карта API |

> **Совет:** шаги **2, 3 и 4** — теоретический каркас. Не листайте теорию по диагонали.

## Что уже есть в репозитории

На старте кода приложения **нет** — всё создаёте по шагам 1–9. Скрипты PostgreSQL уже лежат в `scripts/`.

| Компонент | Статус |
|-----------|--------|
| venv + PostgreSQL | ❌ шаг 1 |
| aiohttp-клиент | ❌ шаг 2 |
| Pydantic / Settings | ❌ шаг 3 |
| web.Application / health | ❌ шаг 4 |
| Модели SQLAlchemy | ❌ шаг 5 |
| Alembic | ❌ шаг 6 |
| CRUD API + схемы | ❌ шаг 7 |
| Swagger | ❌ шаг 8 |
| Сиды / финальный прогон | ❌ шаг 9 |

## Быстрые команды (появятся по ходу)

```bash
source .venv/bin/activate   # Windows: .venv\Scripts\activate
make run                    # сервер
make client                 # задача 1
```

- API: [http://127.0.0.1:8080/health](http://127.0.0.1:8080/health)
- Swagger UI (с шага 8): [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)

```bash
curl -s http://127.0.0.1:8080/books | python -m json.tool
```

**Старт:** [step-01-env.md](step-01-env.md)
