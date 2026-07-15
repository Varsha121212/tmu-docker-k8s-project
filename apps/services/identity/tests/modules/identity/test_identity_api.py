"""Tests for the Identity service API (US-ID-01..US-ID-04).

Traces to: FR-ID-01, FR-ID-02, FR-ID-03, FR-ID-04, BRULE-01, BRULE-02, AT-02.
"""

import uuid


def _register(client, email=None, password="correct-horse-1", display_name="Ada Lovelace"):
    return client.post(
        "/api/auth/register",
        json={
            "email": email or f"{uuid.uuid4()}@example.com",
            "password": password,
            "display_name": display_name,
        },
    )


class TestRegister:
    def test_register_creates_user_and_hides_password_hash(self, client):
        response = _register(client)

        assert response.status_code == 201
        body = response.json()
        assert body["email"]
        assert body["display_name"] == "Ada Lovelace"
        assert "password" not in body
        assert "password_hash" not in body

    def test_register_rejects_duplicate_email(self, client):
        email = f"{uuid.uuid4()}@example.com"
        first = _register(client, email=email)
        assert first.status_code == 201

        second = _register(client, email=email)
        assert second.status_code == 409

    def test_register_rejects_invalid_email(self, client):
        response = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "correct-horse-1", "display_name": "A"},
        )
        assert response.status_code == 422

    def test_register_rejects_short_password(self, client):
        response = client.post(
            "/api/auth/register",
            json={
                "email": f"{uuid.uuid4()}@example.com",
                "password": "short",
                "display_name": "A",
            },
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_with_valid_credentials_returns_jwt(self, client):
        email = f"{uuid.uuid4()}@example.com"
        _register(client, email=email, password="correct-horse-1")

        response = client.post(
            "/api/auth/login", json={"email": email, "password": "correct-horse-1"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    def test_login_with_wrong_password_is_generic_401(self, client):
        email = f"{uuid.uuid4()}@example.com"
        _register(client, email=email, password="correct-horse-1")

        response = client.post(
            "/api/auth/login", json={"email": email, "password": "wrong-password"}
        )

        assert response.status_code == 401
        assert response.json()["message"] == "Invalid credentials"

    def test_login_with_unknown_email_returns_identical_error(self, client):
        """FR-ID-03: must not reveal whether the email or the password was wrong."""
        known_email = f"{uuid.uuid4()}@example.com"
        _register(client, email=known_email, password="correct-horse-1")

        wrong_password_response = client.post(
            "/api/auth/login", json={"email": known_email, "password": "wrong-password"}
        )
        unknown_email_response = client.post(
            "/api/auth/login",
            json={"email": f"{uuid.uuid4()}@example.com", "password": "correct-horse-1"},
        )

        assert wrong_password_response.status_code == unknown_email_response.status_code == 401
        assert (
            wrong_password_response.json()["message"] == unknown_email_response.json()["message"]
        )


class TestMe:
    def test_me_with_valid_token_returns_profile(self, client):
        email = f"{uuid.uuid4()}@example.com"
        _register(client, email=email, password="correct-horse-1")
        login_response = client.post(
            "/api/auth/login", json={"email": email, "password": "correct-horse-1"}
        )
        token = login_response.json()["access_token"]

        response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        assert response.json()["email"] == email

    def test_me_without_token_is_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_garbage_token_is_401(self, client):
        response = client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert response.status_code == 401


def test_health_ready_reports_database_connectivity(client):
    response = client.get("/api/auth/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
