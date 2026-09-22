from fastapi import APIRouter, FastAPI

from app.db import SessionDep
from app.routes import authors, books, genres, exports


def health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    async def health(session: SessionDep) -> dict[str, str]:
        return {"status": "ok"}

    return router


def register_routes(app: FastAPI) -> None:
    app.include_router(health_router())
    app.include_router(genres.router)
    app.include_router(authors.router)
    app.include_router(books.router)
    app.include_router(exports.router)
