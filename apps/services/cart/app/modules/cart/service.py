"""Cart's business logic. Reached over HTTP (GET /, POST /items, PATCH/DELETE
/items/{id}, DELETE /) per SDD 7.4 by Order (read + clear) and external
clients. Pricing/existence checks now call app.core.catalog_client - an HTTP
call to catalog-service - replacing the monolith's in-process
catalog_service.get_book call. Same public boundary, now over the wire.
"""

from dataclasses import dataclass
from decimal import Decimal

import redis

from app.core import catalog_client
from app.modules.cart.internal import repository


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


def add_item(redis_client: redis.Redis, *, user_id: str, book_id: str, quantity: int) -> None:
    book = catalog_client.get_book(book_id)
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


def get_cart(redis_client: redis.Redis, *, user_id: str) -> CartView:
    raw_items = repository.get_items(redis_client, user_id)
    items: list[CartItemView] = []
    total = Decimal("0")

    for book_id, quantity in raw_items.items():
        book = catalog_client.get_book(book_id)
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
                author_name=book.author_name,
                unit_price=book.price,
                quantity=quantity,
                line_total=line_total,
            )
        )
        total += line_total

    return CartView(items=items, total=total)


def clear_cart(redis_client: redis.Redis, *, user_id: str) -> None:
    repository.clear(redis_client, user_id)
