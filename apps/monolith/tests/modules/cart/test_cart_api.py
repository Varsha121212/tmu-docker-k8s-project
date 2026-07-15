"""Tests for the Cart module (US-CART-01..US-CART-04).

Traces to: FR-CART-01, FR-CART-02, FR-CART-03, FR-CART-04, BRULE-03, BRULE-04, FT-05.
"""

from decimal import Decimal

import pytest

from app.core.redis import get_redis
from app.modules.catalog.service import create_book


@pytest.fixture()
def redis_client():
    return get_redis()


@pytest.fixture()
def customer(client, redis_client):
    """Registers a fresh customer and cleans up their cart key afterward -
    Redis writes aren't covered by the Postgres per-test rollback fixture.
    """
    import uuid

    email = f"{uuid.uuid4()}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-1", "display_name": "Cart Tester"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    token = login.json()["access_token"]
    user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]

    yield {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}

    redis_client.delete(f"cart:{user_id}")


@pytest.fixture()
def book(db_session):
    return create_book(
        db_session,
        title="Cart Test Book",
        author_name="Cart Test Author",
        category="Fiction",
        price=Decimal("12.50"),
    )


class TestAddItem:
    def test_add_item_requires_auth(self, client, book):
        response = client.post(
            "/api/cart/items", json={"book_id": str(book.id), "quantity": 1}
        )
        assert response.status_code == 401

    def test_add_item_rejects_zero_quantity(self, client, customer, book):
        response = client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 0},
            headers=customer["headers"],
        )
        assert response.status_code == 422

    def test_add_item_rejects_unknown_book(self, client, customer):
        import uuid

        response = client.post(
            "/api/cart/items",
            json={"book_id": str(uuid.uuid4()), "quantity": 1},
            headers=customer["headers"],
        )
        assert response.status_code == 404

    def test_add_item_reflects_in_cart(self, client, customer, book):
        response = client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 2},
            headers=customer["headers"],
        )
        assert response.status_code == 201
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["quantity"] == 2


class TestUpdateAndRemove:
    def test_update_existing_item_changes_quantity(self, client, customer, book):
        client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 1},
            headers=customer["headers"],
        )

        response = client.patch(
            f"/api/cart/items/{book.id}", json={"quantity": 5}, headers=customer["headers"]
        )

        assert response.status_code == 200
        assert response.json()["items"][0]["quantity"] == 5

    def test_update_item_not_in_cart_is_404(self, client, customer, book):
        response = client.patch(
            f"/api/cart/items/{book.id}", json={"quantity": 5}, headers=customer["headers"]
        )
        assert response.status_code == 404

    def test_remove_item_drops_it_from_cart(self, client, customer, book):
        client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 1},
            headers=customer["headers"],
        )

        response = client.delete(f"/api/cart/items/{book.id}", headers=customer["headers"])

        assert response.status_code == 200
        assert response.json()["items"] == []

    def test_remove_item_not_in_cart_is_404(self, client, customer, book):
        response = client.delete(f"/api/cart/items/{book.id}", headers=customer["headers"])
        assert response.status_code == 404


class TestPricing:
    def test_cart_totals_use_authoritative_catalog_price(self, client, customer, book):
        client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 3},
            headers=customer["headers"],
        )

        response = client.get("/api/cart", headers=customer["headers"])

        assert response.status_code == 200
        body = response.json()
        assert body["items"][0]["unit_price"] == "12.50"
        assert body["items"][0]["line_total"] == "37.50"
        assert body["total"] == "37.50"

    def test_cart_ignores_client_supplied_price(self, client, customer, book):
        """AddItemRequest has no price field at all - proves the total can't be
        manipulated client-side (BRULE-04) because there is nowhere to inject one."""
        response = client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 1, "price": "0.01"},
            headers=customer["headers"],
        )
        assert response.status_code == 201
        assert response.json()["items"][0]["unit_price"] == "12.50"


class TestClearCart:
    def test_clear_empties_the_cart(self, client, customer, book):
        client.post(
            "/api/cart/items",
            json={"book_id": str(book.id), "quantity": 1},
            headers=customer["headers"],
        )

        clear_response = client.delete("/api/cart", headers=customer["headers"])
        assert clear_response.status_code == 204

        get_response = client.get("/api/cart", headers=customer["headers"])
        assert get_response.json()["items"] == []

    def test_clear_is_safe_on_already_empty_cart(self, client, customer):
        response = client.delete("/api/cart", headers=customer["headers"])
        assert response.status_code == 204


def test_health_ready_reports_redis_connectivity(client):
    response = client.get("/api/cart/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
