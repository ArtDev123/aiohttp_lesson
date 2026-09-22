from typing import Annotated

from fastapi import APIRouter, status, Depends

from app.deps import BookRepoDep
from app.schemas import BookCreate, BookRead, BookUpdate, ErrorRead, BookFilters

router = APIRouter(prefix="/books", tags=["books"])


@router.get("", response_model=list[BookRead])
async def list_books(
    repo: BookRepoDep,
    filters: Annotated[BookFilters, Depends()],
) -> list[BookRead]:
    books = await repo.get_all(filters)
    return [BookRead.from_book(book) for book in books]


@router.get(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def get_book(book_id: int, repo: BookRepoDep) -> BookRead:
    book = await repo.get(book_id)
    return BookRead.from_book(book)



@router.post(
    "",
    response_model=BookRead,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"model": ErrorRead}},
)
async def create_book(
    payload: BookCreate,
    books_repo: BookRepoDep,
) -> BookRead:
    book = await books_repo.add(**payload.model_dump())

    return BookRead.from_book(book)



@router.patch(
    "/{book_id}",
    response_model=BookRead,
    responses={404: {"model": ErrorRead}},
)
async def patch_book(
    book_id: int,
    payload: BookUpdate,
    books: BookRepoDep,
) -> BookRead:
    data = payload.model_dump(exclude_unset=True)

    book = await books.update(book_id, **data)
    return BookRead.from_book(book)