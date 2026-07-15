"""Tests for the Order service (US-ORD-01..US-ORD-05): checkout orchestration,
price-snapshot persistence, insufficient-stock compensation, idempotency, and
customer-scoped order history.

Traces to: FR-ORD-01..04, BRULE-04, BRULE-06, BRULE-07, BRULE-09, DR-006, FT-06, FT-07,
FT-08, AT-02.

Cart and Inventory are mocked at the HTTP boundary (tests/fakes.py + conftest's
mock_services fixture) rather than requiring running services - this service's
tests stay independently runnable per US-PLT-04's acceptance criterion.
"""

import threading
import uuid
from decimal import Decimal

import respx
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.order.internal.models import Order, OrderItem
from app.modules.order import service as order_service


def _add_to_cart(fake_cart, customer, book, quantity):
    fake_cart.add(
        customer["user_id"],
        book_id=book["id"],
        title=book["title"],
        unit_price=Decimal(str(book["price"])),
        quantity=quantity,
    )


def _checkout(client, customer, idempotency_key=None):
    return client.post(
        "/api/orders",
        json={"idempotency_key": idempotency_key or str(uuid.uuid4())},
        headers=customer["headers"],
    )


class TestCheckoutHappyPath:
    def test_checkout_creates_order_with_price_snapshot_and_clears_cart(
        self, client, customer, book, fake_cart, fake_inventory
    ):
        _add_to_cart(fake_cart, customer, book, 2)

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

        assert fake_cart.get_items(customer["user_id"]) == []
        assert fake_inventory.get_stock(book["id"]) == 3

    def test_checkout_requires_auth(self, client):
        response = client.post("/api/orders", json={"idempotency_key": str(uuid.uuid4())})
        assert response.status_code == 401


class TestEmptyCart:
    def test_checkout_with_empty_cart_is_400(self, client, customer):
        response = _checkout(client, customer)
        assert response.status_code == 400


class TestInsufficientStock:
    def test_checkout_rejected_and_stock_unchanged(self, client, customer, book, fake_cart, fake_inventory):
        _add_to_cart(fake_cart, customer, book, 10)  # only 5 in stock

        response = _checkout(client, customer)

        assert response.status_code == 409
        assert fake_inventory.get_stock(book["id"]) == 5

    def test_partial_reservation_is_released_on_multi_item_rejection(
        self, client, customer, book, fake_cart, fake_inventory
    ):
        scarce_book = {"id": str(uuid.uuid4()), "title": "Scarce Book", "price": 9}
        fake_inventory.set_stock(scarce_book["id"], 1)

        _add_to_cart(fake_cart, customer, book, 2)  # plenty of stock, reserves fine
        _add_to_cart(fake_cart, customer, scarce_book, 5)  # exceeds stock, fails

        response = _checkout(client, customer)

        assert response.status_code == 409
        # The first item's reservation must be released, not left as a silent deduction.
        assert fake_inventory.get_stock(book["id"]) == 5
        assert fake_inventory.get_stock(scarce_book["id"]) == 1


class TestIdempotency:
    def test_retry_with_same_key_returns_same_order_without_double_deduction(
        self, client, customer, book, fake_cart, fake_inventory
    ):
        _add_to_cart(fake_cart, customer, book, 1)
        key = str(uuid.uuid4())

        first = _checkout(client, customer, idempotency_key=key)
        # Re-add the same item, simulating a client that retries the whole request
        # after a network blip without knowing whether the first attempt landed.
        _add_to_cart(fake_cart, customer, book, 1)
        second = _checkout(client, customer, idempotency_key=key)

        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]
        assert fake_inventory.get_stock(book["id"]) == 4  # deducted once, not twice


class TestOrderHistory:
    def test_list_returns_only_own_orders(self, client, customer, book, fake_cart):
        _add_to_cart(fake_cart, customer, book, 1)
        _checkout(client, customer)

        other_user_id = str(uuid.uuid4())
        from tests.conftest import make_test_jwt

        other_headers = {"Authorization": f"Bearer {make_test_jwt(other_user_id)}"}

        own_list = client.get("/api/orders", headers=customer["headers"]).json()
        other_list = client.get("/api/orders", headers=other_headers).json()

        assert len(own_list) == 1
        assert other_list == []

    def test_cannot_view_another_customers_order(self, client, customer, book, fake_cart):
        _add_to_cart(fake_cart, customer, book, 1)
        order_id = _checkout(client, customer).json()["id"]

        from tests.conftest import make_test_jwt

        other_headers = {"Authorization": f"Bearer {make_test_jwt(str(uuid.uuid4()))}"}

        response = client.get(f"/api/orders/{order_id}", headers=other_headers)
        assert response.status_code == 404

    def test_get_unknown_order_is_404(self, client, customer):
        response = client.get(f"/api/orders/{uuid.uuid4()}", headers=customer["headers"])
        assert response.status_code == 404


class TestPriceSnapshot:
    def test_order_keeps_price_at_checkout_time(self, client, customer, book, fake_cart):
        """Order stores title_snapshot/unit_price on its own row at checkout time and
        never re-reads Catalog afterward - re-fetching the same order must keep
        returning that frozen price regardless of what Catalog's live price is now."""
        _add_to_cart(fake_cart, customer, book, 1)
        order_id = _checkout(client, customer).json()["id"]

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

    def test_two_concurrent_checkouts_with_same_key_produce_one_order(
        self, fake_cart, fake_inventory, mock_services
    ):
        settings = get_settings()
        engine = create_engine(settings.database_url)
        session_factory = sessionmaker(bind=engine, expire_on_commit=False)

        book_id = str(uuid.uuid4())
        fake_inventory.set_stock(book_id, 10)

        user_id = str(uuid.uuid4())
        from tests.conftest import make_test_jwt

        token = make_test_jwt(user_id)
        fake_cart.add(
            user_id, book_id=book_id, title="Concurrency Test Book", unit_price=Decimal("15.00"), quantity=2
        )
        idempotency_key = str(uuid.uuid4())
        results: dict[str, object] = {}

        def attempt(label: str) -> None:
            db = session_factory()
            try:
                order = order_service.checkout(
                    db, user_id=user_id, token=token, idempotency_key=idempotency_key
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
            finally:
                verify_db.close()

            assert fake_inventory.get_stock(book_id) == 8  # 10 - 2, deducted exactly once
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
                cleanup_db.commit()
            finally:
                cleanup_db.close()
