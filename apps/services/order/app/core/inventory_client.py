"""HTTP client for Order -> Inventory (SDD 6.1: Order orchestrates checkout via
Inventory's reserve/release). Sends the shared internal service token (SDD 7.3)
instead of the customer's JWT - these are internal-only endpoints.
"""

import uuid
from dataclasses import dataclass

import httpx

from app.core.config import get_settings

_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)


class InsufficientStockError(Exception):
    pass


@dataclass
class ReservationView:
    id: str
    book_id: str
    quantity: int
    status: str


def _headers() -> dict[str, str]:
    return {"X-Internal-Token": get_settings().internal_service_token}


def reserve(*, book_id: uuid.UUID, quantity: int, idempotency_key: str) -> ReservationView:
    settings = get_settings()
    with httpx.Client(base_url=settings.inventory_service_url, timeout=_TIMEOUT) as client:
        response = client.post(
            "/api/inventory/reserve",
            json={
                "book_id": str(book_id),
                "quantity": quantity,
                "idempotency_key": idempotency_key,
            },
            headers=_headers(),
        )
    if response.status_code == 409:
        raise InsufficientStockError(book_id)
    response.raise_for_status()
    body = response.json()
    return ReservationView(
        id=body["id"], book_id=body["book_id"], quantity=body["quantity"], status=body["status"]
    )


def release(reservation_id: str) -> ReservationView:
    settings = get_settings()
    with httpx.Client(base_url=settings.inventory_service_url, timeout=_TIMEOUT) as client:
        response = client.post(
            "/api/inventory/release",
            json={"reservation_id": reservation_id},
            headers=_headers(),
        )
    response.raise_for_status()
    body = response.json()
    return ReservationView(
        id=body["id"], book_id=body["book_id"], quantity=body["quantity"], status=body["status"]
    )
