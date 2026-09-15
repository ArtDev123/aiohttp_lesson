# Шаг 8 — Swagger UI

**Предыдущий:** [step-07-routes.md](step-07-routes.md) · **Следующий:** [step-09-final.md](step-09-final.md)

## Задача

Открыть интерактивную документацию API: **Swagger UI** на `/docs`. Схемы уже описаны в docstring handlers и в `openapi_components.yaml` — осталось включить UI.

---

## Теория: зачем OpenAPI, а не только curl

| Инструмент | Плюсы | Минусы |
|------------|--------|--------|
| `curl` | всегда под рукой | руками помнить поля |
| Postman | коллекции | синхронизировать с кодом |
| **Swagger UI** | схема из docstring, Try it out | пакет + YAML в хендлерах |

`aiohttp-swagger3` читает блок после `---` в docstring handler и собирает OpenAPI 3. Роуты **обязательно** через `swagger.add_routes` — иначе метода нет ни в схеме, ни с инъекцией `body` / `book_id`.

```text
docstring YAML  +  components.yaml  →  spec
                                         ↓
                                   GET /docs  (Swagger UI)
                                   GET /docs/swagger.json
```

`validate=True` (уже стоит) — невалидный POST (нет `name`) вернёт 400 до вашего handler.

Имя аргумента `request` нельзя заменять на `_request`: swagger3 передаёт его как keyword `request=...`.

---

## 1. Включить UI в `create_app`

В `app/main.py` добавьте `SwaggerUiSettings`:

```python
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings
```

И в `SwaggerDocs(...)`:

```python
swagger = SwaggerDocs(
    app,
    validate=True,
    info=SwaggerInfo(
        title="Mini Library API",
        version="1.0.0",
        description="Учебное API библиотеки на aiohttp.",
    ),
    components="app/openapi_components.yaml",
    swagger_ui_settings=SwaggerUiSettings(path="/docs"),
)
swagger.add_routes(routes())
```

Путь `/docs` без слэша: библиотека сама редиректит на `/docs/`.

---

## 2. Проверьте `app/openapi_components.yaml`

Файл с шага 6 должен содержать схемы `Genre`, `Author`, `Book`, `Error`. Если `$ref` указывает на несуществующую схему, swagger3 упадёт при старте с ошибкой валидации spec.

Развёрнутый вариант (удобнее читать в UI):

```yaml
components:
  schemas:
    Genre:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
    Author:
      type: object
      properties:
        id:
          type: integer
        name:
          type: string
        bio:
          type: string
          nullable: true
    Book:
      type: object
      properties:
        id:
          type: integer
        title:
          type: string
        year:
          type: integer
          nullable: true
        author_id:
          type: integer
        genre_id:
          type: integer
        author:
          type: string
          nullable: true
        genre:
          type: string
          nullable: true
    Error:
      type: object
      properties:
        error:
          type: string
```

---

## ✅ Проверка

```bash
python -m app.main
```

| ☐ | Действие | Ожидаемый результат |
|---|----------|---------------------|
| ☐ | [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs) | страница Swagger UI |
| ☐ | В UI видны теги `health`, `genres`, `authors`, `books` | да |
| ☐ | Try it out → `GET /books` | JSON списка |
| ☐ | Try it out → `POST /genres` с `{"name":"поэзия"}` | `201` |
| ☐ | `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/docs/swagger.json` | `200` |

**Все пункты отмечены?** → [step-09-final.md](step-09-final.md)
