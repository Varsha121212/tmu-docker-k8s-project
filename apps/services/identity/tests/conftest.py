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
