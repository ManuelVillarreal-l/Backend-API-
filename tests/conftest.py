"""Shared test setup.

The tests use their own SQLite file so they never touch the real rutasegura.db.
This must run before the app is imported, which is why it lives in conftest.py.
"""

import os
from pathlib import Path

import pytest

TEST_DB = Path(__file__).resolve().parent.parent / "test_rutasegura.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client
    engine.dispose()
    if TEST_DB.exists():
        TEST_DB.unlink()


def login(client, email: str, password: str) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture(scope="session")
def coordinator_headers(client):
    return login(client, "admin@rutasegura.com", "Admin123*")


@pytest.fixture(scope="session")
def guardian_headers(client):
    return login(client, "acudiente@rutasegura.com", "Acudiente123*")
