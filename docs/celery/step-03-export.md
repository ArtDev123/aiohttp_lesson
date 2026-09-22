# Шаг 3 — Задача `export_catalog`

**Предыдущий:** [step-02-app.md](step-02-app.md) · **Следующий:** [step-04-routes.md](step-04-routes.md)

## Задача

Написать настоящую работу воркера: прочитать все книги из Postgres (вместе с именами автора и жанра) и записать JSON-файл `exports/<task_id>.json`. HTTP ещё нет — задачу дергаем через `.delay()`, как `ping`.

---

## Теория: почему sync, не `AsyncSession`

FastAPI крутится на event loop: `async def` + `asyncpg`. Воркер Celery — **пул обычных процессов**. Он вызывает `def export_catalog():` и ждёт `return`. Своего asyncio-цикла у задачи нет.

```text
процесс Uvicorn                    процесс worker
───────────────                    ──────────────
asyncpg + AsyncSession             psycopg2 + Session
database_url                       database_url_sync
await session.execute(...)         session.execute(...)
```

`database_url_sync` и `psycopg2-binary` уже используются Alembic. Новый драйвер не ставим.

Не импортируйте `BookRepository` в задачу: он заточен под `AsyncSession` и `await`. Воркер не FastAPI, `Depends` там нет. SQL пишем прямо в задаче — один `select`, учебный объём.

В проде часто выносят sync-доступ в отдельный модуль. Здесь оставляем в `tasks.py`, чтобы цепочка «взял задачу → открыл сессию → файл» читалась сверху вниз.

---

## Теория: что кладём в Redis, что — в файл

Результат задачи (`return {...}`) попадает в backend — Redis. Туда хорошо класть **маленькую квитанцию**: сколько книг, как файл называется. Сам каталог — в файл:

| Куда | Что | Почему |
|------|-----|--------|
| `exports/<task_id>.json` | список книг | может вырасти; это «выгрузка» |
| Redis result | `{book_count, filename}` | статус и мета, не вторая копия каталога |

Имя файла = `task_id`. Celery сам выдаёт UUID; мы не генерируем случайные имена. Тогда `GET /exports/{task_id}/file` на шаге 4 просто открывает `exports/{task_id}.json`.

Папку `exports/` оба процесса должны видеть. Пока API и воркер на одной машине — одна папка в корне репозитория. В Docker на шаге 5 появится общий том: иначе файл окажется только в файловой системе контейнера `worker`, а `app` его не найдёт.

---

## Теория: `bind=True`

```python
@celery_app.task(bind=True, name="export_catalog")
def export_catalog(self) -> dict:
    task_id = self.request.id
```

`bind=True` передаёт задачу первым аргументом (`self`). Без него UUID в функции не из чего взять: `delay()` на стороне API уже отработал, воркер видит только тело задачи.

`self.request.id` — тот же id, который вернёт `export_catalog.delay().id` в роуте. Файл и статус склеены одним ключом.

---

## 1. `app/db.py` — sync-движок

К уже существующим `make_engine` / `make_session_factory` / `get_session` добавьте пару функций. Async-часть не меняйте.

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_sync_engine():
    return create_engine(settings.database_url_sync, echo=True)


