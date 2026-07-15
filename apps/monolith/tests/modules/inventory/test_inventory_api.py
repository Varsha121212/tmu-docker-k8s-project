"""Tests for the Inventory module (US-INV-01..US-INV-03).

Traces to: FR-INV-01, FR-INV-02, FR-INV-03, BRULE-03, BRULE-05, DR-006, FT-04, FT-07, AT-02.
"""

import threading
import uuid

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.modules.inventory import service
from app.modules.inventory.internal import repository
from app.modules.inventory.internal.models import Reservation, Stock, StockMovement


def _auth_token(client):
    email = f"{uuid.uuid4()}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-1", "display_name": "Stock Clerk"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    return login.json()["access_token"]


class TestGetStock:
    def test_stock_for_unknown_book_is_zero_not_error(self, client):
        response = client.get(f"/api/inventory/stock/{uuid.uuid4()}")
        assert response.status_code == 200
        assert response.json()["available_qty"] == 0

    def test_stock_reflects_seeded_quantity(self, client, db_session):
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=10)

        response = client.get(f"/api/inventory/stock/{book_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["available_qty"] == 10
        assert body["version"] == 0


class TestReserve:
    def test_reserve_requires_auth(self, client):
        response = client.post(
            "/api/inventory/reserve",
            json={
                "book_id": str(uuid.uuid4()),
                "quantity": 1,
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert response.status_code == 401

    def test_reserve_deducts_stock(self, client, db_session):
        token = _auth_token(client)
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=5)

        response = client.post(
            "/api/inventory/reserve",
            json={"book_id": str(book_id), "quantity": 2, "idempotency_key": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        assert response.json()["status"] == "reserved"

        stock_response = client.get(f"/api/inventory/stock/{book_id}")
        assert stock_response.json()["available_qty"] == 3

    def test_reserve_rejects_insufficient_stock_without_changing_it(self, client, db_session):
        token = _auth_token(client)
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=1)

        response = client.post(
            "/api/inventory/reserve",
            json={"book_id": str(book_id), "quantity": 5, "idempotency_key": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 409
        stock_response = client.get(f"/api/inventory/stock/{book_id}")
        assert stock_response.json()["available_qty"] == 1

    def test_reserve_is_idempotent_on_retry(self, client, db_session):
        token = _auth_token(client)
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=5)
        idempotency_key = str(uuid.uuid4())
        payload = {"book_id": str(book_id), "quantity": 2, "idempotency_key": idempotency_key}
        headers = {"Authorization": f"Bearer {token}"}

        first = client.post("/api/inventory/reserve", json=payload, headers=headers)
        second = client.post("/api/inventory/reserve", json=payload, headers=headers)

        assert first.status_code == second.status_code == 201
        assert first.json()["id"] == second.json()["id"]

        stock_response = client.get(f"/api/inventory/stock/{book_id}")
        assert stock_response.json()["available_qty"] == 3  # deducted once, not twice


class TestRelease:
    def test_release_restores_stock(self, client, db_session):
        token = _auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=5)

        reserve_response = client.post(
            "/api/inventory/reserve",
            json={"book_id": str(book_id), "quantity": 2, "idempotency_key": str(uuid.uuid4())},
            headers=headers,
        )
        reservation_id = reserve_response.json()["id"]

        release_response = client.post(
            "/api/inventory/release", json={"reservation_id": reservation_id}, headers=headers
        )

        assert release_response.status_code == 200
        assert release_response.json()["status"] == "released"

        stock_response = client.get(f"/api/inventory/stock/{book_id}")
        assert stock_response.json()["available_qty"] == 5

    def test_release_is_idempotent_on_retry(self, client, db_session):
        token = _auth_token(client)
        headers = {"Authorization": f"Bearer {token}"}
        book_id = uuid.uuid4()
        repository.ensure_stock_row(db_session, book_id, initial_qty=5)

        reserve_response = client.post(
            "/api/inventory/reserve",
            json={"book_id": str(book_id), "quantity": 2, "idempotency_key": str(uuid.uuid4())},
            headers=headers,
        )
        reservation_id = reserve_response.json()["id"]

        first = client.post(
            "/api/inventory/release", json={"reservation_id": reservation_id}, headers=headers
        )
        second = client.post(
            "/api/inventory/release", json={"reservation_id": reservation_id}, headers=headers
        )

        assert first.status_code == second.status_code == 200
        stock_response = client.get(f"/api/inventory/stock/{book_id}")
        assert stock_response.json()["available_qty"] == 5  # not double-credited

    def test_release_unknown_reservation_is_404(self, client):
        token = _auth_token(client)
        response = client.post(
            "/api/inventory/release",
            json={"reservation_id": str(uuid.uuid4())},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


def test_health_ready_reports_database_connectivity(client):
    response = client.get("/api/inventory/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


class TestConcurrentReservation:
    """Proves the atomic UPDATE actually prevents overselling under real concurrent
    access (BRULE-05), not just sequential calls sharing one transaction.

    Deliberately bypasses the per-test rollback fixture and uses independent DB
    sessions on separate threads, since two genuinely concurrent operations cannot
    happen on a single shared connection. Cleans up everything it commits.
    """

    def test_only_one_of_two_racing_reservations_succeeds(self):
        engine = create_engine(get_settings().database_url)
        session_factory = sessionmaker(bind=engine)
        book_id = uuid.uuid4()

        setup_db = session_factory()
        try:
            repository.ensure_stock_row(setup_db, book_id, initial_qty=5)
        finally:
            setup_db.close()

        results: dict[str, tuple[str, object]] = {}

        def attempt(label: str, quantity: int) -> None:
            db = session_factory()
            try:
                reservation = service.reserve(
                    db, book_id=book_id, quantity=quantity, idempotency_key=f"{label}-{book_id}"
                )
                results[label] = ("ok", reservation.id)
            except service.InsufficientStockError:
                results[label] = ("rejected", None)
            finally:
                db.close()

        try:
            t1 = threading.Thread(target=attempt, args=("first", 3))
            t2 = threading.Thread(target=attempt, args=("second", 3))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            outcomes = [results["first"][0], results["second"][0]]
            assert outcomes.count("ok") == 1
            assert outcomes.count("rejected") == 1

            verify_db = session_factory()
            try:
                stock = repository.get_stock(verify_db, book_id)
                assert stock is not None
                # 5 - 3: the second 3-unit request must never have applied.
                assert stock.available_qty == 2
            finally:
                verify_db.close()
        finally:
            cleanup_db = session_factory()
            try:
                cleanup_db.execute(delete(StockMovement).where(StockMovement.book_id == book_id))
                cleanup_db.execute(delete(Reservation).where(Reservation.book_id == book_id))
                cleanup_db.execute(delete(Stock).where(Stock.book_id == book_id))
                cleanup_db.commit()
            finally:
                cleanup_db.close()
