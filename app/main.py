from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import make_engine, make_session_factory
from app.errors import NotFoundError
from app.routes import register_routes


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    engine = make_engine()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Mini Library API",
        version="1.0.0",
        description="Учебное API библиотеки на FastAPI.",
        lifespan=lifespan,
    )

    @app.exception_handler(NotFoundError)
    async def not_found_handler(
        request: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": exc.message})

    register_routes(app)
    return app


app = create_app()


def main() -> None:
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True,
    )


if __name__ == "__main__":
    main()