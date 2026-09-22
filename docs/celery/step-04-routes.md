# Шаг 4 — Роуты `/exports`

**Предыдущий:** [step-03-export.md](step-03-export.md) · **Следующий:** [step-05-docker.md](step-05-docker.md)

## Задача

Повесить HTTP на очередь: `POST` ставит задачу и сразу возвращает `202` + `task_id`. `GET` читает статус из Redis. Скачивание файла — отдельный эндпоинт. Тело задачи не копируем в хендлер.

---

## Теория: `202 Accepted`

`200` значит «работа сделана, вот результат». Экспорт ещё **не** сделан, когда хендлер отвечает. Правильный код — **`202 Accepted`**: запрос принят, результат будет позже.

```text
POST /exports
  → delay()
  → 202 {"task_id": "...", "status": "PENDING"}

GET /exports/{task_id}          # крутим, пока не SUCCESS
GET /exports/{task_id}/file     # когда файл на диске
```

Клиент сам решает, как часто спрашивать статус. В уроке — руками через `curl`. В проде иногда делают webhook или WebSocket; нам хватит polling.

**Не вызывайте `result.get()` в хендлере.** `get()` блокирует процесс, пока воркер не закончит — и вы вернули синхронный экспорт под видом очереди. Хендлер только кладёт сообщение и читает уже известный статус.

---

## Теория: `AsyncResult`

```python
from celery.result import AsyncResult

result = AsyncResult(task_id, app=celery_app)
result.status    # PENDING / STARTED / SUCCESS / FAILURE
result.result    # то, что return, или исключение
```

Это не asyncio. Имя историческое: «результат асинхронной задачи». Объект ходит в Redis backend и спрашивает ключ `task_id`.

| `status` | Что произошло | Есть ли файл |
|----------|---------------|--------------|
| `PENDING` | в очереди **или** id вообще неизвестен | нет |
| `STARTED` | воркер взял задачу (`task_track_started`) | ещё нет |
| `SUCCESS` | `return` отработал | да |
| `FAILURE` | исключение в задаче | нет |

Ловушка `PENDING`: Celery не отличает «задача ждёт» от «такого id никогда не было». Несуществующий UUID тоже даст `PENDING`. В учебном API это приемлемо: не плодим таблицу job-ов в Postgres. В проде статус часто пишут в свою таблицу.

`result.result` при `SUCCESS` — наш словарь `{book_count, filename}`. При `FAILURE` — объект исключения; в JSON его не кладём как есть, берём `str(...)`.

---

## 1. Схемы в `app/schemas.py`

В конец файла:

```python
class ExportAccepted(BaseModel):
    task_id: str
    status: str


class ExportStatus(BaseModel):
    task_id: str
    status: str
    book_count: int | None = None
    filename: str | None = None
    error: str | None = None
```

`ExportAccepted` — ответ `POST` (ещё нет счётчика). `ExportStatus` — ответ `GET`: лишние поля `None`, пока задача не закончилась. FastAPI сам спрячет их в примере OpenAPI, если задать дефолт.

---

## 2. `app/routes/exports.py`

Новый файл.

```python
from pathlib import Path

from celery.result import AsyncResult
from fastapi import APIRouter, status
from fastapi.responses import FileResponse

from app.celery_app import celery_app
from app.errors import NotFoundError
from app.schemas import ErrorRead, ExportAccepted, ExportStatus
from app.tasks import EXPORT_DIR, export_catalog

router = APIRouter(prefix="/exports", tags=["exports"])


@router.post(
    "",
    response_model=ExportAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_export() -> ExportAccepted:
    result = export_catalog.delay()
    return ExportAccepted(task_id=result.id, status=result.status)


@router.get(
    "/{task_id}",
    response_model=ExportStatus,
)
def get_export(task_id: str) -> ExportStatus:
    result = AsyncResult(task_id, app=celery_app)
    payload = ExportStatus(task_id=task_id, status=result.status)

    if result.successful():
        data = result.result or {}
        payload.book_count = data.get("book_count")
        payload.filename = data.get("filename")
    elif result.failed():
        payload.error = str(result.result)

    return payload


@router.get(
    "/{task_id}/file",
    responses={404: {"model": ErrorRead}},
)
def download_export(task_id: str) -> FileResponse:
    path = EXPORT_DIR / f"{task_id}.json"
    if not path.is_file():
        raise NotFoundError("Файл экспорта ещё не готов или не найден")
    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )
```

