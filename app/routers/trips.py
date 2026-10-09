"""Trips: schedule, start, finish, boarding queue (queue), undo (stack), GPS and ETA."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, DRIVER, GUARDIAN, MONITOR, STAFF, get_current_user, require_roles
from ..database import get_db
from ..models import Attendance, Route, Stop, Student, Trip, User, Vehicle, VehicleLocation, utc_now
from ..operations import check_approaching, estimate_arrival, student_state
from ..schemas import AttendanceOut, EtaOut, LocationCreate, LocationOut, TripCreate, TripOut, TripStart
from ..services import (
    audit,
    catalog_item,
    ensure_can_operate_trip,
    ensure_trip_status,
    get_or_404,
    guardian_student_ids,
    guardians_of,
    notify,
    route_stops,
)
from ..structures.circular_list import CircularList
from ..structures.queue import Queue
from ..structures.stack import Stack

router = APIRouter()


def visible_trips_query(db: Session, user: User):
    query = db.query(Trip)
    role = user.role.code
    if role == COORDINATOR:
        return query
    if role in (DRIVER, MONITOR):
        return query.filter((Trip.driver_id == user.id) | (Trip.monitor_id == user.id))
    if role == GUARDIAN:
        route_ids = {
            s.route_id
            for s in db.query(Student).filter(Student.id.in_(guardian_student_ids(db, user.id) or {-1})).all()
            if s.route_id
        }
        return query.filter(Trip.route_id.in_(route_ids or {-1}))
    return query.filter(Trip.id == -1)


def trip_for(db: Session, user: User, trip_id: int) -> Trip:
    trip = get_or_404(db, Trip, trip_id, "Recorrido")
    if visible_trips_query(db, user).filter(Trip.id == trip.id).first() is None:
        raise HTTPException(403, "No tiene acceso a este recorrido.")
    return trip


@router.get("/", response_model=list[TripOut], summary="Listar recorridos visibles para mi rol")
def list_trips(
    status: str | None = Query(None, pattern=r"^(scheduled|in_progress|finished)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = visible_trips_query(db, user)
    trips = query.order_by(Trip.scheduled_date.desc(), Trip.id.desc()).limit(200).all()
    if status:
        trips = [t for t in trips if t.status.code == status]
    return trips


@router.post("/", response_model=TripOut, status_code=201, summary="Programar recorrido")
def create_trip(data: TripCreate, db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR, DRIVER))):
    route = get_or_404(db, Route, data.route_id, "Ruta")
    driver = get_or_404(db, User, data.driver_id, "Conductor")
    if driver.role.code != DRIVER or not driver.active:
        raise HTTPException(422, "El usuario elegido no es un conductor activo.")
    if user.role.code == DRIVER and driver.id != user.id:
        raise HTTPException(403, "Un conductor solo puede programar sus propios recorridos.")
    if data.monitor_id:
        monitor = get_or_404(db, User, data.monitor_id, "Monitor")
        if monitor.role.code != MONITOR:
            raise HTTPException(422, "El usuario elegido como monitor no tiene ese rol.")
    vehicle_id = data.vehicle_id or route.vehicle_id
    if vehicle_id:
        get_or_404(db, Vehicle, vehicle_id, "Vehículo")
    scheduled = data.scheduled_date or date.today()
    if scheduled < date.today() - timedelta(days=1) or scheduled > date.today() + timedelta(days=60):
        raise HTTPException(422, "La fecha debe estar entre hoy y los próximos 60 días.")
    active_driver_trip = (
        db.query(Trip).filter(Trip.driver_id == driver.id).all()
    )
    if any(t.status.code == "in_progress" for t in active_driver_trip):
        raise HTTPException(409, "El conductor ya tiene un recorrido en curso.")

    trip = Trip(
        route_id=route.id,
        driver_id=driver.id,
        monitor_id=data.monitor_id,
        vehicle_id=vehicle_id,
        status_id=catalog_item(db, "trip_statuses", "scheduled").id,
        direction=data.direction,
        scheduled_date=scheduled,
    )
    db.add(trip)
    db.flush()
    audit(db, user, "create", "trips", trip.id, route.name)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=TripOut, summary="Ver un recorrido")
def get_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return trip_for(db, user, trip_id)


@router.post(
    "/{trip_id}/start",
    response_model=TripOut,
    summary="Iniciar recorrido",
    description="Se registra el clima y el estado de la vía (tomados de los catálogos de la base de datos).",
)
def start_trip(
    trip_id: int,
    data: TripStart,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(COORDINATOR, DRIVER)),
):
    trip = trip_for(db, user, trip_id)
    ensure_can_operate_trip(user, trip)
    ensure_trip_status(trip, "scheduled")
    weather = catalog_item(db, "weather_conditions", data.weather_code)
    road = catalog_item(db, "road_conditions", data.road_condition_code)
    trip.status_id = catalog_item(db, "trip_statuses", "in_progress").id
    trip.weather_id = weather.id
    trip.road_condition_id = road.id
    trip.started_at = utc_now()

    route = db.get(Route, trip.route_id)
    student_ids = [s.id for s in db.query(Student).filter(Student.route_id == trip.route_id, Student.active.is_(True))]
    notify(
        db,
        guardians_of(db, student_ids),
        "trip_started",
        "El recorrido comenzó",
        f"El bus de la {route.name} salió. Clima: {weather.name.lower()}, vía: {road.name.lower()}.",
    )
    audit(db, user, "start", "trips", trip.id)
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/finish", response_model=TripOut, summary="Finalizar recorrido")
def finish_trip(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR, DRIVER))):
    trip = trip_for(db, user, trip_id)
    ensure_can_operate_trip(user, trip)
    ensure_trip_status(trip, "in_progress")
    on_board = [
        s
        for s in db.query(Student).filter(Student.route_id == trip.route_id)
        if student_state(db, trip.id, s.id) == "on_board"
    ]
    if on_board:
        names = ", ".join(s.full_name for s in on_board)
        raise HTTPException(409, f"No se puede finalizar: todavía están a bordo {names}.")
    trip.status_id = catalog_item(db, "trip_statuses", "finished").id
    trip.finished_at = utc_now()
    audit(db, user, "finish", "trips", trip.id)
    db.commit()
    db.refresh(trip)
    return trip


@router.get("/{trip_id}/events", response_model=list[AttendanceOut], summary="Abordajes y descensos del recorrido")
def trip_events(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    trip = trip_for(db, user, trip_id)
    return db.query(Attendance).filter(Attendance.trip_id == trip.id).order_by(Attendance.timestamp, Attendance.id).all()


@router.get(
    "/{trip_id}/queue",
    summary="Cola de abordaje (cola FIFO)",
    description="Estudiantes que faltan por subir, en el orden en que el bus pasa por sus paradas.",
)
def boarding_queue(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    trip = trip_for(db, user, trip_id)
    pending = Queue()
    students = db.query(Student).filter(Student.route_id == trip.route_id, Student.active.is_(True)).all()
    for stop in route_stops(db, trip.route_id):
        for student in sorted((s for s in students if s.stop_id == stop.id), key=lambda s: s.last_name):
            if student_state(db, trip.id, student.id) == "pending":
                pending.enqueue({"student_id": student.id, "full_name": student.full_name, "stop": stop.name})
    return {"pending": len(pending), "next": pending.peek(), "queue": pending.to_list()}


@router.post(
    "/{trip_id}/undo",
    response_model=AttendanceOut,
    summary="Deshacer el último registro (pila LIFO)",
    description="Saca de la pila el registro más reciente del recorrido y lo elimina. Útil si el conductor se equivocó.",
)
def undo_last_event(trip_id: int, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    trip = trip_for(db, user, trip_id)
    ensure_can_operate_trip(user, trip)
    ensure_trip_status(trip, "in_progress")
    history = Stack()
    for event in db.query(Attendance).filter(Attendance.trip_id == trip.id).order_by(Attendance.timestamp, Attendance.id):
        history.push(event)
    last = history.pop()
    if last is None:
        raise HTTPException(404, "No hay registros para deshacer en este recorrido.")
    if (utc_now() - last.timestamp).total_seconds() > 10 * 60:
        raise HTTPException(409, "Solo se pueden deshacer registros de los últimos 10 minutos.")
    removed = AttendanceOut.model_validate(last)
    db.delete(last)
    audit(db, user, "undo", "attendance", removed.id)
    db.commit()
    return removed


# ---------------------------------------------------------------------------
# GPS tracking
# ---------------------------------------------------------------------------

@router.post(
    "/{trip_id}/locations",
    status_code=201,
    summary="Enviar ubicación GPS del bus",
    description="El celular del conductor la envía cada pocos segundos. Si el bus se acerca a una parada, se avisa a los acudientes.",
)
def post_location(
    trip_id: int,
    data: LocationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(COORDINATOR, DRIVER, MONITOR)),
):
    trip = trip_for(db, user, trip_id)
    ensure_can_operate_trip(user, trip)
    ensure_trip_status(trip, "in_progress")
    location = VehicleLocation(trip_id=trip.id, **data.model_dump())
    db.add(location)
    db.flush()
    notified = check_approaching(db, trip, location)
    db.commit()
    return {"saved": True, "approach_notifications": notified}


@router.get("/{trip_id}/locations/latest", response_model=LocationOut, summary="Última ubicación del bus")
def latest_location(trip_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    trip = trip_for(db, user, trip_id)
    location = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.trip_id == trip.id)
        .order_by(VehicleLocation.recorded_at.desc())
        .first()
    )
    if not location:
        raise HTTPException(404, "El bus todavía no ha enviado su ubicación.")
    return location


@router.get("/{trip_id}/locations", response_model=list[LocationOut], summary="Recorrido GPS del bus (últimos puntos)")
def location_trail(
    trip_id: int, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    trip = trip_for(db, user, trip_id)
    points = (
        db.query(VehicleLocation)
        .filter(VehicleLocation.trip_id == trip.id)
        .order_by(VehicleLocation.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return list(reversed(points))


@router.get("/{trip_id}/eta", response_model=EtaOut, summary="Tiempo estimado de llegada a una parada")
def trip_eta(
    trip_id: int, stop_id: int = Query(ge=1), db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    trip = trip_for(db, user, trip_id)
    stop = get_or_404(db, Stop, stop_id, "Parada")
    return estimate_arrival(db, trip, stop)


# ---------------------------------------------------------------------------
# Monitor rotation (circular list)
# ---------------------------------------------------------------------------

@router.get(
    "/rotation/monitors",
    summary="Turnos de monitores para los próximos días (lista circular)",
    description="Asigna un monitor por día hábil recorriendo la lista circular; al llegar al último vuelve al primero.",
)
def monitor_rotation(
    days: int = Query(10, ge=1, le=60), db: Session = Depends(get_db), user: User = Depends(require_roles(COORDINATOR))
):
    from ..models import Role

    ring = CircularList()
    for monitor in db.query(User).join(Role).filter(Role.code == MONITOR, User.active.is_(True)).order_by(User.id):
        ring.append({"user_id": monitor.id, "full_name": monitor.full_name})
    if len(ring) == 0:
        raise HTTPException(404, "No hay monitores activos.")
    school_days = []
    day = date.today()
    while len(school_days) < days:
        if day.weekday() < 5:
            school_days.append(day)
        day += timedelta(days=1)
    assigned = ring.cycle(days)
    return [{"date": d.isoformat(), "monitor": m} for d, m in zip(school_days, assigned)]
