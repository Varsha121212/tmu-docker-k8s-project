"""HTTP client for Cart -> Catalog (SDD 6.1: Cart may call catalog for
price/details). Replaces the monolith's in-process `catalog_service.get_book`
call - same contract (GET /books/{id}), now over the wire.
"""

from dataclasses import dataclass
from decimal import Decimal

import httpx

from app.core.config import get_settings

# SDD 7.6: 2s connect / 5s read timeout target for internal calls.
_TIMEOUT = httpx.Timeout(connect=2.0, read=5.0, write=5.0, pool=5.0)


@dataclass
class BookView:
    id: str
    title: str
    author_name: str
    price: Decimal


def get_book(book_id: str) -> BookView | None:
    settings = get_settings()
    with httpx.Client(base_url=settings.catalog_service_url, timeout=_TIMEOUT) as client:
        response = client.get(f"/api/books/{book_id}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    body = response.json()
    return BookView(
        id=body["id"],
        title=body["title"],
        author_name=body["author_name"],
        price=Decimal(str(body["price"])),
    )
