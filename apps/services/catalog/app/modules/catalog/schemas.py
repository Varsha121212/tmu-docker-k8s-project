import uuid
from decimal import Decimal

from pydantic import BaseModel, Field

from app.modules.catalog.internal.models import Book


class BookOut(BaseModel):
    id: uuid.UUID
    isbn: str | None
    title: str
    author_name: str
    category: str
    price: Decimal
    active: bool
    cover_image_url: str | None

    @classmethod
    def from_model(cls, book: Book) -> "BookOut":
        return cls(
            id=book.id,
            isbn=book.isbn,
            title=book.title,
            author_name=book.author.name,
            category=book.category,
            price=book.price,
            active=book.active,
            cover_image_url=book.cover_image_url,
        )


class PaginatedBooks(BaseModel):
    items: list[BookOut]
    total: int
    page: int
    page_size: int


class BookCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    author_name: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=100)
    price: Decimal = Field(gt=0, decimal_places=2)
    isbn: str | None = Field(default=None, max_length=20)
    cover_image_url: str | None = Field(default=None, max_length=500)
