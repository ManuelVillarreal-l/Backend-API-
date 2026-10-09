"""Functional tests: catalogs, full trip flow with GPS, AI and data-structure endpoints."""

import uuid
from datetime import datetime, timezone

from tests.helpers import login


def test_health_and_docs(client):
    assert client.get("/health").json()["status"] == "healthy"
    docs = client.get("/docs").text
    assert '"Execute": "Ejecutar"' in docs
    assert "crypto.subtle.digest" in docs  # Swagger also hashes the password


def test_catalogs_come_from_database(client, guardian):
    catalogs = client.get("/api/catalogs/", headers=guardian).json()
    assert len(catalogs) == 10
    assert {"rain", "storm"} <= {w["code"] for w in catalogs["weather_conditions"]}
    assert {r["code"] for r in catalogs["roles"]} == {"coordinator", "driver", "monitor", "guardian"}


def test_coordinator_adds_weather_condition(client, coordinator):
    data = {"code": "hail", "name": "Granizo", "delay_minutes": 12, "weather_codes": "77,85,86"}
    response = client.post("/api/catalogs/weather_conditions", json=data, headers=coordinator)
    assert response.status_code == 201, response.text
    item_id = response.json()["id"]
    updated = client.put(f"/api/catalogs/weather_conditions/{item_id}", json={"delay_minutes": 14}, headers=coordinator)
    assert updated.json()["delay_minutes"] == 14
    too_much = client.post(
        "/api/catalogs/road_conditions", json={"code": "flood", "name": "Inundada", "delay_minutes": 99999},
        headers=coordinator,
    )
    assert too_much.status_code == 422


def test_full_trip_flow_with_gps(client, coordinator, driver, guardian):
    trips = client.get("/api/trips/?status=scheduled", headers=driver).json()
    trip = next(t for t in trips if t["route_id"] == 1)

    # Cannot register before starting.
    early = client.post("/api/attendance/scan", json={"qr_code": "RS-DEMO-0001", "trip_id": trip["id"]}, headers=driver)
    assert early.status_code == 409

    started = client.post(
        f"/api/trips/{trip['id']}/start", json={"weather_code": "rain", "road_condition_code": "fair"}, headers=driver
    )
    assert started.status_code == 200, started.text
    assert started.json()["status"]["code"] == "in_progress"

    queue = client.get(f"/api/trips/{trip['id']}/queue", headers=driver).json()
    assert queue["next"]["stop"] == "Vereda Santa Teresita"

    # GPS near the first stop notifies the guardian once.
    gps = {"latitude": 1.1185, "longitude": -77.1730, "speed_kmh": 28}
    sent = client.post(f"/api/trips/{trip['id']}/locations", json=gps, headers=driver).json()
    assert sent["approach_notifications"] >= 1
    again = client.post(f"/api/trips/{trip['id']}/locations", json=gps, headers=driver).json()
    assert again["approach_notifications"] == 0

    eta = client.get(f"/api/trips/{trip['id']}/eta?stop_id=2", headers=guardian)
    assert eta.status_code == 200, eta.text
    assert eta.json()["eta_minutes"] >= 1

    boarded = client.post("/api/attendance/scan", json={"qr_code": "rs-demo-0001", "trip_id": trip["id"]}, headers=driver)
    assert boarded.status_code == 201, boarded.text
    assert boarded.json()["event_type"]["code"] == "boarding"
    twice = client.post(
        "/api/attendance/",
        json={"student_id": 1, "trip_id": trip["id"], "event_type_code": "boarding"},
        headers=driver,
    )
    assert twice.status_code == 409

    not_on_board = client.post(
        "/api/attendance/", json={"student_id": 2, "trip_id": trip["id"], "event_type_code": "drop_off"}, headers=driver
    )
    assert not_on_board.status_code == 409

    # Undo the last event (stack) and register it again.
    undone = client.post(f"/api/trips/{trip['id']}/undo", headers=driver)
    assert undone.status_code == 200
    assert client.post("/api/attendance/scan", json={"qr_code": "RS-DEMO-0001", "trip_id": trip["id"]}, headers=driver).status_code == 201

    # Cannot finish while someone is on board.
    blocked = client.post(f"/api/trips/{trip['id']}/finish", headers=driver)
    assert blocked.status_code == 409
    dropped = client.post("/api/attendance/scan", json={"qr_code": "RS-DEMO-0001", "trip_id": trip["id"]}, headers=driver)
    assert dropped.json()["event_type"]["code"] == "drop_off"

    notifications = client.get("/api/notifications", headers=guardian).json()
    kinds = {n["kind"] for n in notifications}
    assert {"boarding", "drop_off", "trip_started"} <= kinds
    assert any(k.startswith("near:") for k in kinds)

    finished = client.post(f"/api/trips/{trip['id']}/finish", headers=driver)
    assert finished.json()["status"]["code"] == "finished"


