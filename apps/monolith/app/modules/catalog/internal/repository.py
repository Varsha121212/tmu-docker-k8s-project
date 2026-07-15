import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.catalog.internal.models import Author, Book


def list_books(
    db: Session,
    *,
    query: str | None,
    category: str | None,
    author: str | None,
    page: int,
    page_size: int,
) -> tuple[list[Book], int]:
    stmt = select(Book).join(Author).where(Book.active.is_(True))

    if query:
        like = f"%{query}%"
        stmt = stmt.where(Book.title.ilike(like))
    if category:
        stmt = stmt.where(Book.category == category)
    if author:
        stmt = stmt.where(Author.name.ilike(f"%{author}%"))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(Book.title).offset((page - 1) * page_size).limit(page_size)
    items = list(db.scalars(stmt).all())
    return items, total


def get_by_id(db: Session, book_id: uuid.UUID) -> Book | None:
    return db.get(Book, book_id)


def list_categories(db: Session) -> list[str]:
    stmt = select(Book.category).distinct().where(Book.active.is_(True)).order_by(Book.category)
    return list(db.scalars(stmt).all())


def get_or_create_author(db: Session, name: str) -> Author:
    author = db.scalar(select(Author).where(Author.name == name))
    if author is None:
        author = Author(name=name)
        db.add(author)
        db.flush()
    return author


def create_book(
    db: Session,
    *,
    title: str,
    author_id: uuid.UUID,
    category: str,
    price: Decimal,
    isbn: str | None = None,
    cover_image_url: str | None = None,
) -> Book:
    book = Book(
        title=title,
        author_id=author_id,
        category=category,
        price=price,
        isbn=isbn,
        cover_image_url=cover_image_url,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book
