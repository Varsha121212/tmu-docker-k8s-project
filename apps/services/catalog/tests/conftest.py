from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app

_engine = create_engine(get_settings().database_url)
_TestingSessionLocal = sessionmaker(bind=_engine)


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
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_test_jwt(subject: str = "test-user") -> str:
    """Mints a JWT locally using the same shared secret every service verifies
    against, instead of calling a running Identity service - keeps this
    service's tests independently runnable (US-PLT-04's acceptance criterion).
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": subject, "iat": now, "exp": now + timedelta(minutes=30)}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