def test_driver_cannot_operate_other_trips(client, driver):
    other = login(client, "conductor2@rutasegura.com", "Conductor123*")
    trip = next(t for t in client.get("/api/trips/?status=scheduled", headers=other).json())
    response = client.post(
        f"/api/trips/{trip['id']}/start", json={"weather_code": "clear", "road_condition_code": "good"}, headers=driver
    )
    assert response.status_code == 403


def test_offline_sync_is_idempotent(client):
    driver2 = login(client, "conductor2@rutasegura.com", "Conductor123*")
    trip = next(t for t in client.get("/api/trips/?status=scheduled", headers=driver2).json())
    client.post(f"/api/trips/{trip['id']}/start", json={"weather_code": "clear", "road_condition_code": "good"}, headers=driver2)
    event = {
        "client_event_id": str(uuid.uuid4()),
        "trip_id": trip["id"],
        "student_id": 4,
        "event_type_code": "boarding",
        "method_code": "qr",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    first = client.post("/api/attendance/sync", json={"events": [event]}, headers=driver2).json()
    second = client.post("/api/attendance/sync", json={"events": [event]}, headers=driver2).json()
    assert first["saved"] == 1 and second["duplicated"] == 1


def test_incident_notifies_coordinator(client, coordinator, driver):
    response = client.post(
        "/api/incidents",
        json={"incident_type_code": "mechanical", "description": "Se recalentó el motor en la subida."},
        headers=driver,
    )
    assert response.status_code == 201
    notes = client.get("/api/notifications", headers=coordinator).json()
    assert any(n["kind"] == "incident" for n in notes)
    script = client.post(
        "/api/incidents", json={"incident_type_code": "other", "description": "<script>alert(1)</script>"}, headers=driver
    )
    assert script.status_code == 422


def test_ai_delay_uses_regression(client, coordinator):
    response = client.post(
        "/api/ai/delay",
        json={"weather_code": "storm", "road_condition_code": "bad", "stops_remaining": 4, "hour": 6},
        headers=coordinator,
    )
    body = response.json()
    assert body["model"] == "regression"
    assert body["training_samples"] >= 8
    assert body["risk"] == "high"


def test_route_optimization_and_shortest_path(client, coordinator):
    optimized = client.post("/api/routes/2/optimize", headers=coordinator).json()
    assert optimized["saving_percent"] > 0
    assert optimized["suggested_order"][-1] == "Institución Educativa"
    path = client.get("/api/routes/1/shortest-path?from_stop_id=1&to_stop_id=5", headers=coordinator).json()
    assert path["path"][0]["id"] == 1 and path["path"][-1]["id"] == 5


def test_data_structure_endpoints(client, coordinator):
    found = client.get("/api/students/search?q=val", headers=coordinator).json()
    assert [s["full_name"] for s in found] == ["Valentina Pérez"]
    by_last_name = client.get("/api/students/search?q=perez", headers=coordinator).json()
    assert {s["first_name"] for s in by_last_name} == {"Juan", "Valentina"}

    itinerary = client.get("/api/routes/1/itinerary?direction=return", headers=coordinator).json()
    assert itinerary["stops"][0]["name"] == "Institución Educativa"

    tree = client.get("/api/schools/tree", headers=coordinator).json()
    assert tree["total_leaves"] == 10

    rotation = client.get("/api/users/drivers/rotation?driver_user_id=9", headers=coordinator).json()
    assert rotation["next"]["user_id"] == 2  # after the last driver comes the first one

    monitors = client.get("/api/trips/rotation/monitors?days=4", headers=coordinator).json()
    assert monitors[0]["monitor"]["user_id"] == monitors[2]["monitor"]["user_id"]

    structures = client.get("/api/structures", headers=coordinator).json()
    assert len(structures) == 10


def test_absence_risk_and_summary(client, coordinator, guardian):
    risk = client.get("/api/students/1/absence-risk", headers=guardian).json()
    assert risk["trips_analyzed"] >= 10
    summary = client.get("/api/reports/summary", headers=coordinator).json()
    assert summary["students"] == 10
    assert len(summary["attendance_last_7_days"]) == 7


def test_student_registration_validation(client, coordinator):
    data = {
        "document_type_code": "ti",
        "document_number": "1085300099",
        "first_name": "Ana Lucía",
        "last_name": "Cabrera",
        "birth_date": "2015-04-10",
        "grade_code": "fifth",
        "campus_id": 1,
        "route_id": 1,
        "stop_id": 2,
        "guardians": [{"guardian_id": 3, "relationship_code": "mother", "is_primary": True}],
    }
    created = client.post("/api/students/", json=data, headers=coordinator)
    assert created.status_code == 201, created.text
    assert created.json()["qr_code"].startswith("RS-")

    wrong_stop = dict(data, document_number="1085300098", stop_id=7)
    assert client.post("/api/students/", json=wrong_stop, headers=coordinator).status_code == 422
    too_old = dict(data, document_number="1085300097", birth_date="1980-01-01")
    assert client.post("/api/students/", json=too_old, headers=coordinator).status_code == 422
