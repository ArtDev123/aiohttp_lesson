from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import SessionDep, make_engine, make_session_factory
from app.errors import NotFoundError


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    print("before yield")
    engine = make_engine()
    app.state.engine = engine
    app.state.session_factory = make_session_factory(engine)
    yield
    print("after yield")
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

    @app.get("/health")
    async def health(session: SessionDep) -> dict[str, str]:
        print(session)
        return {"status": "ok"}

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