### Разбор `POST`

`def create_export`, не `async def`. `delay()` — быстрый sync-вызов клиента Redis. Не блокируем event loop на секунды, только на сеть до брокера. Если очень захотите — есть `celery[asyncio]`, в уроке не нужно.

Тела запроса нет: выгружаем весь каталог. Когда появятся фильтры экспорта, их передадут аргументами `export_catalog.delay(year=1972)` — JSON-сериализуемые значения, не сессию.

`result.status` сразу после `delay()` почти всегда `PENDING`. Воркер ещё не дошёл.

### Разбор `GET` статуса

`AsyncResult(task_id, app=celery_app)` — обязательно передать `app`. Иначе клиент не знает URL backend и статус не прочитает.

`result.successful()` / `failed()` удобнее, чем сравнивать строки. Промежуточные `PENDING` и `STARTED` просто возвращаем с пустыми `book_count` / `error`.

Не читаем файл в этом хендлере. Статус — про очередь, файл — соседний URL. Иначе `GET /exports/{id}` начнёт таскать килобайты JSON, когда клиенту нужно одно слово `SUCCESS`.

### Разбор `GET` файла

`FileResponse` отдаёт байты с диска, не грузит их в Pydantic. `filename=` заставляет браузер скачать, а не показать.

Проверки «задача SUCCESS?» нет: источник истины для скачивания — **файл**. Если Redis уже забыл результат (TTL backend), а файл лежит, скачивание всё равно работает. Если задача `SUCCESS`, а диск почистили — `404`.

`NotFoundError` поймает тот же handler, что для книг: `{"error": "..."}` и 404.

Порядок роутов важен. Если бы вы написали `/{task_id}` так, что он перехватывает `file` — не проблема: путь `/{task_id}/file` длиннее и регистрируется отдельно. Не делайте `/{task_id}` ловящим всё подряд через `path`.

---

## 3. Подключить роутер

В `app/routes/__init__.py` добавьте импорт и `include_router`.

```python
from app.routes import authors, books, exports, genres


def register_routes(app: FastAPI) -> None:
    app.include_router(health_router())
    app.include_router(genres.router)
    app.include_router(authors.router)
    app.include_router(books.router)
    app.include_router(exports.router)
```

`/health` и CRUD не меняются.

---

## Разбор: два процесса на одной папке

```text
POST  → worker пишет exports/<id>.json
GET /file → app читает тот же путь
```

Запускайте Uvicorn и `celery worker` из **корня** репозитория (`WORKDIR` тот же). Иначе `Path("exports")` разойдётся.

В Docker у каждого контейнера свой диск — это шаг 5. Сейчас оба процесса на хосте, папка общая.

---

## ✅ Проверка

Три процесса: Redis, воркер, API.

```bash
# уже крутятся с прошлых шагов:
# docker run ... redis
# celery -A app.celery_app worker --loglevel=info
python -m app.main
```

```bash
curl -s -X POST http://127.0.0.1:8080/exports
# {"task_id":"....","status":"PENDING"}

# подставьте id:
curl -s http://127.0.0.1:8080/exports/TASK_ID
curl -s http://127.0.0.1:8080/exports/TASK_ID/file | python -m json.tool
```

Swagger: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) — группа `exports`.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `POST /exports` | `202`, есть `task_id` |
| ☐ | сразу `GET /exports/{id}` | `PENDING` или `STARTED` |
| ☐ | через секунду тот же `GET` | `SUCCESS`, `book_count` как у сидов |
| ☐ | `GET .../file` | JSON-массив книг, кириллица на месте |
| ☐ | `GET /exports/нет-такого-id` | `PENDING` (особенность Celery, не 404) |
| ☐ | `GET /exports/нет-такого-id/file` | `404` `{"error":"..."}` |
| ☐ | воркер выключен, новый `POST` | `202`, `GET` висит в `PENDING`, файла нет |
| ☐ | `GET /books` | как раньше, очередь его не сломала |

Если `POST` падает на связи с Redis — API не видит брокер. Сверьте `REDIS_URL` и что контейнер слушает `6379`.

**Все пункты отмечены?** → [step-05-docker.md](step-05-docker.md)
