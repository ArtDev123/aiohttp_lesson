from aiohttp import web
from aiohttp_swagger3 import SwaggerDocs, SwaggerInfo, SwaggerUiSettings

from app.config import HOST, PORT
from app.db import make_engine, make_session_factory
from app.routes import routes


async def on_startup(app: web.Application) -> None:
    engine = make_engine()
    app["engine"] = engine
    app["session_factory"] = make_session_factory(engine)


async def on_cleanup(app: web.Application) -> None:
    await app["engine"].dispose()


def create_app() -> web.Application:
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)

    # Роуты регистрируем через swagger, иначе UI их не увидит.
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
    return app


def main() -> None:
    web.run_app(create_app(), host=HOST, port=PORT)


if __name__ == "__main__":
    main()
