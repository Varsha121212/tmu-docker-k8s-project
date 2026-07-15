"""Order's business logic and the checkout orchestrator (US-ORD-01..04).

Reaches Cart and Inventory over HTTP (app.core.cart_client /
app.core.inventory_client) instead of in-process calls - the same
orchestration sequence the monolith used, now across process boundaries
(SDD 6.2: synchronous HTTP/JSON internal calls, Order as checkout orchestrator).
"""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import cart_client, inventory_client
from app.modules.order.internal import repository
from app.modules.order.internal.models import Order
from app.modules.order.internal.repository import LineItemInput


class EmptyCartError(Exception):
    pass


class CheckoutRejectedError(Exception):
    """Raised when checkout cannot proceed (e.g. insufficient stock on one or more items).
    No order is created and no net inventory is deducted."""


def checkout(db: Session, *, user_id: str, token: str, idempotency_key: str) -> Order:
    existing = repository.get_by_idempotency_key(db, idempotency_key)
    if existing is not None:
        return existing

    cart = cart_client.get_cart(token)
    if not cart.items:
        raise EmptyCartError()

    # Each item's reservation idempotency_key is deterministically derived from the
    # order's own idempotency_key, so a concurrent retry of the *whole* checkout
    # converges on Inventory's own idempotent-replay behavior (same reservation
    # returned, not double-reserved) rather than needing separate dedup logic here.
    reservations = []
    try:
        for item in cart.items:
            reservation = inventory_client.reserve(
                book_id=uuid.UUID(item.book_id),
                quantity=item.quantity,
                idempotency_key=f"{idempotency_key}:{item.book_id}",
            )
            reservations.append(reservation)
    except inventory_client.InsufficientStockError as exc:
        # Compensate: release whatever this attempt did manage to reserve before the
        # failure, so a rejected checkout never leaves a partial net deduction (US-ORD-03).
        for reservation in reservations:
            inventory_client.release(reservation.id)
        raise CheckoutRejectedError("Insufficient stock") from exc

    line_items = [
        LineItemInput(
            book_id=uuid.UUID(item.book_id),
            title=item.title,
            unit_price=item.unit_price,
            quantity=item.quantity,
        )
        for item in cart.items
    ]

    try:
        order = repository.create_order(
            db, user_id=uuid.UUID(user_id), idempotency_key=idempotency_key, line_items=line_items
        )
    except IntegrityError:
        # A concurrent request with the same idempotency_key committed its order first.
        # The reservations above are safe either way - they were made with idempotency
        # keys derived from the same order key, so both attempts reserved the same stock
        # exactly once (Inventory's own idempotent replay), not twice.
        db.rollback()
        existing = repository.get_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing
        raise

    cart_client.clear_cart(token)
    return order


def get_order_for_user(db: Session, *, user_id: str, order_id: str) -> Order | None:
    try:
        parsed_id = uuid.UUID(order_id)
    except ValueError:
        return None
    order = repository.get_by_id(db, parsed_id)
    if order is None or str(order.user_id) != user_id:
        return None
    return order


def list_orders_for_user(db: Session, *, user_id: str) -> list[Order]:
    return repository.list_for_user(db, uuid.UUID(user_id))
