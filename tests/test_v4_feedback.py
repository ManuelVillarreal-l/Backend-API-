"""Changes requested by the professor in the review of version 3:
buses and drivers by campus, paginated lists, saved AI predictions and automatic warnings."""

from tests.helpers import login


def campus_ids(client, coordinator) -> list[int]:
    schools = client.get("/api/schools", headers=coordinator).json()
    return [c["id"] for s in schools for c in s["campuses"]]


# --- Campuses: create from the app, buses and drivers belong to one campus ----------

def test_create_campus_and_bus_for_it(client, coordinator):
    school = client.get("/api/schools", headers=coordinator).json()[0]
    campus = client.post(
        "/api/campuses",
        json={"school_id": school["id"], "name": "Sede Cali Rural", "address": "Vereda La Buitrera"},
        headers=coordinator,
    )
    assert campus.status_code == 201, campus.text
    campus_id = campus.json()["id"]

    bus = client.post(
        "/api/vehicles",
        json={"plate": "CAL321", "brand": "Mercedes", "model_year": 2022, "capacity": 20, "campus_id": campus_id},
        headers=coordinator,
    )
    assert bus.status_code == 201, bus.text
    assert bus.json()["campus_name"] == "Sede Cali Rural"

    only_cali = client.get(f"/api/vehicles?campus_id={campus_id}", headers=coordinator).json()
    assert [v["plate"] for v in only_cali] == ["CAL321"]

    repeated = client.post(
        "/api/campuses", json={"school_id": school["id"], "name": "Sede Cali Rural"}, headers=coordinator
    )
    assert repeated.status_code == 409


def test_bus_for_unknown_campus_is_rejected(client, coordinator):
    response = client.post(
        "/api/vehicles",
        json={"plate": "ZZZ999", "brand": "Kia", "model_year": 2020, "capacity": 20, "campus_id": 99999},
        headers=coordinator,
    )
    assert response.status_code == 404


def test_route_cannot_use_a_bus_of_another_campus(client, coordinator):
    principal, santa_lucia = campus_ids(client, coordinator)[:2]
    bus_of_santa_lucia = client.get(f"/api/vehicles?campus_id={santa_lucia}", headers=coordinator).json()[0]
    response = client.post(
        "/api/routes/",
        json={"name": "Ruta Prueba Sede", "campus_id": principal, "vehicle_id": bus_of_santa_lucia["id"]},
        headers=coordinator,
    )
    assert response.status_code == 422
    assert "otra sede" in response.json()["detail"]


def test_drivers_are_listed_by_campus(client, coordinator):
    principal, santa_lucia = campus_ids(client, coordinator)[:2]
    in_principal = client.get(f"/api/users/drivers?campus_id={principal}", headers=coordinator).json()
    in_santa_lucia = client.get(f"/api/users/drivers?campus_id={santa_lucia}", headers=coordinator).json()
    assert in_principal and in_santa_lucia
    assert all(d["campus_id"] == principal for d in in_principal)
    assert {d["user_id"] for d in in_principal}.isdisjoint({d["user_id"] for d in in_santa_lucia})


def test_trip_with_a_driver_of_another_campus_is_rejected(client, coordinator):
    principal, santa_lucia = campus_ids(client, coordinator)[:2]
    route = next(r for r in client.get("/api/routes/", headers=coordinator).json() if r["campus_id"] == principal)
    outsider = client.get(f"/api/users/drivers?campus_id={santa_lucia}", headers=coordinator).json()[0]
    response = client.post(
        "/api/trips/", json={"route_id": route["id"], "driver_id": outsider["user_id"]}, headers=coordinator
    )
    assert response.status_code == 422
    assert "otra sede" in response.json()["detail"]


# --- Pagination ---------------------------------------------------------------------

