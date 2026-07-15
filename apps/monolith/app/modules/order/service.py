"""Public boundary for the Order module, and the checkout orchestrator (US-ORD-01..04).

This is the first module that calls three other modules' public boundaries in one
operation: Cart (read + clear), Catalog (via Cart's own pricing), and Inventory
(reserve/release). All calls go through app.modules.<name>.service, never .internal -
the same rule enforced everywhere else, checked here by the same import-linter contracts.
"""

import uuid

import redis
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.cart import service as cart_service
from app.modules.inventory import service as inventory_service
from app.modules.order.internal import repository
from app.modules.order.internal.models import Order
from app.modules.order.internal.repository import LineItemInput


class EmptyCartError(Exception):
    pass


class CheckoutRejectedError(Exception):
    """Raised when checkout cannot proceed (e.g. insufficient stock on one or more items).
    No order is created and no net inventory is deducted."""


def checkout(
    db: Session, redis_client: redis.Redis, *, user_id: str, idempotency_key: str
) -> Order:
    existing = repository.get_by_idempotency_key(db, idempotency_key)
    if existing is not None:
        return existing

    cart = cart_service.get_cart(redis_client, db, user_id=user_id)
    if not cart.items:
        raise EmptyCartError()

    # Each item's reservation idempotency_key is deterministically derived from the
    # order's own idempotency_key, so a concurrent retry of the *whole* checkout
    # converges on Inventory's own idempotent-replay behavior (same reservation
    # returned, not double-reserved) rather than needing separate dedup logic here.
    reservations = []
    try:
        for item in cart.items:
            reservation = inventory_service.reserve(
                db,
                book_id=uuid.UUID(item.book_id),
                quantity=item.quantity,
                idempotency_key=f"{idempotency_key}:{item.book_id}",
            )
            reservations.append(reservation)
    except inventory_service.InsufficientStockError as exc:
        # Compensate: release whatever this attempt did manage to reserve before the
        # failure, so a rejected checkout never leaves a partial net deduction (US-ORD-03).
        for reservation in reservations:
            inventory_service.release(db, reservation.id)
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

    cart_service.clear_cart(redis_client, user_id=user_id)
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
