"""Public boundary for the Cart module.

Order must call these functions - never app.modules.cart.internal directly - to clear a
cart after a successful checkout. When Cart is extracted into its own service, these
signatures become the HTTP contract (GET /, POST /items, PATCH/DELETE /items/{book_id}, DELETE /).

Pricing/existence checks call app.modules.catalog.service, never catalog.internal - this is
the first in-process cross-module call in the monolith, and it goes through the same public
boundary that will become an HTTP call to catalog-service once Cart is extracted.
"""

from dataclasses import dataclass
from decimal import Decimal

import redis
from sqlalchemy.orm import Session

from app.modules.cart.internal import repository
from app.modules.catalog import service as catalog_service


class BookNotFoundError(Exception):
    pass


class ItemNotInCartError(Exception):
    pass


@dataclass
class CartItemView:
    book_id: str
    title: str
    author_name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


@dataclass
class CartView:
    items: list[CartItemView]
    total: Decimal


def add_item(
    redis_client: redis.Redis, db: Session, *, user_id: str, book_id: str, quantity: int
) -> None:
    book = catalog_service.get_book(db, book_id)
    if book is None:
        raise BookNotFoundError(book_id)
    repository.set_item(redis_client, user_id, book_id, quantity)


def update_item(
    redis_client: redis.Redis, *, user_id: str, book_id: str, quantity: int
) -> None:
    if not repository.item_exists(redis_client, user_id, book_id):
        raise ItemNotInCartError(book_id)
    repository.set_item(redis_client, user_id, book_id, quantity)


def remove_item(redis_client: redis.Redis, *, user_id: str, book_id: str) -> None:
    removed = repository.remove_item(redis_client, user_id, book_id)
    if not removed:
        raise ItemNotInCartError(book_id)


def get_cart(redis_client: redis.Redis, db: Session, *, user_id: str) -> CartView:
    raw_items = repository.get_items(redis_client, user_id)
    items: list[CartItemView] = []
    total = Decimal("0")

    for book_id, quantity in raw_items.items():
        book = catalog_service.get_book(db, book_id)
        if book is None:
            # Book was removed from the catalog after being added to a cart. Skipping it
            # is a deliberate simplification (not covered by any acceptance criteria);
            # Order's checkout validation (US-ORD-01) is the actual point that must catch this.
            continue
        line_total = book.price * quantity
        items.append(
            CartItemView(
                book_id=book_id,
                title=book.title,
                author_name=book.author.name,
                unit_price=book.price,
                quantity=quantity,
                line_total=line_total,
            )
        )
        total += line_total

    return CartView(items=items, total=total)


def clear_cart(redis_client: redis.Redis, *, user_id: str) -> None:
    repository.clear(redis_client, user_id)
