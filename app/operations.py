"""Business rules of a trip: who can board or get off, notifications, GPS geofence and ETA."""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import Attendance, Notification, Stop, Student, Trip, User, VehicleLocation, utc_now
from .services import (
    audit,
    catalog_item,
    ensure_can_operate_trip,
    ensure_trip_status,
    guardians_of,
    haversine_km,
    notify,
    route_stops,
)
from .structures.linked_list import LinkedList

APPROACH_RADIUS_KM = 0.6
DEFAULT_SPEED_KMH = 25.0


def local_time_text(moment: datetime) -> str:
    """HH:MM in Colombia time (UTC-5) for notification messages."""
    from datetime import timedelta

    return (moment - timedelta(hours=5)).strftime("%I:%M %p").lstrip("0").lower()


def student_state(db: Session, trip_id: int, student_id: int) -> str:
    """'pending' (not on the bus), 'on_board' or 'delivered' for this trip."""
    last = (
        db.query(Attendance)
        .filter(Attendance.trip_id == trip_id, Attendance.student_id == student_id)
        .order_by(Attendance.timestamp.desc(), Attendance.id.desc())
        .first()
    )
    if not last:
        return "pending"
    return "on_board" if last.event_type.code == "boarding" else "delivered"


def register_event(
    db: Session,
    user: User,
    trip: Trip,
    student: Student,
    event_code: str,
    method_code: str,
    latitude: float | None = None,
    longitude: float | None = None,
    client_event_id: str | None = None,
    occurred_at: datetime | None = None,
) -> Attendance:
    """Validate and save a boarding or drop-off, then notify the guardians."""
    ensure_can_operate_trip(user, trip)
    ensure_trip_status(trip, "in_progress")
    event_type = catalog_item(db, "event_types", event_code)
    method = catalog_item(db, "check_in_methods", method_code)

    if student.route_id != trip.route_id or not student.active:
        raise HTTPException(422, f"{student.full_name} no pertenece a la ruta de este recorrido.")

    state = student_state(db, trip.id, student.id)
    if event_code == "boarding" and state == "on_board":
        raise HTTPException(409, f"{student.full_name} ya está a bordo.")
    if event_code == "boarding" and state == "delivered":
        raise HTTPException(409, f"{student.full_name} ya bajó del bus en este recorrido.")
    if event_code == "drop_off" and state != "on_board":
        raise HTTPException(409, f"{student.full_name} no está a bordo; no puede bajar del bus.")

    stops = route_stops(db, trip.route_id)
    if event_code == "boarding":
        stop_id = student.stop_id if trip.direction == "outbound" else (stops[-1].id if stops else None)
    else:
        stop_id = (stops[-1].id if stops else None) if trip.direction == "outbound" else student.stop_id

    event = Attendance(
        student_id=student.id,
        trip_id=trip.id,
        stop_id=stop_id,
        event_type_id=event_type.id,
        method_id=method.id,
        recorded_by=user.id,
        latitude=latitude,
        longitude=longitude,
        client_event_id=client_event_id,
        timestamp=occurred_at or utc_now(),
    )
    db.add(event)
    db.flush()

    stop_name = next((s.name for s in stops if s.id == stop_id), "la parada")
    verb = "subió al bus" if event_code == "boarding" else "bajó del bus"
    notify(
        db,
        guardians_of(db, [student.id]),
        event_code,
        f"{student.first_name} {verb}",
        f"{student.full_name} {verb} en {stop_name} a las {local_time_text(event.timestamp)}.",
    )
    audit(db, user, event_code, "attendance", event.id, student.full_name)
    return event


# ---------------------------------------------------------------------------
# GPS
# ---------------------------------------------------------------------------

def check_approaching(db: Session, trip: Trip, location: VehicleLocation) -> int:
    """Notify guardians once when the bus gets close to the stop where their child waits."""
    if trip.direction != "outbound":
        return 0
    sent = 0
    students = db.query(Student).filter(Student.route_id == trip.route_id, Student.active.is_(True)).all()
    for stop in route_stops(db, trip.route_id):
        if haversine_km(location.latitude, location.longitude, stop.latitude, stop.longitude) > APPROACH_RADIUS_KM:
            continue
        waiting = [s for s in students if s.stop_id == stop.id and student_state(db, trip.id, s.id) == "pending"]
        if not waiting:
            continue
        kind = f"near:{trip.id}:{stop.id}"
        if db.query(Notification).filter(Notification.kind == kind).first():
            continue
        names = ", ".join(s.first_name for s in waiting)
        notify(
            db,
            guardians_of(db, [s.id for s in waiting]),
            kind,
            "El bus está llegando",
            f"El bus está a menos de {int(APPROACH_RADIUS_KM * 1000)} m de {stop.name}. Prepare a {names}.",
        )
        sent += 1
    return sent


def estimate_arrival(db: Session, trip: Trip, target: Stop) -> dict:
    """ETA to a stop: distance along the route (linked list of stops) / recent average speed."""
    locations = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.trip_id == trip.id)
        .order_by(VehicleLocation.recorded_at.desc())
        .limit(5)
        .all()
    )
    if not locations:
        raise HTTPException(404, "El bus todavía no ha enviado su ubicación.")
    latest = locations[0]

    stops = LinkedList()
    for stop in route_stops(db, trip.route_id):
        stops.append(stop)
    all_stops = stops.to_list()
    if trip.direction == "return":
        all_stops.reverse()

    # The next stop is the closest one that is not behind the bus.
    nearest_index = min(
        range(len(all_stops)),
        key=lambda i: haversine_km(latest.latitude, latest.longitude, all_stops[i].latitude, all_stops[i].longitude),
    )
    target_index = next((i for i, s in enumerate(all_stops) if s.id == target.id), None)
    if target_index is None:
        raise HTTPException(422, "La parada no pertenece a la ruta del recorrido.")

    if target_index < nearest_index:
        distance = 0.0  # the bus already passed this stop
    else:
        distance = haversine_km(
            latest.latitude, latest.longitude, all_stops[nearest_index].latitude, all_stops[nearest_index].longitude
        )
        for a, b in zip(all_stops[nearest_index:target_index], all_stops[nearest_index + 1 : target_index + 1]):
            distance += haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)

    speeds = [loc.speed_kmh for loc in locations if loc.speed_kmh and loc.speed_kmh > 5]
    speed = sum(speeds) / len(speeds) if speeds else DEFAULT_SPEED_KMH
    return {
        "trip_id": trip.id,
        "stop_id": target.id,
        "stop_name": target.name,
        "distance_km": round(distance, 2),
        "eta_minutes": int(round(distance / speed * 60)),
        "speed_used_kmh": round(speed, 1),
        "bus_location": latest,
    }
