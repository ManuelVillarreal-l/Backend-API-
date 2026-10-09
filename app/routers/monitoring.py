"""Incidents, notifications, dashboard report and audit log."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, STAFF, get_current_user, require_roles
from ..database import get_db
from ..models import (
    Attendance,
    AuditLog,
    EventType,
    Incident,
    Notification,
    Route,
    Student,
    Trip,
    TripStatus,
    User,
    VehicleLocation,
    utc_now,
)
from ..schemas import IncidentCreate, IncidentOut, NotificationOut
from ..services import audit, catalog_item, coordinators, get_or_404, notify

router = APIRouter()


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

@router.post(
    "/incidents",
    response_model=IncidentOut,
    status_code=201,
    summary="Reportar incidente (botón de emergencia)",
    description="Avisa de inmediato a todos los coordinadores, con la ubicación GPS si está disponible.",
)
def report_incident(data: IncidentCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    incident_type = catalog_item(db, "incident_types", data.incident_type_code)
    if data.trip_id:
        get_or_404(db, Trip, data.trip_id, "Recorrido")
    incident = Incident(
        trip_id=data.trip_id,
        incident_type_id=incident_type.id,
        reported_by=user.id,
        description=data.description,
        latitude=data.latitude,
        longitude=data.longitude,
    )
    db.add(incident)
    db.flush()
    urgency = "🚨 " if incident_type.severity == 3 else ""
    notify(
        db,
        coordinators(db),
        "incident",
        f"{urgency}Incidente: {incident_type.name}",
        f"{user.full_name} reportó: {data.description}",
    )
    audit(db, user, "report", "incidents", incident.id, incident_type.code)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("/incidents", response_model=list[IncidentOut], summary="Listar incidentes")
def list_incidents(
    open_only: bool = False, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))
):
    query = db.query(Incident)
    if user.role.code != COORDINATOR:
        query = query.filter(Incident.reported_by == user.id)
    if open_only:
        query = query.filter(Incident.resolved_at.is_(None))
    return query.order_by(Incident.created_at.desc()).limit(100).all()


@router.patch("/incidents/{incident_id}/resolve", response_model=IncidentOut, summary="Marcar incidente como resuelto")
def resolve_incident(incident_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR))):
    incident = get_or_404(db, Incident, incident_id, "Incidente")
    if incident.resolved_at:
        raise HTTPException(409, "El incidente ya estaba resuelto.")
    incident.resolved_at = utc_now()
    audit(db, user, "resolve", "incidents", incident.id)
    db.commit()
    db.refresh(incident)
    return incident


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@router.get("/notifications", response_model=list[NotificationOut], summary="Mis notificaciones")
def my_notifications(
    unread_only: bool = False, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    return query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(50).all()


@router.post("/notifications/read-all", summary="Marcar todas mis notificaciones como leídas")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: utc_now()}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


# ---------------------------------------------------------------------------
# Dashboard report
# ---------------------------------------------------------------------------

@router.get("/reports/summary", summary="Resumen para el panel del coordinador")
def summary(db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR))):
    today = date.today()
    students = db.query(Student).filter(Student.active.is_(True)).all()
    routes = db.query(Route).filter(Route.active.is_(True)).all()
    trips = db.query(Trip).join(TripStatus).all()
    boarding_id = db.query(EventType).filter(EventType.code == "boarding").one().id

    in_progress = []
    for trip in (t for t in trips if t.status.code == "in_progress"):
        last = (
            db.query(VehicleLocation)
            .filter(VehicleLocation.trip_id == trip.id)
            .order_by(VehicleLocation.recorded_at.desc())
            .first()
        )
        route = next(r for r in routes if r.id == trip.route_id)
        in_progress.append(
            {
                "trip_id": trip.id,
                "route_id": route.id,
                "route_name": route.name,
                "latitude": last.latitude if last else None,
                "longitude": last.longitude if last else None,
                "last_seen": last.recorded_at if last else None,
            }
        )

    # Attendance rate of the last 7 days (outbound trips): students boarded / students assigned.
    series = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        day_trips = [t for t in trips if t.scheduled_date == day and t.direction == "outbound" and t.status.code == "finished"]
        assigned = sum(sum(1 for s in students if s.route_id == t.route_id) for t in day_trips)
        boarded = 0
        if day_trips:
            boarded = (
                db.query(Attendance.student_id, Attendance.trip_id)
                .filter(Attendance.trip_id.in_([t.id for t in day_trips]), Attendance.event_type_id == boarding_id)
                .distinct()
                .count()
            )
        series.append(
            {"date": day.isoformat(), "assigned": assigned, "boarded": boarded,
             "rate": round(boarded / assigned * 100, 1) if assigned else None}
        )

    open_incidents = db.query(Incident).filter(Incident.resolved_at.is_(None)).count()
    return {
        "students": len(students),
        "routes": len(routes),
        "trips_in_progress": in_progress,
        "trips_scheduled": sum(1 for t in trips if t.status.code == "scheduled"),
        "open_incidents": open_incidents,
        "attendance_last_7_days": series,
    }


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

@router.get("/audit", summary="Bitácora de auditoría (quién hizo qué y cuándo)")
def audit_log(
    limit: int = Query(100, ge=1, le=500), db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR))
):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()
    names = {u.id: u.full_name for u in db.query(User).all()}
    return [
        {
            "id": row.id,
            "user": names.get(row.user_id, "Sistema"),
            "action": row.action,
            "entity": row.entity,
            "entity_id": row.entity_id,
            "detail": row.detail,
            "created_at": row.created_at,
        }
        for row in rows
    ]
