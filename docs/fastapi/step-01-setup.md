# Шаг 1 — Пакеты FastAPI и что не трогаем

**Предыдущий:** [README.md](README.md) · **Следующий:** [step-02-app.md](step-02-app.md)

## Задача

Добавить FastAPI и Uvicorn в окружение и зафиксировать, какие файлы **переиспользуем как есть**. Сервер пока не переписываем — на этом шаге только зависимости.

Без этого шага на шаге 2 нечего импортировать.

---

## Теория: ASGI вместо `web.run_app`

aiohttp сам слушает порт (`web.run_app`). FastAPI — это **приложение**, его запускает ASGI-сервер.

```text
Uvicorn  →  FastAPI (app)  →  ваши роуты
```

| Роль | aiohttp | FastAPI |
|------|---------|---------|
| Приложение | `web.Application` | `FastAPI()` |
| Процесс, который слушает порт | `web.run_app` | **Uvicorn** |
| Протокол | собственный | ASGI |

`aiohttp` в `requirements.txt` **оставляем**: клиент (`task_1_client`) на нём. `aiohttp-swagger3` после переписывания сервера не понадобится — UI документации встроен в FastAPI.

PostgreSQL, `.env`, миграции, сиды уже есть из первого гайда. Если БД не поднята — вернитесь к [step-01-env.md](../remaining/step-01-env.md).

---

## 1. Дописать `requirements.txt`

В конец файла добавьте:

```text
fastapi>=0.115
uvicorn[standard]>=0.32
```

`[standard]` ставит `httptools` / `uvloop` (где доступен) — Uvicorn так быстрее и удобнее с `--reload`.

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

Windows: `.\.venv\Scripts\Activate.ps1`, затем та же команда `pip`.

---

## 2. Что копировать нельзя / не нужно

Не создавайте новые модели и не гоняйте `make migrations` «на всякий случай». Схема таблиц не меняется.

| Оставить | Не трогать на этом шаге |
|----------|-------------------------|
| `app/config.py` | `app/main.py` (шаг 2) |
| `app/models.py` | `app/routes/` (шаг 3) |
| `app/db.py` (`make_engine` / `make_session_factory`) | `app/schemas.py` (шаг 3) |
| `alembic/` | `app/openapi_components.yaml` (удалим на шаге 3) |
| `app/seed.py` | новый `repositories/` (шаг 4) |
| `task_1_client/` | — |

`make_engine` и `make_session_factory` пригодятся: FastAPI будет вызывать их в lifespan, сиды — как раньше.

---

## Разбор пакетов

| Пакет | Зачем |
|-------|--------|
| `fastapi` | роуты, `Depends`, автогенерация OpenAPI, валидация body через Pydantic |
| `uvicorn` | запуск ASGI-приложения |
| `aiohttp` | только `task_1_client` |
| `sqlalchemy` / `asyncpg` / `alembic` | как в первом гайде |

Pydantic 2 уже стоит — FastAPI 0.115 с ним дружит. Отдельный пакет `pydantic` обновлять не нужно, если `pip` не ругается.

---

## ✅ Проверка

```bash
source .venv/bin/activate
python -c "import fastapi, uvicorn; print(fastapi.__version__, uvicorn.__version__)"
python -c "from app.models import Genre, Author, Book; from app.config import settings; print(settings.app_port)"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `pip install -r requirements.txt` | без ошибок, в выводе есть `fastapi` и `uvicorn` |
| ☐ | импорт fastapi / uvicorn | две версии, не `ModuleNotFoundError` |
| ☐ | импорт моделей и settings | печатает `8080` (или ваш `APP_PORT`) |
| ☐ | `python -m app.main` | **пока** ещё aiohttp-сервер — так и должно быть |

Сервер на aiohttp на этом шаге специально не ломаем: каркас FastAPI — следующий файл.

**Все пункты отмечены?** → [step-02-app.md](step-02-app.md)
