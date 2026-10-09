"""Security requirements: hashed passwords, 30-minute tokens, lockout, validation, permissions."""

from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth import ALGORITHM, SECRET_KEY, client_digest
from app.database import SessionLocal
from app.models import User


def test_password_is_never_stored_or_returned(client, coordinator):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == "admin@rutasegura.com").one()
        assert "Admin123*" not in user.password_hash
        assert client_digest("admin@rutasegura.com", "Admin123*") not in user.password_hash
        assert user.password_hash.startswith("pbkdf2_sha256$310000$")
    body = client.get("/api/users/", headers=coordinator).text
    assert "password" not in body


def test_plain_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": "admin@rutasegura.com", "password": "Admin123*"})
    assert response.status_code == 422
    assert "cifrada" in response.json()["detail"][0]["msg"]


def test_giant_password_is_rejected(client):
    response = client.post("/api/auth/login", json={"email": "admin@rutasegura.com", "password": "a" * 5000})
    assert response.status_code == 422


def test_oversized_request_is_rejected(client):
    response = client.post(
        "/api/auth/login",
        content=b'{"email":"' + b"a" * 70_000 + b'"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413


def test_token_lasts_30_minutes(client):
    email = "admin@rutasegura.com"
    body = client.post("/api/auth/login", json={"email": email, "password": client_digest(email, "Admin123*")}).json()
    assert body["expires_in"] == 30 * 60
    claims = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
    assert claims["exp"] - claims["iat"] == 30 * 60


def test_expired_token_is_rejected(client):
    past = datetime.now(timezone.utc) - timedelta(minutes=31)
    token = jwt.encode({"sub": "1", "iat": past, "exp": past + timedelta(minutes=30)}, SECRET_KEY, algorithm=ALGORITHM)
    response = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "venció" in response.json()["detail"]


def test_account_locks_after_five_failures(client):
    email = "monitor2@rutasegura.com"
    wrong = client_digest(email, "Equivocada1*")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": email, "password": wrong}).status_code == 401
    locked = client.post("/api/auth/login", json={"email": email, "password": client_digest(email, "Monitor123*")})
    assert locked.status_code == 429
    assert "bloqueada" in locked.json()["detail"]


def test_swagger_form_login(client):
    email = "admin@rutasegura.com"
    response = client.post("/api/auth/token", data={"username": email, "password": client_digest(email, "Admin123*")})
    assert response.status_code == 200


def test_profile_returns_the_token_owner(client, guardian):
    body = client.get("/api/auth/profile", headers=guardian).json()
    assert body["email"] == "acudiente@rutasegura.com"
    assert body["role"]["code"] == "guardian"
    assert "password" not in body and "password_hash" not in body
    assert client.get("/api/auth/me", headers=guardian).status_code == 404


def test_public_registration_does_not_exist(client):
    response = client.post("/api/auth/register", json={})
    assert response.status_code in (404, 405)


def test_only_coordinator_creates_users(client, driver):
    assert client.post("/api/users/", json={}, headers=driver).status_code == 403


def test_user_form_regex_validation(client, coordinator):
    bad = {
        "role_code": "guardian",
        "document_type_code": "cc",
        "document_number": "12ab",
        "first_name": "Juan123",
        "last_name": "Pérez",
        "email": "no-es-un-correo",
        "phone": "123",
        "password": client_digest("x@y.co", "Clave123*"),
    }
    response = client.post("/api/users/", json=bad, headers=coordinator)
    assert response.status_code == 422
    fields = {item["loc"][-1] for item in response.json()["detail"]}
    assert {"document_number", "first_name", "email", "phone"} <= fields


def test_create_user_with_role_from_table(client, coordinator):
    email = "nuevo.acudiente@rutasegura.com"
    data = {
        "role_code": "guardian",
        "document_type_code": "cc",
        "document_number": "1085999001",
        "first_name": "María José",
        "last_name": "Ortega",
        "email": email,
        "phone": "3157778899",
        "password": client_digest(email, "Clave123*"),
    }
    response = client.post("/api/users/", json=data, headers=coordinator)
    assert response.status_code == 201, response.text
    assert response.json()["role"]["code"] == "guardian"
    assert client.post("/api/users/", json=data, headers=coordinator).status_code == 409


def test_guardian_only_sees_own_children(client, guardian):
    students = client.get("/api/students/", headers=guardian).json()
    assert {"Juan Pérez", "Valentina Pérez"} <= {s["full_name"] for s in students}
    # Every visible student is linked to this guardian (user 3).
    assert all(any(g["guardian_id"] == 3 for g in s["guardians"]) for s in students)
    others = client.get("/api/students/3", headers=guardian)
    assert others.status_code == 403


def test_guardian_cannot_list_users(client, guardian):
    assert client.get("/api/users/", headers=guardian).status_code == 403
