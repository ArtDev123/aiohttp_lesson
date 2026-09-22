# Шаг 6 — Финальный прогон

**Предыдущий:** [step-05-docker.md](step-05-docker.md) · **К карте:** [guide.md](guide.md)

## Задача

Прогнать экспорт целиком: либо четыре контейнера, либо хост (API + воркер + Redis + Postgres). Старый CRUD не должен поехать.

---

## 1. Два способа запуска

**Compose** (после шага 5):

```bash
docker compose up --build
```

**Хост** (Redis в одноразовом контейнере, остальное в venv):

```bash
docker run --rm -p 6379:6379 --name library-redis redis:7-alpine
# другие терминалы:
source .venv/bin/activate
celery -A app.celery_app worker --loglevel=info
python -m app.main
```

Не мешайте: либо Compose, либо хост. Два API на 8080 не встанут.

---

## 2. Чеклист API

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/books | python -m json.tool

TASK_ID=$(curl -s -X POST http://127.0.0.1:8080/exports | python -c "import json,sys; print(json.load(sys.stdin)['task_id'])")
echo "$TASK_ID"
sleep 2
curl -s "http://127.0.0.1:8080/exports/$TASK_ID"
curl -s "http://127.0.0.1:8080/exports/$TASK_ID/file" | python -m json.tool
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/exports/not-a-task/file
```

Swagger: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) — теги `exports`, `books`, `health`.

| ☐ | Проверка |
|---|----------|
| ☐ | `GET /health` → `{"status":"ok"}` |
| ☐ | `GET /books` как раньше |
| ☐ | `POST /exports` → `202` и `task_id` |
| ☐ | `GET /exports/{id}` → `SUCCESS`, `book_count` совпадает с длиной `GET /books` |
| ☐ | `GET .../file` — тот же набор книг, поля `author` / `genre` — строки |
| ☐ | неизвестный id на `/file` → `404` `{"error":"..."}` |
| ☐ | неизвестный id на `GET /exports/{id}` → `PENDING` (так устроен Celery) |
| ☐ | воркер в логе получил `export_catalog`, не Uvicorn |
| ☐ | `task_1_client` по-прежнему на aiohttp |
| ☐ | миграций новых нет |

---

## 3. Цепочки

```text
POST /exports
  → export_catalog.delay()
  → Redis (очередь)
  → 202 {task_id, PENDING}

worker
  → sync Session (psycopg2)
  → SELECT books + selectinload
  → exports/<task_id>.json
  → Redis (result: book_count, filename)

GET /exports/{id}
  → AsyncResult
  → PENDING | STARTED | SUCCESS | FAILURE

GET /exports/{id}/file
  → FileResponse, если файл есть
```

```text
четыре процесса (Compose)
  app      FastAPI, не пишет каталог
  worker   Celery, не слушает 8080
  redis    брокер + backend
  db       и API, и воркер
```

---

## 4. Было / стало

| Тема | До | После |
|------|----|--------|
| Тяжёлая работа | в хендлере, клиент ждёт | в воркере, клиент получает номер |
| Процессы | Uvicorn + Postgres | + Redis + Celery |
| Ответ на «сделай выгрузку» | `200` + тело | `202` + `task_id` |
| SQL в задаче | — | sync, `database_url_sync` |
| Docker | `app` + `db` | + `redis` + `worker` + том `exports` |

---

## 5. Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `ModuleNotFoundError: celery` в воркере | не пересобрали образ / не `pip install` в venv |
| вечный `PENDING` | воркер не запущен или другой `REDIS_URL` |
| `SUCCESS` и 404 на файл | разные рабочие директории или том только у одного сервиса |
| `delay()` в хендлере, ответ висит секундами | вызвали `.get()`, а не вернули `task_id` |
| `MissingGreenlet` / lazy load в воркере | нет `selectinload` |
| кириллица `\u041f...` | нет `ensure_ascii=False` |
| воркер поднимает Uvicorn | забыли сменить `entrypoint` |
| `Error connecting to localhost:6379` в Compose | не переопределили `REDIS_URL` |
| задача пишет в Postgres `localhost` из контейнера | нет `POSTGRES_HOST: db` у `worker` |

---

## 6. Куда расти (не в этом уроке)

- Таблица `export_jobs` в Postgres, если нужен список всех выгрузок и внятный 404 вместо `PENDING`.
- Аргументы задачи: `export_catalog.delay(genre_id=1)` — те же query-фильтры, что у `GET /books`.
- Повтор упавших задач (`autoretry_for`, `max_retries`).
- Celery Beat — по расписанию, не по `POST`.
- Flower — UI очереди; ещё один контейнер.

Тесты этого API на отдельной `library_test` (очередь — eager, без Redis) — следующий гайд: [../pytest/README.md](../pytest/README.md).

Карта раздела: [guide.md](guide.md) · Docker: [../docker/README.md](../docker/README.md)
