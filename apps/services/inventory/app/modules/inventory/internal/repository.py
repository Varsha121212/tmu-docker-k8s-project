import uuid

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.inventory.internal.models import Reservation, Stock, StockMovement


def get_stock(db: Session, book_id: uuid.UUID) -> Stock | None:
    return db.get(Stock, book_id)


def ensure_stock_row(db: Session, book_id: uuid.UUID, initial_qty: int = 0) -> Stock:
    """Idempotent: creates a zero/initial stock row for a book if one doesn't exist yet."""
    stock = db.get(Stock, book_id)
    if stock is None:
        stock = Stock(book_id=book_id, available_qty=initial_qty, version=0)
        db.add(stock)
        db.commit()
    return stock


def get_reservation_by_idempotency_key(db: Session, idempotency_key: str) -> Reservation | None:
    return db.scalar(select(Reservation).where(Reservation.idempotency_key == idempotency_key))


def get_reservation(db: Session, reservation_id: uuid.UUID) -> Reservation | None:
    return db.get(Reservation, reservation_id)


class InsufficientStockError(Exception):
    pass


def reserve_stock(
    db: Session, *, book_id: uuid.UUID, quantity: int, idempotency_key: str
) -> Reservation:
    existing = get_reservation_by_idempotency_key(db, idempotency_key)
    if existing is not None:
        return existing

    # Single atomic UPDATE with a WHERE guard: Postgres row-locks the target row for the
    # duration of the UPDATE, so concurrent reservations against the same book_id cannot
    # both succeed past the available_qty check - the loser simply matches zero rows.
    result = db.execute(
        update(Stock)
        .where(Stock.book_id == book_id, Stock.available_qty >= quantity)
        .values(available_qty=Stock.available_qty - quantity, version=Stock.version + 1)
    )
    if result.rowcount == 0:
        db.rollback()
        raise InsufficientStockError(book_id)

    # Generated explicitly rather than relying on the model's default=uuid.uuid4, which
    # SQLAlchemy only resolves at flush time - reservation.id would still be None here.
    reservation_id = uuid.uuid4()
    reservation = Reservation(
        id=reservation_id,
        book_id=book_id,
        quantity=quantity,
        idempotency_key=idempotency_key,
        status="reserved",
    )
    db.add(reservation)
    db.add(
        StockMovement(
            book_id=book_id, delta=-quantity, reason="reserve", reference_id=reservation_id
        )
    )
    try:
        db.commit()
    except IntegrityError:
        # Concurrent request raced us on the same idempotency_key and committed first.
        db.rollback()
        existing = get_reservation_by_idempotency_key(db, idempotency_key)
        if existing is not None:
            return existing
        raise
    db.refresh(reservation)
    return reservation


def release_reservation(db: Session, reservation_id: uuid.UUID) -> Reservation | None:
    reservation = db.get(Reservation, reservation_id)
    if reservation is None:
        return None
    if reservation.status == "released":
        return reservation

    # Guarded UPDATE so two concurrent release calls for the same reservation can't both
    # credit stock back - only the one that actually flips reserved -> released proceeds.
    result = db.execute(
        update(Reservation)
        .where(Reservation.id == reservation_id, Reservation.status == "reserved")
        .values(status="released")
    )
    if result.rowcount == 1:
        db.execute(
            update(Stock)
            .where(Stock.book_id == reservation.book_id)
            .values(
                available_qty=Stock.available_qty + reservation.quantity,
                version=Stock.version + 1,
            )
        )
        db.add(
            StockMovement(
                book_id=reservation.book_id,
                delta=reservation.quantity,
                reason="release",
                reference_id=reservation.id,
            )
        )
        db.commit()
    else:
        db.rollback()
    db.refresh(reservation)
    return reservation
