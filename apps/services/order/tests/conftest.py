import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app
from tests.fakes import FakeCart, FakeInventory, InsufficientStockError, ReservationNotFoundError

_engine = create_engine(get_settings().database_url)
_TestingSessionLocal = sessionmaker(bind=_engine)


def make_test_jwt(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=30)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture()
def db_session():
    """Each test runs inside an outer transaction that is always rolled back,
    so tests exercise the real Postgres schema/constraints without leaving
    data behind in the shared local dev database.
    """
    connection = _engine.connect()
    outer_transaction = connection.begin()
    session = _TestingSessionLocal(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer_transaction.rollback()
        connection.close()


@pytest.fixture()
def fake_cart():
    return FakeCart()


@pytest.fixture()
def fake_inventory():
    return FakeInventory()


@pytest.fixture()
def mock_services(fake_cart, fake_inventory):
    """Wires app.core.cart_client / app.core.inventory_client's HTTP calls to the
    in-memory fakes, so this service's tests don't require a running
    cart-service / inventory-service (US-PLT-04's acceptance criterion).
    """
    settings = get_settings()

    def _user_id_from_auth_header(request: httpx.Request) -> str:
        token = request.headers["authorization"].removeprefix("Bearer ")
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload["sub"]

    def _get_cart(request: httpx.Request) -> httpx.Response:
        user_id = _user_id_from_auth_header(request)
        items = fake_cart.get_items(user_id)
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "book_id": i.book_id,
                        "title": i.title,
                        "author_name": "Test Author",
                        "unit_price": str(i.unit_price),
                        "quantity": i.quantity,
                        "line_total": str(i.unit_price * i.quantity),
                    }
                    for i in items
                ],
                "total": str(sum((i.unit_price * i.quantity for i in items), start=0)),
            },
        )

    def _clear_cart(request: httpx.Request) -> httpx.Response:
        user_id = _user_id_from_auth_header(request)
        fake_cart.clear(user_id)
        return httpx.Response(204)

    def _reserve(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        try:
            reservation = fake_inventory.reserve(
                book_id=body["book_id"],
                quantity=body["quantity"],
                idempotency_key=body["idempotency_key"],
            )
        except InsufficientStockError:
            return httpx.Response(409, json={"message": "Insufficient stock"})
        return httpx.Response(
            201,
            json={
                "id": reservation.id,
                "book_id": reservation.book_id,
                "quantity": reservation.quantity,
                "status": reservation.status,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    def _release(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        try:
            reservation = fake_inventory.release(body["reservation_id"])
        except ReservationNotFoundError:
            return httpx.Response(404, json={"message": "Reservation not found"})
        return httpx.Response(
            200,
            json={
                "id": reservation.id,
                "book_id": reservation.book_id,
                "quantity": reservation.quantity,
                "status": reservation.status,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    with respx.mock(assert_all_called=False) as mock:
        mock.get(f"{settings.cart_service_url}/api/cart").mock(side_effect=_get_cart)
        mock.delete(f"{settings.cart_service_url}/api/cart").mock(side_effect=_clear_cart)
        mock.post(f"{settings.inventory_service_url}/api/inventory/reserve").mock(
            side_effect=_reserve
        )
        mock.post(f"{settings.inventory_service_url}/api/inventory/release").mock(
            side_effect=_release
        )
        yield mock


@pytest.fixture()
def client(db_session, mock_services):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def customer():
    user_id = str(uuid.uuid4())
    token = make_test_jwt(subject=user_id)
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}


@pytest.fixture()
def book(fake_inventory):
    book_id = str(uuid.uuid4())
    fake_inventory.set_stock(book_id, 5)
    return {"id": book_id, "title": "Order Test Book", "price": 20}
