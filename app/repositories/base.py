from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.errors import NotFoundError

ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class BaseRepository(Generic[ModelType]):
    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> Sequence[ModelType]:
        result = await self._session.execute(select(self.model).order_by(self.model.id))
        return result.scalars().all()

    async def get(self, id: int) -> ModelType | None:
        object = await self._session.get(self.model, id)
        if object is None:
            raise NotFoundError(f"{self.model.__name__} with id {id} not found")
        return object

    async def add(self, **fields: Any) -> ModelType:
        object = self.model(**fields)
        self._session.add(object)
        await self._session.commit()
        await self._session.refresh(object)
        return object

    async def update(self, id: int, **fields: Any) -> ModelType | None:
        object = await self.get(id)
        if object is None:
            raise NotFoundError(f'{self.model.__name__} with id {id} not found')

        for key, value in fields.items():
            setattr(object, key, value)

        await self._session.commit()
        await self._session.refresh(object)
        return object
