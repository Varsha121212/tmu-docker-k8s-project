"""HTTP client for Order -> Cart (SDD 6.1: Order may reach Cart to read and
clear it during checkout). Forwards the customer's own bearer token, since
Cart's routes are customer-scoped by that token and have no separate
internal-token surface (only Inventory's write endpoints do, per SDD 7.3).
"""

from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings

_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)


@dataclass
class CartItemView:
    book_id: str
    title: str
    unit_price: Decimal
    quantity: int


@dataclass
class CartView:
    items: list[CartItemView]


def get_cart(token: str) -> CartView:
    settings = get_settings()
    with httpx.Client(base_url=settings.cart_service_url, timeout=_TIMEOUT) as client:
        response = client.get("/api/cart", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
    body = response.json()
    items = [
        CartItemView(
            book_id=item["book_id"],
            title=item["title"],
            unit_price=Decimal(str(item["unit_price"])),
            quantity=item["quantity"],
        )
        for item in body["items"]
    ]
    return CartView(items=items)


def clear_cart(token: str) -> None:
    settings = get_settings()
    with httpx.Client(base_url=settings.cart_service_url, timeout=_TIMEOUT) as client:
        response = client.delete("/api/cart", headers={"Authorization": f"Bearer {token}"})
    response.raise_for_status()
