# Шаг 5 — Redis и воркер в Compose

**Предыдущий:** [step-04-routes.md](step-04-routes.md) · **Следующий:** [step-06-final.md](step-06-final.md)

## Задача

Убрать ручной `docker run redis` и воркер с хоста. В `docker-compose.yml` появляются сервисы `redis` и `worker`. API в контейнере ходит в брокер по имени `redis`, файл экспорта лежит на **общем томе**.

Локальный `make run` + `make worker` по-прежнему работают с `REDIS_URL=localhost`. Compose переопределяет URL, как уже делал с `POSTGRES_HOST`.

---

## Теория: ещё два контейнера

После [docker/step-02](../docker/step-02-app.md) схема была такой:

```text
хост:8080 → app → db:5432
```

Теперь:

```text
хост:8080 → app ──► db:5432
              │
              └──► redis:6379 ──► worker ──► db:5432
                                    │
                         том exports ◄── app читает файл
```

| Сервис | Образ | Команда |
|--------|--------|---------|
| `db` | `postgres:16` | как была |
| `redis` | `redis:7-alpine` | дефолт образа (`redis-server`) |
| `app` | наш Dockerfile | entrypoint: alembic + uvicorn |
| `worker` | **тот же** образ | `celery worker`, **без** entrypoint |

`worker` собирается из того же `Dockerfile`: в образе уже есть Celery и код `app/`. Меняется только процесс при старте.

Помните правило Docker-гайда: один контейнер — один процесс. Не запускайте Celery из `docker-entrypoint.sh` рядом с Uvicorn. Два сервиса, один `build: .`.

---

## Теория: `localhost` для Redis

Та же ошибка, что с Postgres:

```text
make run на хосте          →  redis://localhost:6379  = контейнер с -p 6379
код внутри контейнера app  →  redis://localhost:6379  = пусто (Redis в другом контейнере)
код внутри app / worker    →  redis://redis:6379/0    = сервис redis
```

В Compose у `app` и `worker` пишем:

```yaml
REDIS_URL: redis://redis:6379/0
```

Имя хоста `redis` — ключ сервиса, DNS внутри сети Compose. Порт **6379**, не тот, что проброшен на ноутбук. Проброс `6379:6379` нужен только если с хоста зовёте `redis-cli`; контейнерам он не обязателен.

---

## Теория: общий том `exports`

У контейнера свой корневой диск. `worker` пишет `/app/exports/<id>.json` **внутрь себя**. Контейнер `app` этого файла не видит — у него другой диск.

```text
без тома                         с томом
────────                         ──────
worker: /app/exports/aaa.json    volume exports
app:    /app/exports/  (пусто)     ├─ смонтирован в worker:/app/exports
                                   └─ смонтирован в app:/app/exports
```

Именованный том — как `pgdata`, только для JSON. Bind-mount `./exports:/app/exports` тоже сработал бы и показал файлы в git-папке; в уроке берём named volume, чтобы не смешивать с кодом. Смотреть файл: `docker compose exec app ls /app/exports`.

`WORKDIR` образа — `/app`, задача пишет `Path("exports")` → `/app/exports`. Том монтируем именно туда.

---

## Теория: зачем сбрасывать `entrypoint`

`docker-entrypoint.sh` делает `alembic upgrade`, сиды и `exec python -m app.main`. Если повесить его на `worker`, получите **второй Uvicorn** (или гонку миграций), а не Celery.

```yaml
worker:
  build: .
  entrypoint: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
```

`entrypoint` в Compose **заменяет** `ENTRYPOINT` образа. Скрипт не вызывается. Миграции по-прежнему гоняет только `app` и только после `db` healthy.

Массив JSON — exec-форма: PID 1 = процесс `celery`, сигналы `compose stop` дойдут.

`depends_on` у воркера: ждать `db` (healthy) и `redis` (healthy). Без Redis воркер сразу умрёт с connection refused. Без Postgres первая задача упадёт в `FAILURE` — лучше не стартовать раньше времени.

---

## 1. Дописать `docker-compose.yml`

