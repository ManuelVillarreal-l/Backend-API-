"""Test helpers without side effects (safe to import from any test module)."""

from app.auth import client_digest


def login(client, email: str, password: str) -> dict:
    """Log in like the browser does: send only the SHA-256 digest of the password."""
    response = client.post("/api/auth/login", json={"email": email, "password": client_digest(email, password)})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
