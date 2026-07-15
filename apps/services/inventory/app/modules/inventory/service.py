"""Inventory's business logic. Reached over HTTP (GET /stock/{id}, POST /reserve,
POST /release) per SDD 7.3 - reserve/release are internal-only, guarded by
app.core.internal_auth, since Order is now their only caller.
"""

import uuid

from sqlalchemy.orm import Session

from app.modules.inventory.internal import repository
from app.modules.inventory.internal.models import Reservation

InsufficientStockError = repository.InsufficientStockError


class ReservationNotFoundError(Exception):
    pass


def get_available_quantity(db: Session, book_id: uuid.UUID) -> tuple[int, int]:
    """Returns (available_qty, version). A book with no stock row is treated as
    zero-available rather than an error (US-INV-01: zero stock is not an error)."""
    stock = repository.get_stock(db, book_id)
    if stock is None:
        return 0, 0
    return stock.available_qty, stock.version


def reserve(db: Session, *, book_id: uuid.UUID, quantity: int, idempotency_key: str) -> Reservation:
    return repository.reserve_stock(
        db, book_id=book_id, quantity=quantity, idempotency_key=idempotency_key
    )


def release(db: Session, reservation_id: uuid.UUID) -> Reservation:
    reservation = repository.release_reservation(db, reservation_id)
    if reservation is None:
        raise ReservationNotFoundError(reservation_id)
    return reservation
