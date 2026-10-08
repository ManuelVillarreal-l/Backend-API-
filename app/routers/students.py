import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..constants import Role
from ..database import get_db
from ..models import Route, Stop, Student, User
from ..schemas import StudentCreate, StudentOut

router = APIRouter()


def new_qr_code() -> str:
    return "RS-" + secrets.token_hex(6).upper()


@router.get("/", response_model=list[StudentOut], summary="Listar estudiantes")
def list_students(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Student).order_by(Student.full_name).all()


@router.post("/", response_model=StudentOut, summary="Crear estudiante")
def create_student(
    data: StudentCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.COORDINATOR)),
):
    if data.guardian_id and not db.get(User, data.guardian_id):
        raise HTTPException(404, "Acudiente no encontrado")
    if data.route_id and not db.get(Route, data.route_id):
        raise HTTPException(404, "Ruta no encontrada")
    if data.stop_id and not db.get(Stop, data.stop_id):
        raise HTTPException(404, "Parada no encontrada")

    qr_code = data.qr_code or new_qr_code()
    if db.query(Student).filter(Student.qr_code == qr_code).first():
        raise HTTPException(409, "El código QR ya existe")

    payload = data.model_dump()
    payload["qr_code"] = qr_code
    student = Student(**payload)
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentOut, summary="Ver un estudiante")
def get_student(student_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    student = db.get(Student, student_id)
    if not student:
        raise HTTPException(404, "Estudiante no encontrado")
    return student
