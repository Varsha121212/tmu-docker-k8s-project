"""Repeatable, version-controlled catalog seed data (US-CAT-04 / FR-CAT-04).

Safe to run multiple times: skips any (title, author) pair that already exists,
so re-running after a partial failure, or every time `docker compose up` runs
against an already-seeded volume, converges to the same state instead of
duplicating books.

Usage (inside the catalog-service container, working directory /app):
    python -m scripts.seed_catalog
"""

from decimal import Decimal

from sqlalchemy import select

from app.core.db import SessionLocal
from app.modules.catalog.internal.models import Author, Book
from app.modules.catalog.service import create_book

BOOKS: list[dict] = [
    {"title": "The Quiet Algorithm", "author": "Maren Sato", "category": "Fiction", "price": "14.99", "cover": "the-quiet-algorithm.svg"},
    {"title": "Salt and Circuit", "author": "Maren Sato", "category": "Fiction", "price": "16.50", "cover": "salt-and-circuit.svg"},
    {"title": "A Short History of Tomorrow", "author": "Idris Okafor", "category": "History", "price": "22.00", "cover": "a-short-history-of-tomorrow.svg"},
    {"title": "The Cartographer's Silence", "author": "Idris Okafor", "category": "History", "price": "19.75", "cover": "the-cartographers-silence.svg"},
    {"title": "Learning Distributed Systems", "author": "Priya Ramanathan", "category": "Technology", "price": "39.99", "cover": "learning-distributed-systems.svg"},
    {"title": "Kubernetes in Practice", "author": "Priya Ramanathan", "category": "Technology", "price": "44.00", "cover": "kubernetes-in-practice.svg"},
    {"title": "The Grammar of Rivers", "author": "Elin Vosberg", "category": "Poetry", "price": "12.25", "cover": "the-grammar-of-rivers.svg"},
    {"title": "Marginal Notes", "author": "Elin Vosberg", "category": "Poetry", "price": "11.00", "cover": "marginal-notes.svg"},
    {"title": "Field Notes on Gravity", "author": "Tomasz Wren", "category": "Science", "price": "18.40", "cover": "field-notes-on-gravity.svg"},
    {"title": "The Slow Physics of Light", "author": "Tomasz Wren", "category": "Science", "price": "21.30", "cover": "the-slow-physics-of-light.svg"},
    {"title": "Bread, Salt, Ledger", "author": "Naledi Mokoena", "category": "Fiction", "price": "15.20", "cover": "bread-salt-ledger.svg"},
    {"title": "The Understudy's Garden", "author": "Naledi Mokoena", "category": "Fiction", "price": "13.99", "cover": "the-understudys-garden.svg"},
    {"title": "Systems of Trust", "author": "Priya Ramanathan", "category": "Technology", "price": "34.50", "cover": "systems-of-trust.svg"},
    {"title": "An Incomplete Atlas", "author": "Idris Okafor", "category": "History", "price": "24.99", "cover": "an-incomplete-atlas.svg"},
    {"title": "Everything That Floats", "author": "Elin Vosberg", "category": "Poetry", "price": "10.50", "cover": "everything-that-floats.svg"},
    {"title": "The Weight of Small Moons", "author": "Tomasz Wren", "category": "Science", "price": "20.00", "cover": "the-weight-of-small-moons.svg"},
]


def seed() -> None:
    db = SessionLocal()
    created = 0
    skipped = 0
    try:
        for entry in BOOKS:
            author = db.scalar(select(Author).where(Author.name == entry["author"]))
            existing = None
            if author is not None:
                existing = db.scalar(
                    select(Book).where(
                        Book.title == entry["title"], Book.author_id == author.id
                    )
                )
            if existing is not None:
                skipped += 1
                continue

            create_book(
                db,
                title=entry["title"],
                author_name=entry["author"],
                category=entry["category"],
                price=Decimal(entry["price"]),
                cover_image_url=f"/covers/{entry['cover']}",
            )
            created += 1
    finally:
        db.close()

    print(f"Seed complete: {created} book(s) created, {skipped} already present.")


if __name__ == "__main__":
    seed()
