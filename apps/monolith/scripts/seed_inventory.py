"""Repeatable initial stock seed: gives every catalog book a starting stock row.

Safe to run multiple times - only books without an existing stock row are touched.

Usage (from apps/monolith):
    .venv/Scripts/python.exe -m scripts.seed_inventory
"""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.catalog.internal.models import Book
from app.modules.inventory.internal.models import Stock
from app.modules.inventory.internal.repository import ensure_stock_row

DEFAULT_INITIAL_QTY = 25


def seed() -> None:
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        book_ids = db.scalars(select(Book.id)).all()
        for book_id in book_ids:
            if db.get(Stock, book_id) is not None:
                skipped += 1
                continue
            ensure_stock_row(db, book_id, initial_qty=DEFAULT_INITIAL_QTY)
            created += 1
    finally:
        db.close()

    print(f"Seed complete: {created} stock row(s) created, {skipped} already present.")


if __name__ == "__main__":
    seed()
