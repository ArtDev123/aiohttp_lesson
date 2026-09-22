# Шаг 2 — Тестовая Postgres

**Предыдущий:** [step-01-setup.md](step-01-setup.md) · **Следующий:** [step-03-fixtures.md](step-03-fixtures.md)

## Задача

Поднять базу **`library_test`**, в которую pytest сможет писать и которую можно целиком чистить. Сиды в `library_db` не трогаем. Тестов приложения ещё нет — только инфраструктура.

---

## Теория: две базы, один сервер

Postgres — это процесс. Внутри него много **баз** (каталогов). Подключение всегда говорит, в какую:

```text
postgresql://library_user:...@localhost:5432/library_db      ← Swagger, сиды
postgresql://library_user:...@localhost:5434/library_test    ← только pytest
```

Имя после слэша — не «ещё один контейнер обязательно», а имя каталога. Можно создать `library_test` на том же сервере, что и `library_db`. Опасно ровно тем, что легко перепутать URL.

Поэтому в уроке тестовая база живёт в **отдельном контейнере** на порту **5434**. Стереть её том — сиды на 5432/5433 на месте.

```text
хост
 ├── :5432  локальный Postgres из шага 1 (library_db)     — по желанию
 ├── :5433  Compose-сервис db (library_db)                — гайд Docker
 └── :5434  контейнер library-test-db (library_test)      — этот шаг
```

Пользователь тот же (`library_user` / `library_pass`), чтобы не плодить секреты. Меняются **имя БД** и **порт**.

Тесты ставят эти значения в `os.environ` **до** импорта `Settings`. Файл `.env` не меняйте: `make run` должен по-прежнему открывать `library_db`.

---

## Теория: кто создаёт пустую базу

Официальный образ `postgres:16` при первом старте читает `POSTGRES_DB` и создаёт каталог сам. Отдельный `CREATE DATABASE` не нужен.

`createdb` на уже живущем сервере — запасной путь, если Docker сейчас не хотите трогать. Тогда порт остаётся 5432, меняется только имя. **Не** делайте `TRUNCATE` по ошибке в `library_db`.

---

## 1. Контейнер (основной путь)

Как Redis в гайде Celery — одноразовый контейнер:

```bash
docker run -d --rm --name library-test-db \
  -e POSTGRES_DB=library_test \
  -e POSTGRES_USER=library_user \
  -e POSTGRES_PASSWORD=library_pass \
  -p 5434:5432 \
  postgres:16
```

`-d` — в фоне. `--rm` — удалится после `docker stop`. Слева `5434`, справа внутри всегда `5432`.

Подождите, пока демон примет соединения:

```bash
until docker exec library-test-db pg_isready -U library_user -d library_test; do
  sleep 1
done
```

Должно закончиться строкой `accepting connections`.

Проверка с хоста (нужен `psql` **или** тот же docker):

```bash
docker exec library-test-db \
  psql -U library_user -d library_test -c "SELECT current_database();"
```

Печатает `library_test`. Таблиц книг ещё нет — их создаст Alembic на шаге 3, не руками.

Остановка, когда закончите работать:

```bash
docker stop library-test-db
```

Если `5434` занят — смените левую часть `-p` и запомните порт: его же передадите в `TEST_POSTGRES_PORT`.

---

## 2. Запасной путь: база на уже стоящем Postgres

Только если контейнер не поднимаете. Локальный сервер с [шага 1 aiohttp](../remaining/step-01-env.md), пользователь уже есть:

```bash
psql -U library_user -d postgres -c "CREATE DATABASE library_test OWNER library_user;"
```

Повторный запуск скажет «already exists» — это нормально.

Тогда в тестах порт **5432**, не 5434. На шаге 3: `TEST_POSTGRES_PORT=5432`.

Не используйте для этого `library_db`. Не гоняйте `TRUNCATE` «проверить запрос» в сидовой базе.

---

## 3. Опционально: сервис в Compose

Если удобнее держать тестовую БД рядом с `db` / `redis`, добавьте в `docker-compose.yml`:

```yaml
  db_test:
    image: postgres:16
    environment:
      POSTGRES_DB: library_test
      POSTGRES_USER: ${POSTGRES_USER:-library_user}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-library_pass}
    ports:
      - "5434:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-library_user} -d library_test"]
      interval: 3s
      timeout: 3s
      retries: 10
```

Том не вешаем: данные тестов не бережём. `compose down` — база пустая, схема приедет снова из Alembic.

```bash
docker compose up -d db_test
```

Остальные сервисы (`app`, `worker`) не обязательны, чтобы гонять pytest с хоста.

---

## 4. Makefile (опционально)

```makefile
test-db:
	docker run -d --rm --name library-test-db \
		-e POSTGRES_DB=library_test \
		-e POSTGRES_USER=library_user \
		-e POSTGRES_PASSWORD=library_pass \
		-p 5434:5432 \
		postgres:16

test-db-stop:
	docker stop library-test-db
```

Windows без make — те же `docker run` / `docker stop`.

---

## Разбор: чего нет в `.env`

| Файл / переменная | Кто читает | База |
|-------------------|------------|------|
| `.env` `POSTGRES_DB=library_db` | `make run`, Compose `app` | боевая учебная |
| `os.environ` в `conftest.py` | только процесс `pytest` | `library_test` |

Не добавляйте `library_test` в `.env` «навсегда»: следующий `python -m app.main` откроет пустую базу без сидов, и вы решите, что приложение сломалось.

Порт тестов вынесем в `TEST_POSTGRES_PORT` (дефолт `5434`) — его нет в `Settings`. `conftest` переложит его в `POSTGRES_PORT` до импорта приложения.

---

## ✅ Проверка

```bash
docker exec library-test-db pg_isready -U library_user -d library_test
docker exec library-test-db \
  psql -U library_user -d library_test -c '\l'
```

В списке баз есть `library_test`.

Откройте DBeaver / `psql` на **5432 или 5433** — сиды `library_db` на месте.

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | контейнер (или `createdb`) запущен | `pg_isready` ок |
| ☐ | подключение к `library_test` | `current_database` = `library_test` |
| ☐ | таблиц `books` ещё нет | Alembic не гоняли |
| ☐ | `.env` не меняли | `POSTGRES_DB=library_db` |
| ☐ | `library_db` жива | сиды не исчезли |

Контейнер не останавливайте — он нужен на шаге 3.

**Все пункты отмечены?** → [step-03-fixtures.md](step-03-fixtures.md)
