"""Catalog's business logic. Reached over HTTP (GET /books, GET /books/{id},
GET /categories, POST /books) per SDD 7.2 by Cart and by external clients -
this file's signatures are the same public boundary the monolith module used.
"""

import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.catalog.internal import repository
from app.modules.catalog.internal.models import Book

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def list_books(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    author: str | None = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> tuple[list[Book], int]:
    page = max(page, 1)
    page_size = min(max(page_size, 1), MAX_PAGE_SIZE)
    return repository.list_books(
        db, query=query, category=category, author=author, page=page, page_size=page_size
    )


def get_book(db: Session, book_id: str) -> Book | None:
    try:
        parsed_id = uuid.UUID(book_id)
    except ValueError:
        return None
    return repository.get_by_id(db, parsed_id)


def list_categories(db: Session) -> list[str]:
    return repository.list_categories(db)


def create_book(
    db: Session,
    *,
    title: str,
    author_name: str,
    category: str,
    price: Decimal,
    isbn: str | None = None,
    cover_image_url: str | None = None,
) -> Book:
    author = repository.get_or_create_author(db, author_name)
    return repository.create_book(
        db,
        title=title,
        author_id=author.id,
        category=category,
        price=price,
        isbn=isbn,
        cover_image_url=cover_image_url,
    )
