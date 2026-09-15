from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Genre(Base):
    __tablename__ = "genres"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)

    books: Mapped[list["Book"]] = relationship(back_populates="genre")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}


class Author(Base):
    __tablename__ = "authors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)

    books: Mapped[list["Book"]] = relationship(back_populates="author")

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "bio": self.bio}


class Book(Base):
    __tablename__ = "books"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("authors.id"))
    genre_id: Mapped[int] = mapped_column(ForeignKey("genres.id"))

    author: Mapped[Author] = relationship(back_populates="books")
    genre: Mapped[Genre] = relationship(back_populates="books")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "author_id": self.author_id,
            "genre_id": self.genre_id,
            "author": self.author.name if self.author else None,
            "genre": self.genre.name if self.genre else None,
        }