def test_students_are_loaded_by_pages(client, coordinator):
    first = client.get("/api/students/paged?page=1&page_size=5", headers=coordinator).json()
    assert len(first["items"]) == 5
    assert first["total"] >= 10 and first["pages"] == -(-first["total"] // 5)
    second = client.get("/api/students/paged?page=2&page_size=5", headers=coordinator).json()
    assert {s["id"] for s in first["items"]}.isdisjoint({s["id"] for s in second["items"]})

    beyond = client.get("/api/students/paged?page=999&page_size=5", headers=coordinator).json()
    assert beyond["page"] == first["pages"]  # a page after the last one shows the last one

    filtered = client.get("/api/students/paged?q=jojoa", headers=coordinator).json()
    assert filtered["total"] == 2
    assert all("Jojoa" in s["last_name"] for s in filtered["items"])


def test_pagination_rejects_wrong_values(client, coordinator):
    assert client.get("/api/students/paged?page=0", headers=coordinator).status_code == 422
    assert client.get("/api/students/paged?page_size=1000", headers=coordinator).status_code == 422
    assert client.get("/api/students/paged?q=<script>", headers=coordinator).status_code == 422


def test_guardian_pages_only_show_own_children(client, guardian):
    page = client.get("/api/students/paged?page_size=50", headers=guardian).json()
    own = client.get("/api/students/", headers=guardian).json()
    assert page["total"] == len(page["items"]) == len(own)
    assert {s["id"] for s in page["items"]} == {s["id"] for s in own}


def test_users_are_loaded_by_pages_with_filters(client, coordinator):
    page = client.get("/api/users/paged?page_size=5", headers=coordinator).json()
    assert len(page["items"]) == 5 and page["total"] > 5
    drivers = client.get("/api/users/paged?role=driver&page_size=50", headers=coordinator).json()
    assert drivers["items"] and all(u["role"]["code"] == "driver" for u in drivers["items"])
    found = client.get("/api/users/paged?q=admin@rutasegura.com", headers=coordinator).json()
    assert found["total"] == 1


def test_users_pages_are_only_for_the_coordinator(client, guardian):
    assert client.get("/api/users/paged", headers=guardian).status_code == 403


# --- AI: predictions are saved and can be consulted --------------------------------

def test_ai_predictions_are_saved_in_the_history(client, coordinator):
    before = client.get("/api/ai/predictions", headers=coordinator).json()["total"]
    route = client.get("/api/routes/", headers=coordinator).json()[0]
    client.post(
        "/api/ai/delay",
        json={"route_id": route["id"], "weather_code": "rain", "road_condition_code": "bad", "stops_remaining": 3, "hour": 6},
        headers=coordinator,
    )
    history = client.get("/api/ai/predictions?page_size=5", headers=coordinator).json()
    assert history["total"] == before + 1
    latest = history["items"][0]
    assert latest["route_name"] == route["name"]
    assert latest["created_by"]  # who asked for the prediction
    assert latest["weather"] and latest["road_condition"]


def test_preview_predictions_are_not_saved(client, coordinator):
    before = client.get("/api/ai/predictions", headers=coordinator).json()["total"]
    preview = client.post(
        "/api/ai/delay",
        json={"weather_code": "clear", "road_condition_code": "good", "stops_remaining": 2, "preview": True},
        headers=coordinator,
    )
    assert preview.status_code == 200
    assert client.get("/api/ai/predictions", headers=coordinator).json()["total"] == before


# --- Automatic warnings -------------------------------------------------------------

def test_start_with_bad_conditions_warns_of_delay_and_finish_reports_missed_children(client, coordinator):
    principal = campus_ids(client, coordinator)[0]
    route = next(r for r in client.get("/api/routes/", headers=coordinator).json() if r["campus_id"] == principal)
    busy = {t["driver_id"] for t in client.get("/api/trips/?status=in_progress", headers=coordinator).json()}
    driver = next(
        d for d in client.get(f"/api/users/drivers?campus_id={principal}", headers=coordinator).json()
        if d["user_id"] not in busy
    )
    trip = client.post(
        "/api/trips/", json={"route_id": route["id"], "driver_id": driver["user_id"]}, headers=coordinator
    ).json()
    predictions_before = client.get("/api/ai/predictions", headers=coordinator).json()["total"]
    started = client.post(
        f"/api/trips/{trip['id']}/start",
        json={"weather_code": "storm", "road_condition_code": "landslide"},
        headers=coordinator,
    )
    assert started.status_code == 200, started.text
    assert client.get("/api/ai/predictions", headers=coordinator).json()["total"] == predictions_before + 1

    notifications = client.get("/api/notifications", headers=coordinator).json()
    assert any(n["title"] == "Posible retraso del bus" for n in notifications)

    finished = client.post(f"/api/trips/{trip['id']}/finish", headers=coordinator)
    assert finished.status_code == 200, finished.text
    notifications = client.get("/api/notifications", headers=coordinator).json()
    missed = [n for n in notifications if "no subió al bus" in n["title"]]
    students_of_route = [
        s for s in client.get("/api/students/", headers=coordinator).json() if s["route_id"] == route["id"] and s["active"]
    ]
    assert len(missed) >= len(students_of_route) > 0


def test_guardian_receives_missed_boarding_warning(client, coordinator):
    """The previous test finished a trip in which nobody boarded: the guardians of that route are warned."""
    guardian = login(client, "acudiente@rutasegura.com", "Acudiente123*")
    children = client.get("/api/students/", headers=guardian).json()
    finished = client.get("/api/trips/?status=finished", headers=coordinator).json()
    routes_with_missed = {t["route_id"] for t in finished}
    titles = [n["title"] for n in client.get("/api/notifications", headers=guardian).json()]
    if any(c["route_id"] in routes_with_missed for c in children):
        assert any("no subió al bus" in t for t in titles)


# --- Existing databases receive the new columns without losing data ---------------

def test_old_database_gets_the_new_campus_columns(tmp_path):
    import sqlite3

    from app.database import add_missing_columns, build_engine

    path = tmp_path / "old.db"
    with sqlite3.connect(path) as old:
        old.execute("CREATE TABLE campuses (id INTEGER PRIMARY KEY)")
        old.execute("CREATE TABLE vehicles (id INTEGER PRIMARY KEY, plate TEXT)")
        old.execute("CREATE TABLE drivers (id INTEGER PRIMARY KEY)")
        old.execute("INSERT INTO vehicles (plate) VALUES ('ABC123')")
    engine = build_engine(f"sqlite:///{path}")
    assert add_missing_columns(engine) == ["vehicles.campus_id", "drivers.campus_id"]
    assert add_missing_columns(engine) == []  # running it again changes nothing
    engine.dispose()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT plate, campus_id FROM vehicles").fetchall() == [("ABC123", None)]
