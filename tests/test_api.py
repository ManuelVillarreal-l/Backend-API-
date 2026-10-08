def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_docs_in_spanish(client):
    response = client.get("/docs")
    assert response.status_code == 200
    assert '"Execute": "Ejecutar"' in response.text


def test_login_json(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@rutasegura.com", "password": "Admin123*"},
    )
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"


def test_login_wrong_password(client):
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@rutasegura.com", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Correo o contraseña incorrectos"


def test_login_swagger_form(client):
    """The Swagger Authorize button sends a form to /token."""
    response = client.post(
        "/api/auth/token",
        data={"username": "admin@rutasegura.com", "password": "Admin123*"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_protected_endpoint_requires_token(client):
    response = client.get("/api/students/")
    assert response.status_code == 401
    assert response.json()["detail"] == "No autenticado. Inicie sesión con el botón Autorizar."


def test_demo_data(client, coordinator_headers):
    students = client.get("/api/students/", headers=coordinator_headers).json()
    assert any(s["full_name"] == "Juan Pérez Demo" for s in students)

    stops = client.get("/api/routes/1/stops", headers=coordinator_headers).json()
    assert [s["name"] for s in stops] == [
        "Vereda El Encano",
        "Vereda La Laguna",
        "Institución Educativa",
    ]


def test_full_trip_flow(client, coordinator_headers):
    users = client.get("/api/users/", headers=coordinator_headers).json()
    driver_id = next(u["id"] for u in users if u["role"] == "driver")

    trip = client.post(
        "/api/trips/", json={"route_id": 1, "driver_id": driver_id}, headers=coordinator_headers
    ).json()
    assert trip["status"] == "scheduled"

    started = client.post(f"/api/trips/{trip['id']}/start", headers=coordinator_headers).json()
    assert started["status"] == "in_progress"
    assert started["started_at"] is not None

    for stop_id, event_type in [(1, "boarding"), (3, "drop_off")]:
        response = client.post(
            "/api/attendance/",
            json={
                "student_id": 1,
                "trip_id": trip["id"],
                "stop_id": stop_id,
                "event_type": event_type,
                "method": "qr",
            },
            headers=coordinator_headers,
        )
        assert response.status_code == 200

    history = client.get("/api/attendance/student/1", headers=coordinator_headers).json()
    assert {e["event_type"] for e in history if e["trip_id"] == trip["id"]} == {"boarding", "drop_off"}

    finished = client.post(f"/api/trips/{trip['id']}/finish", headers=coordinator_headers).json()
    assert finished["status"] == "finished"


def test_scan_qr(client, coordinator_headers):
    trip = client.post("/api/trips/", json={"route_id": 1}, headers=coordinator_headers).json()
    response = client.post(
        "/api/attendance/scan",
        json={"qr_code": "RS-DEMO-0001", "trip_id": trip["id"], "stop_id": 1, "event_type": "boarding"},
        headers=coordinator_headers,
    )
    assert response.status_code == 200
    assert response.json()["method"] == "qr"


def test_invalid_event_type(client, coordinator_headers):
    response = client.post(
        "/api/attendance/",
        json={"student_id": 1, "trip_id": 1, "event_type": "abordaje"},
        headers=coordinator_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"].startswith("Valor no válido")


def test_missing_field_message_in_spanish(client):
    response = client.post("/api/auth/login", json={"email": "admin@rutasegura.com"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Campo obligatorio"


def test_not_found_message_in_spanish(client):
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"] == "Recurso no encontrado"


def test_guardian_cannot_register_attendance(client, guardian_headers):
    response = client.post(
        "/api/attendance/",
        json={"student_id": 1, "trip_id": 1, "event_type": "boarding"},
        headers=guardian_headers,
    )
    assert response.status_code == 403


def test_delay_prediction(client, coordinator_headers):
    response = client.post(
        "/api/ai/delay",
        json={"weather": "rain", "road_condition": "bad", "historical_delay_minutes": 0, "stops_remaining": 2},
        headers=coordinator_headers,
    )
    body = response.json()
    assert response.status_code == 200
    assert body["estimated_delay_minutes"] == 19.4
    assert body["risk"] == "high"
