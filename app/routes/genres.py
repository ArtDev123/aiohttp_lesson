from fastapi import APIRouter, status

from app.deps import GenreRepoDep
from app.errors import NotFoundError
from app.schemas import ErrorRead, GenreCreate, GenreRead, GenreUpdate


router = APIRouter(prefix="/genres", tags=["genres"])


@router.get("", response_model=list[GenreRead])
async def list_genres(repo: GenreRepoDep) -> list[GenreRead]:
    genres = await repo.get_all()
    return [GenreRead.model_validate(genre) for genre in genres]


@router.get(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def get_genre(genre_id: int, repo: GenreRepoDep) -> GenreRead:
    genre = await repo.get(genre_id)
    return GenreRead.model_validate(genre)


@router.post(
    "",
    response_model=GenreRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_genre(payload: GenreCreate, repo: GenreRepoDep) -> GenreRead:
    genre = await repo.add(**payload.model_dump())
    return GenreRead.model_validate(genre)


@router.patch(
    "/{genre_id}",
    response_model=GenreRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_genre(
    genre_id: int, payload: GenreUpdate, repo: GenreRepoDep
) -> GenreRead:
    genre = await repo.update(genre_id, **payload.model_dump(exclude_unset=True))
    return GenreRead.model_validate(genre)
