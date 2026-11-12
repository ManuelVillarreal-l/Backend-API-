"""CRUD (edit / delete) endpoints and the attendance matrix."""


def test_health_reports_database(client):
    body = client.get("/health").json()
    assert body["database"] in ("sqlite", "postgresql", "sqlite-fallback")


def test_attendance_matrix(client, coordinator, guardian):
    response = client.get("/api/attendance/matrix?route_id=1&days=10", headers=coordinator)
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["days"]) == 10
    assert len(data["cells"]) == len(data["students"])
    assert all(len(row) == 10 for row in data["cells"])
    assert {c for row in data["cells"] for c in row} <= {"P", "A", "-"}
    assert client.get("/api/attendance/matrix?route_id=1", headers=guardian).status_code == 403


def test_vehicle_crud(client, coordinator):
    created = client.post(
        "/api/vehicles", json={"plate": "XYZ987", "brand": "Chevrolet", "model_year": 2020, "capacity": 20},
        headers=coordinator,
    )
    assert created.status_code == 201, created.text
    vehicle_id = created.json()["id"]
    updated = client.put(f"/api/vehicles/{vehicle_id}", json={"capacity": 25}, headers=coordinator)
    assert updated.json()["capacity"] == 25
    deleted = client.delete(f"/api/vehicles/{vehicle_id}", headers=coordinator)
    assert deleted.json()["active"] is False


def test_route_and_stop_crud(client, coordinator):
    campus_id = client.get("/api/schools", headers=coordinator).json()[0]["campuses"][0]["id"]
    route = client.post(
        "/api/routes/", json={"name": "Ruta de prueba CRUD", "campus_id": campus_id}, headers=coordinator
    ).json()
    stops = [
        client.post(
            "/api/routes/stops",
            json={"route_id": route["id"], "name": f"Parada {n}", "latitude": 1.2 + n / 100, "longitude": -77.3},
            headers=coordinator,
        ).json()
        for n in (1, 2, 3)
    ]
    renamed = client.put(f"/api/routes/stops/{stops[0]['id']}", json={"name": "Parada Uno"}, headers=coordinator)
    assert renamed.json()["name"] == "Parada Uno"
    assert client.delete(f"/api/routes/stops/{stops[1]['id']}", headers=coordinator).status_code == 200
    remaining = client.get(f"/api/routes/{route['id']}/stops", headers=coordinator).json()
    assert [s["order"] for s in remaining] == [1, 2]
    edited = client.put(f"/api/routes/{route['id']}", json={"description": "Editada"}, headers=coordinator)
    assert edited.json()["description"] == "Editada"
    assert client.delete(f"/api/routes/{route['id']}", headers=coordinator).json()["active"] is False


# Students used by other test files; this test must not rename or withdraw them.
PROTECTED_STUDENTS = {"Juan Pérez", "Valentina Pérez"}


def test_student_edit_and_withdraw(client, coordinator, guardian):
    students = client.get("/api/students/", headers=coordinator).json()
    student = next(s for s in reversed(students) if s["full_name"] not in PROTECTED_STUDENTS)
    assert client.put(f"/api/students/{student['id']}", json={"first_name": "Nuevo"}, headers=guardian).status_code == 403
    edited = client.put(f"/api/students/{student['id']}", json={"first_name": "Nuevo"}, headers=coordinator)
    assert edited.status_code == 200, edited.text
    assert edited.json()["first_name"] == "Nuevo"
    withdrawn = client.delete(f"/api/students/{student['id']}", headers=coordinator)
    assert withdrawn.json()["active"] is False
    found = client.get("/api/students/search?q=Nuevo", headers=coordinator).json()
    assert student["id"] not in {s["id"] for s in found}
    assert client.delete(f"/api/students/{student['id']}", headers=coordinator).status_code == 409


def test_user_edit(client, coordinator):
    target = client.get("/api/users/?role=monitor", headers=coordinator).json()[0]
    edited = client.put(f"/api/users/{target['id']}", json={"phone": "3109998877"}, headers=coordinator)
    assert edited.status_code == 200, edited.text
    assert edited.json()["phone"] == "3109998877"
    blocked = client.put(f"/api/users/{target['id']}", json={"email": "otro@rutasegura.com"}, headers=coordinator)
    assert blocked.status_code == 422


def test_cancel_scheduled_trip(client, coordinator):
    drivers = client.get("/api/users/?role=driver", headers=coordinator).json()
    # Other tests leave trips in progress; a driver with one cannot get a new trip (409).
    busy = {t["driver_id"] for t in client.get("/api/trips/?status=in_progress", headers=coordinator).json()}
    free_driver = next(d for d in drivers if d["id"] not in busy)
    trip = client.post("/api/trips/", json={"route_id": 1, "driver_id": free_driver["id"]}, headers=coordinator)
    assert trip.status_code == 201, trip.text
    trip_id = trip.json()["id"]
    assert client.put(f"/api/trips/{trip_id}", json={"monitor_id": None}, headers=coordinator).status_code == 200
    assert client.delete(f"/api/trips/{trip_id}", headers=coordinator).json()["cancelled"] is True
    assert client.get(f"/api/trips/{trip_id}", headers=coordinator).status_code == 404
