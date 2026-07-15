from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user_id
from app.modules.catalog import service
from app.modules.catalog.schemas import BookCreate, BookOut, PaginatedBooks

router = APIRouter(prefix="/api/books", tags=["catalog"])


@router.get("/health/ready")
def health_ready(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable"
        ) from exc
    return {"status": "ready"}


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)) -> list[str]:
    return service.list_categories(db)


@router.get("", response_model=PaginatedBooks)
def list_books(
    q: str | None = Query(default=None, max_length=300, description="Search by title"),
    category: str | None = Query(default=None, max_length=100),
    author: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedBooks:
    items, total = service.list_books(
        db, query=q, category=category, author=author, page=page, page_size=page_size
    )
    return PaginatedBooks(
        items=[BookOut.from_model(book) for book in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: str, db: Session = Depends(get_db)) -> BookOut:
    book = service.get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return BookOut.from_model(book)


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(
    payload: BookCreate,
    db: Session = Depends(get_db),
    # SDD 7.2 / BRD BRULE-10: demo/seed writes must be protected, not publicly anonymous.
    # No admin role exists yet, so "any authenticated user" is the Stage 1 stand-in.
    _current_user_id: str = Depends(get_current_user_id),
) -> BookOut:
    book = service.create_book(
        db,
        title=payload.title,
        author_name=payload.author_name,
        category=payload.category,
        price=payload.price,
        isbn=payload.isbn,
        cover_image_url=payload.cover_image_url,
    )
    return BookOut.from_model(book)
