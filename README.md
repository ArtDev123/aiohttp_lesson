# aiohttp — клиент и мини-библиотека

Пошаговый гайд: **aiohttp.ClientSession** и маленькое REST API библиотеки (PostgreSQL, SQLAlchemy, Alembic, Swagger).

На старте в репозитории **нет кода приложения** — его вы собираете по шагам. Уже лежат только документация и скрипты PostgreSQL.

**Начните здесь:** [docs/README.md](docs/README.md)

После сборки aiohttp-сервера — переписывание на FastAPI: [docs/fastapi/README.md](docs/fastapi/README.md).

Когда API работает — Docker (Desktop, контейнеры, Compose): [docs/docker/README.md](docs/docker/README.md).

После Docker — фоновый экспорт на Celery: [docs/celery/README.md](docs/celery/README.md). Затем автотесты на `library_test`: [docs/pytest/README.md](docs/pytest/README.md).

Книга вместе с автором и жанром одним запросом — GraphQL: [docs/graphql/README.md](docs/graphql/README.md).

Прогресс экспорта по WebSocket: [docs/websockets/README.md](docs/websockets/README.md).

```bash
# Linux
./scripts/init_postgres.sh

# macOS
./scripts/init_postgres_mac.sh

# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File scripts\init_postgres.ps1
```
