"""Repeatable initial stock seed: gives every catalog book a starting stock row.

Inventory has no direct access to Catalog's database (SDD 6.1: services must
not query another service's schema directly), so this reads the book list over
HTTP from catalog-service instead of importing its models - the same boundary
every other cross-service call in this project already respects.

Safe to run multiple times - only books without an existing stock row are
touched, so re-running against an already-seeded volume converges to the same
state.

Usage (inside the inventory-service container, working directory /app):
    python -m scripts.seed_stock
"""

import os
import uuid

import httpx

from app.core.db import SessionLocal
from app.modules.inventory.internal.models import Stock
from app.modules.inventory.internal.repository import ensure_stock_row

DEFAULT_INITIAL_QTY = 25
PAGE_SIZE = 100


def _fetch_all_book_ids(catalog_url: str) -> list[uuid.UUID]:
    book_ids: list[uuid.UUID] = []
    page = 1
    with httpx.Client(base_url=catalog_url, timeout=10.0) as client:
        while True:
            response = client.get("/api/books", params={"page": page, "page_size": PAGE_SIZE})
            response.raise_for_status()
            body = response.json()
            book_ids.extend(uuid.UUID(item["id"]) for item in body["items"])
            if len(body["items"]) < PAGE_SIZE:
                break
            page += 1
    return book_ids


def seed() -> None:
    catalog_url = os.environ.get("CATALOG_SERVICE_URL", "http://catalog:8000")
    book_ids = _fetch_all_book_ids(catalog_url)

    db = SessionLocal()
    created = 0
    skipped = 0
    try:
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
