# Шаг 2 — Приложение Celery и задача `ping`

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-export.md](step-03-export.md)

## Задача

Создать объект `Celery`, зарегистрировать пустую задачу `ping` и прогнать её через живой воркер. Экспорта книг ещё нет — сначала проверяем, что API-процесс и воркер разговаривают через Redis.

---

## Теория: приложение Celery

В FastAPI есть `app = FastAPI(...)` — точка сборки роутов. У Celery то же самое: один объект знает брокер, backend и список модулей с задачами.

```python
celery_app = Celery(
    "library",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)
```

| Аргумент | Смысл |
|----------|--------|
| `"library"` | имя приложения (логи, префикс ключей в Redis) |
| `broker` | куда класть сообщения |
| `backend` | куда писать статус и `return` задачи |
| `include` | какие модули импортировать при старте воркера, чтобы увидеть `@task` |

`broker` и `backend` могут быть разными Redis DB (`.../0` и `.../1`). В уроке один URL — проще. Не путайте с PostgreSQL: книги живут в Postgres, квитанции задач — в Redis.

`include=["app.tasks"]` обязателен. Без него воркер стартует, но «задачи `ping` не знаю» — декоратор не выполнился, функция не зарегистрирована.

---

## Теория: задача и `delay`

Обычный вызов:

```python
ping()          # выполнилось здесь и сейчас, в этом процессе
```

Вызов через очередь:

```python
result = ping.delay()   # сообщение в Redis, эта строка почти мгновенная
result.id               # UUID
result.get(timeout=5)   # подождать результат (в роуте так не делаем)
```

`delay(*args, **kwargs)` — сахар над `apply_async`. Аргументы должны сериализоваться в JSON: числа, строки, списки, словари. **Нельзя** передать `AsyncSession`, открытый файл или ORM-объект — воркер в другом процессе, pickle-сюрпризы нам не нужны. Поэтому сериализатор сразу ставим `json`.

```text
ping.delay()
    → Redis: {task: "ping", id: "aa-bb", args: []}
    → воркер: достал, вызвал ping(), получил "pong"
    → Redis: {id: "aa-bb", status: SUCCESS, result: "pong"}
```

Если воркера нет, сообщение лежит в брокере. `get(timeout=5)` тогда упрётся в таймаут — это нормально, не «баг ping».

---

## Теория: воркер — отдельный процесс

```bash
celery -A app.celery_app worker --loglevel=info
```

| Кусок | Смысл |
|-------|--------|
| `-A app.celery_app` | импортировать модуль и взять объект `celery_app` |
| `worker` | роль: забирать задачи, не Beat и не Flower |
| `--loglevel=info` | в логе видно `received` / `succeeded` |

Это **не** `python -m app.main`. Два терминала:

```text
терминал 1:  python -m app.main          # порт 8080
терминал 2:  celery -A app.celery_app worker
терминал 3:  curl / docker redis
```

Пока воркер не запущен, `POST /exports` на шаге 4 всё равно вернёт `202` — сообщение в Redis есть. Файла не будет, пока кто-то не заберёт задачу. Поэтому `ping` гоняем руками: сразу видно, жив ли воркер.

---

## 1. `app/celery_app.py`

Новый файл.

```python
from celery import Celery

from app.config import settings

celery_app = Celery(
    "library",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
```

### Разбор

`Celery(...)` не открывает HTTP-порт и не лезет в Postgres. Только конфиг клиента и воркера.

`task_serializer="json"` — аргументы и результат только JSON. Если случайно передадите ORM, упадёте сразу, а не на стороне воркера с нечитаемым pickle.

`task_track_started=True` — статус `STARTED`, когда воркер взял задачу. Без флага вы увидите только `PENDING` и `SUCCESS`: «уже делают» неотличимо от «ещё в очереди». На шаге 4 это пригодится в `GET /exports/{id}`.

`timezone` / `enable_utc` — чтобы логи и ETA не плясали с локальным поясом. Учебные задачи без расписания, но дефолт лучше зафиксировать.

Не создавайте второй `Celery()` в `tasks.py`. Один объект на процесс, его импортируют и роуты, и команда `celery -A`.

---

## 2. `app/tasks.py`

Новый файл. Пока одна функция.

```python
from app.celery_app import celery_app


@celery_app.task(name="ping")
def ping() -> str:
    return "pong"
```

### Разбор

`@celery_app.task` регистрирует функцию в реестре приложения. Имя `"ping"` попадёт в сообщение Redis. Без `name=` Celery взял бы `"app.tasks.ping"` — длиннее и привязано к пути модуля.

Это обычный `def`, не `async def`. Воркер Celery вызывает задачу синхронно. `await` внутри без своего event loop не заработает — поэтому на шаге 3 будет sync SQLAlchemy, не `AsyncSession`.

`return "pong"` Celery положит в backend. `result.get()` на стороне клиента вернёт эту строку.

Не вызывайте `ping()` из модуля на импорте. Регистрация — да, выполнение — нет.

---

## 3. Makefile (опционально)

К уже существующим целям:

```makefile
worker:
	$(BIN)/celery -A app.celery_app worker --loglevel=info
```

Windows без make:

```bash
celery -A app.celery_app worker --loglevel=info
```

---

## Разбор: кто кого импортирует

```text
celery -A app.celery_app
        → import app.celery_app
        → include=["app.tasks"]
        → import app.tasks
        → @celery_app.task  (ping в реестре)
```

`tasks.py` импортирует `celery_app`. `celery_app.py` **не** импортирует `tasks` сверху файла — только строкой в `include`. Иначе легко словить циклический импорт, когда задач станет больше.

Роуты на шаге 4 будут писать `from app.tasks import export_catalog` и звать `.delay()`. FastAPI-процесс **не** выполняет тело задачи: он только кладёт сообщение.

---

## ✅ Проверка

Терминал 1 — Redis (если ещё не запущен с шага 1):

```bash
docker run --rm -p 6379:6379 --name library-redis redis:7-alpine
```

Терминал 2 — воркер:

```bash
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
```

В логе должны быть строки вроде `celery@... ready` и список задач: `ping`.

Терминал 3:

```bash
source .venv/bin/activate
python -c "from app.tasks import ping; r = ping.delay(); print(r.id); print(r.get(timeout=5))"
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | старт воркера | `ready`, в `[tasks]` есть `ping` |
| ☐ | `ping.delay()` + `get` | UUID и строка `pong` |
| ☐ | лог воркера | `Task ping[...] received` и `succeeded` |
| ☐ | остановить воркер и снова `get(timeout=5)` | `TimeoutError` — сообщение висит, выполнять некому |
| ☐ | в `app/main.py` нет импорта Celery | API пока не знает про очередь — так и должно быть |

Если `get` сразу кидает связь с Redis — воркер и клиент смотрят на разные URL, или контейнер не запущен. Сверьте `settings.redis_url` и `docker ps`.

**Все пункты отмечены?** → [step-03-export.md](step-03-export.md)
