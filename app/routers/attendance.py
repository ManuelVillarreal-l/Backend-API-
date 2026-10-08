from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..constants import CheckInMethod, Role
from ..database import get_db
from ..models import Attendance, Stop, Student, Trip
from ..schemas import AttendanceCreate, AttendanceOut, ScanCreate

router = APIRouter()

STAFF_ROLES = (Role.DRIVER, Role.MONITOR, Role.COORDINATOR)


def save_event(
    db: Session,
    student_id: int,
    trip_id: int,
    stop_id: int | None,
    event_type: str,
    method: str,
) -> Attendance:
    if not db.get(Student, student_id):
        raise HTTPException(404, "Estudiante no encontrado")
    if not db.get(Trip, trip_id):
        raise HTTPException(404, "Recorrido no encontrado")
    if stop_id is not None and not db.get(Stop, stop_id):
        raise HTTPException(404, "Parada no encontrada")

    event = Attendance(
        student_id=student_id,
        trip_id=trip_id,
        stop_id=stop_id,
        event_type=event_type,
        method=method,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.post("/", response_model=AttendanceOut, summary="Registrar abordaje o descenso")
def register_event(
    data: AttendanceCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*STAFF_ROLES)),
):
    return save_event(db, data.student_id, data.trip_id, data.stop_id, data.event_type, data.method)


@router.post("/scan", response_model=AttendanceOut, summary="Registrar abordaje o descenso por código QR")
def scan_qr(
    data: ScanCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*STAFF_ROLES)),
):
    student = db.query(Student).filter(Student.qr_code == data.qr_code).first()
    if not student:
        raise HTTPException(404, "Código QR no reconocido")
    return save_event(db, student.id, data.trip_id, data.stop_id, data.event_type, CheckInMethod.QR.value)


@router.get("/student/{student_id}", response_model=list[AttendanceOut], summary="Historial de un estudiante")
def student_history(student_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    return (
        db.query(Attendance)
        .filter(Attendance.student_id == student_id)
        .order_by(Attendance.timestamp.desc())
        .all()
    )




