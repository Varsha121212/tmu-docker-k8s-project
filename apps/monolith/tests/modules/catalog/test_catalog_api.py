"""Tests for the Catalog module API (US-CAT-01..US-CAT-03).

Traces to: FR-CAT-01, FR-CAT-02, FR-CAT-03, BRULE-10.
"""

import uuid


def _create_book(
    client, token, title=None, author=None, category="Fiction", price="14.99", cover_image_url=None
):
    payload = {
        "title": title or f"Book {uuid.uuid4()}",
        "author_name": author or f"Author {uuid.uuid4()}",
        "category": category,
        "price": price,
    }
    if cover_image_url is not None:
        payload["cover_image_url"] = cover_image_url
    return client.post(
        "/api/books",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )


def _auth_token(client):
    email = f"{uuid.uuid4()}@example.com"
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "correct-horse-1", "display_name": "Cataloguer"},
    )
    login = client.post("/api/auth/login", json={"email": email, "password": "correct-horse-1"})
    return login.json()["access_token"]


class TestCreateBook:
    def test_create_requires_auth(self, client):
        response = client.post(
            "/api/books",
            json={
                "title": "Unauthorized Entry",
                "author_name": "Nobody",
                "category": "Fiction",
                "price": "9.99",
            },
        )
        assert response.status_code == 401

    def test_create_with_auth_succeeds(self, client):
        token = _auth_token(client)
        response = _create_book(client, token, title="A Bound Volume")

        assert response.status_code == 201
        body = response.json()
        assert body["title"] == "A Bound Volume"
        assert body["active"] is True
        assert body["cover_image_url"] is None

    def test_create_with_cover_image_url_round_trips(self, client):
        token = _auth_token(client)
        response = _create_book(
            client, token, title="Illustrated Edition", cover_image_url="/covers/illustrated-edition.svg"
        )

        assert response.status_code == 201
        assert response.json()["cover_image_url"] == "/covers/illustrated-edition.svg"


class TestListBooks:
    def test_list_returns_paginated_shape(self, client):
        token = _auth_token(client)
        _create_book(client, token)

        response = client.get("/api/books")

        assert response.status_code == 200
        body = response.json()
        assert "items" in body and "total" in body and "page" in body and "page_size" in body
        assert body["total"] >= 1

    def test_list_filters_by_title_query(self, client):
        token = _auth_token(client)
        unique_title = f"Zeta Chronicles {uuid.uuid4()}"
        _create_book(client, token, title=unique_title)

        response = client.get("/api/books", params={"q": "Zeta Chronicles"})

        assert response.status_code == 200
        titles = [item["title"] for item in response.json()["items"]]
        assert unique_title in titles

    def test_list_filters_by_category(self, client):
        token = _auth_token(client)
        unique_category = f"Category-{uuid.uuid4()}"
        _create_book(client, token, category=unique_category)

        response = client.get("/api/books", params={"category": unique_category})

        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["category"] == unique_category

    def test_list_filters_by_author(self, client):
        token = _auth_token(client)
        unique_author = f"Author-{uuid.uuid4()}"
        _create_book(client, token, author=unique_author)

        response = client.get("/api/books", params={"author": unique_author})

        assert response.status_code == 200
        authors = [item["author_name"] for item in response.json()["items"]]
        assert unique_author in authors


class TestGetBook:
    def test_get_existing_book_returns_details(self, client):
        token = _auth_token(client)
        created = _create_book(client, token, title="Findable Book").json()

        response = client.get(f"/api/books/{created['id']}")

        assert response.status_code == 200
        assert response.json()["title"] == "Findable Book"

    def test_get_missing_book_is_404(self, client):
        response = client.get(f"/api/books/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_get_with_malformed_id_is_404_not_500(self, client):
        response = client.get("/api/books/not-a-uuid")
        assert response.status_code == 404


def test_categories_endpoint_reflects_created_books(client):
    token = _auth_token(client)
    unique_category = f"Category-{uuid.uuid4()}"
    _create_book(client, token, category=unique_category)

    response = client.get("/api/books/categories")

    assert response.status_code == 200
    assert unique_category in response.json()


def test_health_ready_reports_database_connectivity(client):
    response = client.get("/api/books/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
