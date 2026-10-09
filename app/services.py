"""Helpers shared by the routers: catalogs, permissions, audit, notifications, geography."""

import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models
from .auth import COORDINATOR, DRIVER, GUARDIAN, MONITOR
from .models import (
    AuditLog,
    Notification,
    Route,
    Stop,
    Student,
    StudentGuardian,
    Trip,
    User,
)

# ---------------------------------------------------------------------------
# Catalogs
# ---------------------------------------------------------------------------

CATALOG_MODELS = {
    "roles": models.Role,
    "document_types": models.DocumentType,
    "relationships": models.Relationship,
    "grades": models.Grade,
    "trip_statuses": models.TripStatus,
    "event_types": models.EventType,
    "check_in_methods": models.CheckInMethod,
    "weather_conditions": models.WeatherCondition,
    "road_conditions": models.RoadCondition,
    "incident_types": models.IncidentType,
}

CATALOG_LABELS = {
    "roles": "rol",
    "document_types": "tipo de documento",
    "relationships": "parentesco",
    "grades": "grado",
    "trip_statuses": "estado de recorrido",
    "event_types": "tipo de evento",
    "check_in_methods": "método de registro",
    "weather_conditions": "clima",
    "road_conditions": "estado de la vía",
    "incident_types": "tipo de incidente",
}


def catalog_item(db: Session, catalog: str, code: str):
    """Return the active catalog row with that code, or a 422 error in Spanish."""
    model = CATALOG_MODELS[catalog]
    item = db.query(model).filter(model.code == code, model.active.is_(True)).first()
    if not item:
        raise HTTPException(422, f"El {CATALOG_LABELS[catalog]} '{code}' no existe o está inactivo.")
    return item


def get_or_404(db: Session, model, item_id: int, label: str):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(404, f"{label} no encontrado.")
    return item


# ---------------------------------------------------------------------------
# Permissions over students and trips
# ---------------------------------------------------------------------------

def guardian_student_ids(db: Session, guardian_id: int) -> set[int]:
    rows = db.query(StudentGuardian.student_id).filter(StudentGuardian.guardian_id == guardian_id).all()
    return {row[0] for row in rows}


def staff_route_ids(db: Session, user: User) -> set[int]:
    """Routes a driver or monitor works on (any trip assigned to them)."""
    rows = (
        db.query(Trip.route_id)
        .filter((Trip.driver_id == user.id) | (Trip.monitor_id == user.id))
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def visible_students_query(db: Session, user: User):
    query = db.query(Student)
    role = user.role.code
    if role == COORDINATOR:
        return query
    if role == GUARDIAN:
        return query.filter(Student.id.in_(guardian_student_ids(db, user.id) or {-1}))
    if role in (DRIVER, MONITOR):
        return query.filter(Student.route_id.in_(staff_route_ids(db, user) or {-1}))
    return query.filter(Student.id == -1)


def ensure_can_see_student(db: Session, user: User, student: Student) -> None:
    if visible_students_query(db, user).filter(Student.id == student.id).first() is None:
        raise HTTPException(403, "No tiene permiso para ver la información de este estudiante.")


def ensure_can_operate_trip(user: User, trip: Trip) -> None:
    """Only the assigned driver/monitor (or a coordinator) can operate a trip."""
    if user.role.code == COORDINATOR:
        return
    if user.id in (trip.driver_id, trip.monitor_id):
        return
    raise HTTPException(403, "Este recorrido está asignado a otro conductor.")


def ensure_trip_status(trip: Trip, *codes: str) -> None:
    if trip.status.code not in codes:
        messages = {
            "scheduled": "El recorrido ya fue iniciado o finalizado.",
            "in_progress": "El recorrido no está en curso. Inícielo primero.",
        }
        raise HTTPException(409, messages.get(codes[0], "Estado de recorrido no válido para esta acción."))


# ---------------------------------------------------------------------------
# Audit log and notifications
# ---------------------------------------------------------------------------

def audit(db: Session, user: User | None, action: str, entity: str, entity_id: int | None = None, detail: str | None = None) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity=entity,
            entity_id=entity_id,
            detail=(detail or "")[:300] or None,
        )
    )


def notify(db: Session, user_ids, kind: str, title: str, message: str) -> None:
    for user_id in set(user_ids):
        db.add(Notification(user_id=user_id, kind=kind[:30], title=title[:100], message=message[:300]))


def guardians_of(db: Session, student_ids) -> list[int]:
    if not student_ids:
        return []
    rows = db.query(StudentGuardian.guardian_id).filter(StudentGuardian.student_id.in_(list(student_ids))).all()
    return [row[0] for row in rows]


def coordinators(db: Session) -> list[int]:
    return [
        user.id
        for user in db.query(User).join(models.Role).filter(models.Role.code == COORDINATOR, User.active.is_(True))
    ]


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two GPS points, in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def route_stops(db: Session, route_id: int) -> list[Stop]:
    return db.query(Stop).filter(Stop.route_id == route_id).order_by(Stop.order).all()


def route_or_404(db: Session, route_id: int) -> Route:
    return get_or_404(db, Route, route_id, "Ruta")
