from fastapi import APIRouter, status

from app.deps import AuthorRepoDep
from app.errors import NotFoundError
from app.schemas import AuthorCreate, AuthorRead, AuthorUpdate, ErrorRead

router = APIRouter(prefix="/authors", tags=["authors"])


@router.get("", response_model=list[AuthorRead])
async def list_authors(repo: AuthorRepoDep) -> list[AuthorRead]:
    authors = await repo.get_all()
    return [AuthorRead.model_validate(author) for author in authors]


@router.get(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def get_author(author_id: int, repo: AuthorRepoDep) -> AuthorRead:
    author = await repo.get(author_id)
    return AuthorRead.model_validate(author)


@router.post(
    "",
    response_model=AuthorRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_author(payload: AuthorCreate, repo: AuthorRepoDep) -> AuthorRead:
    author = await repo.add(**payload.model_dump())
    return AuthorRead.model_validate(author)


@router.patch(
    "/{author_id}",
    response_model=AuthorRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_author(
    author_id: int, payload: AuthorUpdate, repo: AuthorRepoDep
) -> AuthorRead:
    author = await repo.update(author_id, **payload.model_dump(exclude_unset=True))
    return AuthorRead.model_validate(author)