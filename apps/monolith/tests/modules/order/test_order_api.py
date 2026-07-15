"""Tests for the Order module (US-ORD-01..US-ORD-05): checkout orchestration,
price-snapshot persistence, insufficient-stock compensation, idempotency, and
customer-scoped order history.

Traces to: FR-ORD-01..04, BRULE-04, BRULE-06, BRULE-07, BRULE-09, DR-006, FT-06, FT-07,
FT-08, AT-02.
"""

import threading
import uuid
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.redis import get_redis
from app.modules.catalog.internal.models import Author, Book
from app.modules.catalog.service import create_book
from app.modules.inventory.internal.models import Reservation, Stock, StockMovement
from app.modules.inventory.internal.repository import ensure_stock_row
from app.modules.order.internal.models import Order, OrderItem
from app.modules.order import service as order_service


@pytest.fixture()
def redis_client():
    return get_redis()


@pytest.fixture()
def customer(client, redis_client):
    email = f"{uuid.uuid4()}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-1", "display_name": "Order Tester"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    token = login.json()["access_token"]
    user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    yield {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}

    redis_client.delete(f"cart:{user_id}")


@pytest.fixture()
def book(db_session):
    b = create_book(
        db_session,
        title="Order Test Book",
        author_name="Order Test Author",
        category="Fiction",
        price=Decimal("20.00"),
    )
    ensure_stock_row(db_session, b.id, initial_qty=5)
    return b


def _add_to_cart(client, customer, book, quantity):
    return client.post(
        "/api/cart/items",
        json={"book_id": str(book.id), "quantity": quantity},
        headers=customer["headers"],
    )


def _checkout(client, customer, idempotency_key=None):
    return client.post(
        "/api/orders",
        json={"idempotency_key": idempotency_key or str(uuid.uuid4())},
        headers=customer["headers"],
    )


class TestCheckoutHappyPath:
    def test_checkout_creates_order_with_price_snapshot_and_clears_cart(
        self, client, customer, book, db_session
    ):
        _add_to_cart(client, customer, book, 2)

        response = _checkout(client, customer)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "completed"
        assert body["total_amount"] == "40.00"
        assert len(body["items"]) == 1
        assert body["items"][0]["title_snapshot"] == "Order Test Book"
        assert body["items"][0]["unit_price"] == "20.00"
        assert body["items"][0]["quantity"] == 2
        assert body["items"][0]["line_total"] == "40.00"

        cart_response = client.get("/api/cart", headers=customer["headers"])
        assert cart_response.json()["items"] == []

        stock_response = client.get(f"/api/inventory/stock/{book.id}")
        assert stock_response.json()["available_qty"] == 3

    def test_checkout_requires_auth(self, client):
        response = client.post("/api/orders", json={"idempotency_key": str(uuid.uuid4())})
        assert response.status_code == 401


class TestEmptyCart:
    def test_checkout_with_empty_cart_is_400(self, client, customer):
        response = _checkout(client, customer)
        assert response.status_code == 400


class TestInsufficientStock:
    def test_checkout_rejected_and_cart_and_stock_unchanged(self, client, customer, book):
        _add_to_cart(client, customer, book, 10)  # only 5 in stock

        response = _checkout(client, customer)

        assert response.status_code == 409
        stock_response = client.get(f"/api/inventory/stock/{book.id}")
        assert stock_response.json()["available_qty"] == 5

        cart_response = client.get("/api/cart", headers=customer["headers"])
        assert cart_response.json()["items"][0]["quantity"] == 10

    def test_partial_reservation_is_released_on_multi_item_rejection(
        self, client, customer, book, db_session
    ):
        scarce_book = create_book(
            db_session,
            title="Scarce Book",
            author_name="Order Test Author",
            category="Fiction",
            price=Decimal("9.00"),
        )
        ensure_stock_row(db_session, scarce_book.id, initial_qty=1)

        _add_to_cart(client, customer, book, 2)  # plenty of stock, reserves fine
        _add_to_cart(client, customer, scarce_book, 5)  # exceeds stock, fails

        response = _checkout(client, customer)

        assert response.status_code == 409
        # The first item's reservation must be released, not left as a silent deduction.
        first_stock = client.get(f"/api/inventory/stock/{book.id}")
        assert first_stock.json()["available_qty"] == 5
        second_stock = client.get(f"/api/inventory/stock/{scarce_book.id}")
        assert second_stock.json()["available_qty"] == 1


class TestIdempotency:
    def test_retry_with_same_key_returns_same_order_without_double_deduction(
        self, client, customer, book
    ):
        _add_to_cart(client, customer, book, 1)
        key = str(uuid.uuid4())

        first = _checkout(client, customer, idempotency_key=key)
        # Re-add the same item, simulating a client that retries the whole request
        # after a network blip without knowing whether the first attempt landed.
        second = _checkout(client, customer, idempotency_key=key)

        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        stock_response = client.get(f"/api/inventory/stock/{book.id}")
        assert stock_response.json()["available_qty"] == 4  # deducted once, not twice


