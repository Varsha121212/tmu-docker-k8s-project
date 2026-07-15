import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import jwt
import pytest
import respx
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.redis import get_redis
from app.main import app


def make_test_jwt(subject: str = "test-user") -> str:
    """Mints a JWT locally using the same shared secret every service verifies
    against, instead of calling a running Identity service - keeps this
    service's tests independently runnable (US-PLT-04's acceptance criterion).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=30)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def redis_client():
    return get_redis()


@pytest.fixture()
def customer(client, redis_client):
    """A fresh customer identity (locally-minted JWT); cleans up their cart key
    afterward since Redis writes aren't covered by any per-test DB rollback.
    """
    user_id = str(uuid.uuid4())
    token = make_test_jwt(subject=user_id)

    yield {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}

    redis_client.delete(f"cart:{user_id}")


BOOK_PRICE = "12.50"


@pytest.fixture()
def book(mock_catalog):
    """A book known to the mocked Catalog service - stands in for the monolith
    test's real `create_book(db_session, ...)` fixture, since Cart no longer
    has Catalog's code or database in-process (US-PLT-04).
    """
    return SimpleNamespace(id=mock_catalog.book_id)


@pytest.fixture()
def mock_catalog():
    """Mocks Cart -> Catalog HTTP calls (app.core.catalog_client) instead of
    requiring a real running catalog-service, so this service's test suite
    stays independently runnable.
    """
    settings = get_settings()
    book_id = str(uuid.uuid4())

    with respx.mock(base_url=settings.catalog_service_url, assert_all_called=False) as mock:
        mock.get(f"/api/books/{book_id}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": book_id,
                    "isbn": None,
                    "title": "Cart Test Book",
                    "author_name": "Cart Test Author",
                    "category": "Fiction",
                    "price": BOOK_PRICE,
                    "active": True,
                    "cover_image_url": None,
                },
            )
        )
        mock.get(url__regex=r"/api/books/.*").mock(return_value=httpx.Response(404))
        mock.book_id = book_id
        yield mock
