"""Boarding and drop-off: manual, by QR code (binary search tree) and offline sync."""

from datetime import date, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, STAFF, require_roles
from ..database import get_db
from ..models import Attendance, EventType, Route, Student, Trip, User, utc_now
from ..operations import register_event, student_state
from ..schemas import AttendanceMatrixOut, AttendanceCreate, AttendanceOut, OfflineSync, ScanCreate, SyncResult
from ..services import get_or_404
from ..structures.attendance_matrix import ABSENT, NO_TRIP, PRESENT, AttendanceMatrix
from ..structures.bst import BST

router = APIRouter()
staff_only = require_roles(*STAFF)


def existing_event(db: Session, client_event_id: str | None) -> Attendance | None:
    if not client_event_id:
        return None
    return db.query(Attendance).filter(Attendance.client_event_id == client_event_id).first()


@router.post("/", response_model=AttendanceOut, status_code=201, summary="Registrar abordaje o descenso manual")
def register_manual(data: AttendanceCreate, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    if (duplicate := existing_event(db, data.client_event_id)) is not None:
        return duplicate
    trip = get_or_404(db, Trip, data.trip_id, "Recorrido")
    student = get_or_404(db, Student, data.student_id, "Estudiante")
    event = register_event(
        db, user, trip, student, data.event_type_code, data.method_code,
        data.latitude, data.longitude, data.client_event_id,
    )
    commit_event(db)
    db.refresh(event)
    return event


@router.post(
    "/scan",
    response_model=AttendanceOut,
    status_code=201,
    summary="Registrar por código QR (árbol binario de búsqueda)",
    description=(
        "Busca al estudiante en un árbol binario de búsqueda armado con los códigos QR de la ruta. "
        "Si no está a bordo registra la subida; si está a bordo registra la bajada."
    ),
)
def scan_qr(data: ScanCreate, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    if (duplicate := existing_event(db, data.client_event_id)) is not None:
        return duplicate
    trip = get_or_404(db, Trip, data.trip_id, "Recorrido")
    index = BST()
    for student in db.query(Student).filter(Student.route_id == trip.route_id, Student.active.is_(True)):
        index.insert(student.qr_code, student)
    student = index.search(data.qr_code)
    if student is None:
        raise HTTPException(404, f"El código {data.qr_code} no es de un estudiante de esta ruta.")
    state = student_state(db, trip.id, student.id)
    if state == "delivered":
        raise HTTPException(409, f"{student.full_name} ya bajó del bus en este recorrido.")
    event_code = "boarding" if state == "pending" else "drop_off"
    event = register_event(
        db, user, trip, student, event_code, "qr", data.latitude, data.longitude, data.client_event_id
    )
    commit_event(db)
    db.refresh(event)
    return event


def commit_event(db: Session) -> None:
    """Save the event; a repeated client_event_id sent at the same time is a duplicate, not an error 500."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Este registro ya había sido guardado.")


@router.post(
    "/sync",
    response_model=SyncResult,
    summary="Sincronizar registros hechos sin señal (modo offline)",
    description=(
        "El celular guarda en una cola los registros hechos sin internet y los envía cuando vuelve la señal. "
        "Cada registro tiene un identificador único, así que reenviarlo no lo duplica."
    ),
)
def sync_offline(data: OfflineSync, db: Session = Depends(get_db), user: User = Depends(staff_only)):
    saved = duplicated = 0
    rejected: list[str] = []
    now = utc_now()
    for item in sorted(data.events, key=lambda e: e.occurred_at):
        if existing_event(db, item.client_event_id):
            duplicated += 1
            continue
        occurred = item.occurred_at
        if occurred.tzinfo is not None:  # convert to naive UTC, like every stored time
            occurred = occurred.astimezone(timezone.utc).replace(tzinfo=None)
        if occurred > now + timedelta(minutes=5) or occurred < now - timedelta(hours=24):
            rejected.append(f"{item.client_event_id}: la hora del registro no es válida.")
            continue
        trip = db.get(Trip, item.trip_id)
        student = db.get(Student, item.student_id)
        if not trip or not student:
            rejected.append(f"{item.client_event_id}: recorrido o estudiante inexistente.")
            continue
        try:
            register_event(
                db, user, trip, student, item.event_type_code, item.method_code,
                item.latitude, item.longitude, item.client_event_id, occurred,
            )
            db.commit()
            saved += 1
        except IntegrityError:
            # The same event arrived twice at the same time (two syncs in parallel).
            db.rollback()
            duplicated += 1
        except HTTPException as error:
            db.rollback()
            rejected.append(f"{item.client_event_id}: {error.detail}")
    return SyncResult(saved=saved, duplicated=duplicated, rejected=rejected)


@router.get(
    "/matrix",
    response_model=AttendanceMatrixOut,
    summary="Matriz de asistencia diaria (estudiante × día)",
    description=(
        "Arma una matriz (arreglo bidimensional): cada fila es un estudiante de la ruta y cada columna "
        "un día hábil. P = subió al bus ese día, A = hubo recorrido pero no subió, - = no hubo recorrido."
    ),
)
def attendance_matrix(
    route_id: int = Query(ge=1),
    days: int = Query(10, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(COORDINATOR)),
):
    route = get_or_404(db, Route, route_id, "Ruta")

    school_days: list[date] = []
    day = date.today()
    while len(school_days) < days:
        if day.weekday() < 5:
            school_days.append(day)
        day -= timedelta(days=1)
    school_days.reverse()

    students = (
        db.query(Student)
        .filter(Student.route_id == route.id, Student.active.is_(True))
        .order_by(Student.last_name, Student.first_name)
        .all()
    )
    matrix = AttendanceMatrix([s.id for s in students], school_days)

    trips = (
        db.query(Trip)
        .filter(Trip.route_id == route.id, Trip.scheduled_date >= school_days[0], Trip.scheduled_date <= school_days[-1])
        .all()
    )
    trip_day = {t.id: t.scheduled_date for t in trips if t.status.code != "scheduled"}
    for trip_date in set(trip_day.values()):
        if trip_date in matrix.column_index:
            matrix.fill_column(trip_date, ABSENT)

    if trip_day and students:
        boardings = (
            db.query(Attendance.student_id, Attendance.trip_id)
            .join(EventType, Attendance.event_type_id == EventType.id)
            .filter(EventType.code == "boarding", Attendance.trip_id.in_(list(trip_day)))
            .all()
        )
        for student_id, trip_id in boardings:
            trip_date = trip_day[trip_id]
            if student_id in matrix.row_index and trip_date in matrix.column_index:
                matrix.set(student_id, trip_date, PRESENT)

    return AttendanceMatrixOut(
        route_id=route.id,
        route_name=route.name,
        days=school_days,
        students=[
            {
                "student_id": s.id,
                "full_name": s.full_name,
                "present": matrix.count_row(s.id, PRESENT),
                "absent": matrix.count_row(s.id, ABSENT),
                "attendance_rate": matrix.attendance_rate(s.id),
            }
            for s in students
        ],
        cells=matrix.to_list(),
        present_per_day=[matrix.count_column(d, PRESENT) for d in school_days],
        legend={PRESENT: "Presente", ABSENT: "Ausente", NO_TRIP: "Sin recorrido"},
    )