class TestOrderHistory:
    def test_list_returns_only_own_orders(self, client, customer, book):
        _add_to_cart(client, customer, book, 1)
        _checkout(client, customer)

        other_email = f"{uuid.uuid4()}@example.com"
        client.post(
            "/api/auth/register",
            json={"email": other_email, "password": "correct-horse-1", "display_name": "Other"},
        )
        other_login = client.post(
            "/api/auth/login", json={"email": other_email, "password": "correct-horse-1"}
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        own_list = client.get("/api/orders", headers=customer["headers"]).json()
        other_list = client.get("/api/orders", headers=other_headers).json()

        assert len(own_list) == 1
        assert other_list == []

    def test_cannot_view_another_customers_order(self, client, customer, book):
        _add_to_cart(client, customer, book, 1)
        order_id = _checkout(client, customer).json()["id"]

        other_email = f"{uuid.uuid4()}@example.com"
        client.post(
            "/api/auth/register",
            json={"email": other_email, "password": "correct-horse-1", "display_name": "Other"},
        )
        other_login = client.post(
            "/api/auth/login", json={"email": other_email, "password": "correct-horse-1"}
        )
        other_headers = {"Authorization": f"Bearer {other_login.json()['access_token']}"}

        response = client.get(f"/api/orders/{order_id}", headers=other_headers)
        assert response.status_code == 404

    def test_get_unknown_order_is_404(self, client, customer):
        response = client.get(f"/api/orders/{uuid.uuid4()}", headers=customer["headers"])
        assert response.status_code == 404


class TestPriceSnapshot:
    def test_order_keeps_original_price_after_catalog_price_changes(
        self, client, customer, book, db_session
    ):
        _add_to_cart(client, customer, book, 1)
        order_id = _checkout(client, customer).json()["id"]

        book.price = Decimal("999.99")
        db_session.commit()

        response = client.get(f"/api/orders/{order_id}", headers=customer["headers"])
        assert response.json()["items"][0]["unit_price"] == "20.00"


def test_health_ready_reports_database_connectivity(client):
    response = client.get("/api/orders/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


class TestConcurrentCheckout:
    """Proves the IntegrityError-catch-and-return-existing path actually prevents a
    duplicate order under real concurrent access (US-ORD-04 AC2), not just sequential
    retries sharing one transaction. Bypasses the per-test rollback fixture for the
    same reason as the Inventory concurrency test - cleans up everything it commits.
    """

    def test_two_concurrent_checkouts_with_same_key_produce_one_order(self):
        engine = create_engine(get_settings().database_url)
        # expire_on_commit=False matches app.core.db.SessionLocal - without it, `b.id`
        # becomes inaccessible the moment setup_db closes (attributes expire on commit
        # by SQLAlchemy's default and can't be reloaded from a detached instance).
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        redis_client = get_redis()

        setup_db = session_factory()
        try:
            b = create_book(
                setup_db,
                title="Concurrency Test Book",
                author_name="Concurrency Author",
                category="Fiction",
                price=Decimal("15.00"),
            )
            ensure_stock_row(setup_db, b.id, initial_qty=10)
        finally:
            setup_db.close()

        user_id = str(uuid.uuid4())
        redis_client.hset(f"cart:{user_id}", str(b.id), 2)
        idempotency_key = str(uuid.uuid4())
        results: dict[str, object] = {}

        def attempt(label: str) -> None:
            db = session_factory()
            try:
                order = order_service.checkout(
                    db, redis_client, user_id=user_id, idempotency_key=idempotency_key
                )
                results[label] = order.id
            finally:
                db.close()

        try:
            t1 = threading.Thread(target=attempt, args=("first",))
            t2 = threading.Thread(target=attempt, args=("second",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            assert results["first"] == results["second"]

            verify_db = session_factory()
            try:
                orders = (
                    verify_db.query(Order)
                    .filter(Order.idempotency_key == idempotency_key)
                    .all()
                )
                assert len(orders) == 1

                stock = verify_db.get(Stock, b.id)
                assert stock.available_qty == 8  # 10 - 2, deducted exactly once
            finally:
                verify_db.close()
        finally:
            cleanup_db = session_factory()
            try:
                cleanup_db.execute(
                    delete(OrderItem).where(
                        OrderItem.order_id.in_(
                            cleanup_db.query(Order.id).filter(
                                Order.idempotency_key == idempotency_key
                            )
                        )
                    )
                )
                cleanup_db.execute(delete(Order).where(Order.idempotency_key == idempotency_key))
                cleanup_db.execute(delete(StockMovement).where(StockMovement.book_id == b.id))
                cleanup_db.execute(delete(Reservation).where(Reservation.book_id == b.id))
                cleanup_db.execute(delete(Stock).where(Stock.book_id == b.id))
                cleanup_db.execute(delete(Book).where(Book.id == b.id))
                cleanup_db.execute(delete(Author).where(Author.id == b.author_id))
                cleanup_db.commit()
            finally:
                cleanup_db.close()
            redis_client.delete(f"cart:{user_id}")