def make_sync_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(engine, expire_on_commit=False)
```

`echo=True` — как у async-движка: в логе воркера будет видно `SELECT`. Для учебной задачи это полезнее, чем тишина.

Движок создаём **внутри задачи**, не на уровне модуля `db.py`. Урок FastAPI уже объяснял: объект соединения привязан к тому, кто его создал. Воркер форкает процессы; движок, созданный при импорте, после форка может сломаться. Проще открыть в задаче и закрыть в `finally`.

---

## 2. Папка `exports/` и `.gitignore`

В корне репозитория создайте папку и пустой маркер:

```bash
mkdir -p exports
touch exports/.gitkeep
```

В `.gitignore` добавьте:

```text
exports/*.json
```

`.gitkeep` оставляет папку в git, JSON выгрузок — нет. Каталог с книгами не секрет, но засорять дифф бинарными/сгенерированными файлами не нужно.

---

## 3. Дописать `app/tasks.py`

Оставьте `ping`. Ниже — экспорт.

```python
import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.celery_app import celery_app
from app.db import make_sync_engine, make_sync_session_factory
from app.models import Book

EXPORT_DIR = Path("exports")


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"


@celery_app.task(bind=True, name="export_catalog")
def export_catalog(self) -> dict:
    engine = make_sync_engine()
    factory = make_sync_session_factory(engine)
    try:
        with factory() as session:
            rows = session.execute(
                select(Book)
                .options(
                    selectinload(Book.author),
                    selectinload(Book.genre),
                )
                .order_by(Book.id)
            ).scalars().all()

            payload = [
                {
                    "id": book.id,
                    "title": book.title,
                    "year": book.year,
                    "author": book.author.name,
                    "genre": book.genre.name,
                }
                for book in rows
            ]
    finally:
        engine.dispose()

    EXPORT_DIR.mkdir(exist_ok=True)
    path = EXPORT_DIR / f"{self.request.id}.json"
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {"book_count": len(payload), "filename": path.name}
```

### Разбор по блокам

**`EXPORT_DIR = Path("exports")`** — относительный путь от **текущей рабочей директории**. И `celery worker`, и `python -m app.main` запускайте из корня репозитория. Иначе файл уедет в неожиданное место, а `FileResponse` его не найдёт.

**`make_sync_engine()` внутри задачи** — новое соединение на один экспорт. Для редкой выгрузки это нормально. Не тащите сюда `request.app.state`: у воркера нет FastAPI `app`.

**`with factory() as session:`** — sync-сессия закроется сама. `commit` не нужен: мы только читаем. Падение SELECT не оставит висящий коннект.

**`selectinload(Book.author)` / `genre`** — та же история, что в `BookRepository`. Без `selectinload` обращение к `book.author.name` либо сделает ленивый запрос (лавина N+1), либо упадёт, если сессия уже закрыта. Грузим связи сразу.

**`ensure_ascii=False`** — в сидах русские названия. Без флага в файле будет `\u041f\u0438\u043a\u043d\u0438\u043a` вместо «Пикник».

**`indent=2`** — файл читаемый глазами. Для гигабайтного дампа не делают; у нас три книги.

**`return {"book_count", "filename"}`** — только мета. Список книг в Redis не дублируем: его отдаст файл.

**`finally: engine.dispose()`** — даже если SELECT упал, пул соединений закрыт. Иначе воркер со временем утечёт в `too many connections`.

Порядок «сначала БД, потом файл» важен: пустой или битый JSON не появится, если запрос к Postgres не удался. Celery пометит задачу `FAILURE`, в backend ляжет текст исключения.

---

## Разбор: чего в задаче нет

| Не пишем | Почему |
|----------|--------|
| `async def` | воркер sync |
| `BookRepository` | он async |
| `Depends` | нет контейнера FastAPI |
| `BookRead` | Pydantic-схема HTTP; в файл кладём простой `dict` |
| `raise NotFoundError` | это выгрузка всех строк, пустой список — валидный результат |

Пустой каталог — `book_count: 0` и файл `[]`. Не ошибка.

---

## ✅ Проверка

Postgres должен быть доступен так же, как для `make run` (локальный или проброс из Docker). Сиды уже залиты.

Воркер перезапустите: он импортирует `tasks` **на старте**. Старый процесс `ping` не увидит новую функцию.

```bash
# терминал воркера: Ctrl+C и снова
celery -A app.celery_app worker --loglevel=info
```

В логе в `[tasks]` теперь `ping` и `export_catalog`.

Другой терминал:

```bash
source .venv/bin/activate
python -c "
from app.tasks import export_catalog
r = export_catalog.delay()
print(r.id)
print(r.get(timeout=10))
"
ls exports/
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | рестарт воркера | в списке задач есть `export_catalog` |
| ☐ | `delay` + `get` | словарь `book_count` (у сидов обычно 3) и `filename` |
| ☐ | `ls exports/` | файл `<uuid>.json` |
| ☐ | открыть JSON | книги с полями `title`, `author`, `genre` кириллицей |
| ☐ | лог воркера | `SELECT` и `Task export_catalog[...] succeeded` |
| ☐ | выключить Postgres и снова `delay` | задача `FAILURE`, файла нет (или старые файлы не перетёрлись) |

Если `get` пишет ошибку про `localhost:5432` — воркер смотрит не в тот Postgres. URL тот же, что у API: `Settings.database_url_sync`.

Роутов `/exports` ещё нет — не вызывайте `curl` на них.

**Все пункты отмечены?** → [step-04-routes.md](step-04-routes.md)
