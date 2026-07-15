"""In-memory fakes standing in for Cart and Inventory over HTTP, so Order's test
suite stays independently runnable without a real running cart-service /
inventory-service (US-PLT-04's acceptance criterion). Each fake reproduces the
one real-service behavior its tests depend on: Inventory's atomic
check-and-deduct reservation (guarded by a lock, mirroring the real service's
Postgres row-lock atomicity) and idempotent replay by idempotency_key; Cart's
per-user item storage.
"""

import threading
import uuid
from dataclasses import dataclass, field
from decimal import Decimal


class InsufficientStockError(Exception):
    pass


class ReservationNotFoundError(Exception):
    pass


@dataclass
class FakeReservation:
    id: str
    book_id: str
    quantity: int
    status: str


class FakeInventory:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.stock: dict[str, int] = {}
        self.reservations_by_key: dict[str, FakeReservation] = {}
        self.reservations_by_id: dict[str, FakeReservation] = {}

    def set_stock(self, book_id: str, quantity: int) -> None:
        self.stock[book_id] = quantity

    def get_stock(self, book_id: str) -> int:
        return self.stock.get(book_id, 0)

    def reserve(self, *, book_id: str, quantity: int, idempotency_key: str) -> FakeReservation:
        with self._lock:
            existing = self.reservations_by_key.get(idempotency_key)
            if existing is not None:
                return existing

            available = self.stock.get(book_id, 0)
            if available < quantity:
                raise InsufficientStockError(book_id)

            self.stock[book_id] = available - quantity
            reservation = FakeReservation(
                id=str(uuid.uuid4()), book_id=book_id, quantity=quantity, status="reserved"
            )
            self.reservations_by_key[idempotency_key] = reservation
            self.reservations_by_id[reservation.id] = reservation
            return reservation

    def release(self, reservation_id: str) -> FakeReservation:
        with self._lock:
            reservation = self.reservations_by_id.get(reservation_id)
            if reservation is None:
                raise ReservationNotFoundError(reservation_id)
            if reservation.status == "released":
                return reservation
            reservation.status = "released"
            self.stock[reservation.book_id] = self.stock.get(reservation.book_id, 0) + reservation.quantity
            return reservation


@dataclass
class FakeCartItem:
    book_id: str
    title: str
    unit_price: Decimal
    quantity: int


class FakeCart:
    def __init__(self) -> None:
        self._items: dict[str, dict[str, FakeCartItem]] = {}

    def add(self, user_id: str, *, book_id: str, title: str, unit_price: Decimal, quantity: int) -> None:
        self._items.setdefault(user_id, {})[book_id] = FakeCartItem(
            book_id=book_id, title=title, unit_price=unit_price, quantity=quantity
        )

    def get_items(self, user_id: str) -> list[FakeCartItem]:
        return list(self._items.get(user_id, {}).values())

    def clear(self, user_id: str) -> None:
        self._items[user_id] = {}