Полный файл после этого шага (старые поля `db` / `app` те же, плюс три правки: `redis`, `worker`, том и `REDIS_URL` у `app`):

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-library_db}
      POSTGRES_USER: ${POSTGRES_USER:-library_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-library_pass}
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-library_user} -d ${POSTGRES_DB:-library_db}"]
      interval: 3s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 3s
      timeout: 3s
      retries: 10

  app:
    build: .
    ports:
      - "8080:8080"
    env_file:
      - .env
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      APP_HOST: 0.0.0.0
      APP_PORT: 8080
      REDIS_URL: redis://redis:6379/0
    volumes:
      - exports:/app/exports
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: .
    entrypoint: ["celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
    env_file:
      - .env
    environment:
      POSTGRES_HOST: db
      POSTGRES_PORT: 5432
      REDIS_URL: redis://redis:6379/0
    volumes:
      - exports:/app/exports
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  pgdata:
  exports:
```

### Разбор новых полей

**`redis.image: redis:7-alpine`** — готовый образ, Dockerfile не пишем. `alpine` меньше `redis:7`. Данные брокера в уроке не сохраняем: том для Redis не вешаем. `compose down` — очередь пустая, файлы экспорта в томе `exports` остаются.

**`redis.healthcheck`** — `redis-cli ping` → `PONG` → код 0. `CMD` без shell: аргументы списком. `app` и `worker` ждут `service_healthy`, не просто `started`.

**`redis.ports: "6379:6379"`** — чтобы с ноутбука можно было оставить `REDIS_URL=localhost` для `make worker`. Если порт занят учебным `docker run` с шага 1 — остановите тот контейнер (`docker stop library-redis`), иначе Compose не займёт 6379.

**`app.environment.REDIS_URL`** — побеждает строку из `.env`. Settings в контейнере увидит хост `redis`.

**`app.volumes: exports:/app/exports`** — те же файлы, что пишет `worker`.

**`worker.build: .`** — тот же контекст и `.dockerignore`. После смены `requirements.txt` нужен `--build`, иначе в образе нет пакета `celery`.

**`worker.entrypoint`** — не entrypoint образа. Миграции не дублируются.

**`worker.environment.POSTGRES_HOST: db`** — воркер тоже не на `localhost`. Забытый хост: задача `FAILURE`, API живой, `GET` покажет `error`.

**`volumes.exports:`** в корне файла — объявить том. Имя совпадает с левой частью монтирования.

Dockerfile менять **не нужно**: `COPY app ./app` уже заберёт `celery_app.py` и `tasks.py`. `EXPOSE` для воркера не нужен — он не слушает HTTP.

---

## 2. Остановить ручной Redis

```bash
docker stop library-redis
```

Иначе два Redis на 6379. Потом:

```bash
docker compose up --build
```

В логах четыре сервиса. У `worker` — `celery@... ready` и задачи `ping`, `export_catalog`. У `app` — по-прежнему alembic, сиды, Uvicorn.

Локальный воркер (`make worker`) на время Compose выключите: два воркера на одну очередь не сломают урок, но файл может написать «не тот» процесс (хост vs том).

---

## Разбор: кто куда ходит

| С кого | Куда | Адрес |
|--------|------|--------|
| браузер | API | `127.0.0.1:8080` |
| контейнер `app` | Postgres | `db:5432` |
| контейнер `app` | Redis | `redis:6379` |
| контейнер `worker` | Postgres | `db:5432` |
| контейнер `worker` | Redis | `redis:6379` |
| `make run` на хосте | Postgres / Redis | `localhost` из `.env` |

`5433` и `6379` на хосте — только отладка (DBeaver, `redis-cli`). Приложение внутри сети их не использует.

---

## ✅ Проверка

```bash
docker compose ps
curl -s -X POST http://127.0.0.1:8080/exports
# подождать секунду, подставить id:
curl -s http://127.0.0.1:8080/exports/TASK_ID
curl -s http://127.0.0.1:8080/exports/TASK_ID/file | python -m json.tool
docker compose exec app ls /app/exports
docker compose logs worker --tail=30
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | `compose ps` | `db`, `redis`, `app`, `worker` — running / healthy |
| ☐ | лог `worker` | `ready`, нет второго Uvicorn |
| ☐ | `POST /exports` | `202` |
| ☐ | `GET` статуса | `SUCCESS` |
| ☐ | `GET .../file` | каталог книг |
| ☐ | `ls` в `app` | тот же `<id>.json`, что написал worker |
| ☐ | `GET /books` | жив |
| ☐ | `compose down` и `up` | том `exports` на месте, `pgdata` на месте; очередь Redis пустая |

---

## Типичные ошибки

| Симптом | Что проверить |
|---------|----------------|
| `Error 111 connecting to localhost:6379` в логе `app` | забыли `REDIS_URL: redis://redis:6379/0` |
| воркер сразу рестартится | Redis ещё не healthy **или** в образе нет `celery` (пересоберите) |
| `SUCCESS`, но `GET /file` → 404 | том не смонтирован в оба сервиса, или разные пути |
| в `worker` крутится Uvicorn | не переопределили `entrypoint` |
| задача `FAILURE` про `localhost:5432` | у `worker` нет `POSTGRES_HOST: db` |
| `Bind for 0.0.0.0:6379 failed` | жив `library-redis` с шага 1 |
| `POST` 202, статус вечно `PENDING` | `worker` не запущен или смотрит в другой Redis |

**Все пункты отмечены?** → [step-06-final.md](step-06-final.md)
