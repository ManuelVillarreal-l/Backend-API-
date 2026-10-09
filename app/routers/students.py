"""Students: each role only sees the students it is allowed to.

- Coordinator: all students.
- Driver / monitor: students of the routes they work on.
- Guardian: only their own children.
"""

import secrets
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import ai
from ..auth import COORDINATOR, GUARDIAN, get_current_user, require_roles
from ..database import get_db
from ..models import Attendance, Campus, Route, Stop, Student, StudentGuardian, User
from ..schemas import AbsenceRiskOut, CatalogRef, AttendanceOut, GuardianOut, StudentCreate, StudentOut
from ..services import audit, catalog_item, ensure_can_see_student, get_or_404, visible_students_query
from ..structures.avl import AVLTree

router = APIRouter()
coordinator_only = require_roles(COORDINATOR)


def student_out(student: Student) -> StudentOut:
    return StudentOut(
        id=student.id,
        first_name=student.first_name,
        last_name=student.last_name,
        full_name=student.full_name,
        document_number=student.document_number,
        document_type=CatalogRef.model_validate(student.document_type),
        birth_date=student.birth_date,
        grade=CatalogRef.model_validate(student.grade),
        campus_id=student.campus_id,
        route_id=student.route_id,
        stop_id=student.stop_id,
        qr_code=student.qr_code,
        active=student.active,
        guardians=guardian_links(student),
    )


def guardian_links(student: Student) -> list[GuardianOut]:
    return [
        GuardianOut(
            guardian_id=link.guardian_id,
            full_name=link.guardian.full_name,
            phone=link.guardian.phone,
            relationship=link.kinship.name,
            is_primary=link.is_primary,
        )
        for link in student.guardians
    ]


def normalize(text: str) -> str:
    replacements = str.maketrans("áéíóúüñÁÉÍÓÚÜÑ", "aeiouunAEIOUUN")
    return text.translate(replacements).lower().strip()


@router.get("/", response_model=list[StudentOut], summary="Listar estudiantes visibles para mi rol")
def list_students(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    students = visible_students_query(db, user).order_by(Student.last_name, Student.first_name).all()
    return [student_out(s) for s in students]


@router.get(
    "/search",
    response_model=list[StudentOut],
    summary="Buscar estudiantes por nombre (árbol AVL)",
    description="Se construye un índice AVL con nombre y apellido; la búsqueda por prefijo es O(log n + k).",
)
def search_students(
    q: str = Query(min_length=1, max_length=50, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü ]+$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    index = AVLTree()
    for student in visible_students_query(db, user).all():
        index.insert((normalize(student.first_name + " " + student.last_name), student.id), student)
        index.insert((normalize(student.last_name + " " + student.first_name), student.id), student)
    found, seen = [], set()
    for student in index.prefix_search(normalize(q), limit=40):
        if student.id not in seen:
            seen.add(student.id)
            found.append(student_out(student))
    return found[:20]


@router.post("/", response_model=StudentOut, status_code=201, summary="Registrar estudiante (solo coordinador)")
def create_student(data: StudentCreate, db: Session = Depends(get_db), user: User = Depends(coordinator_only)):
    document_type = catalog_item(db, "document_types", data.document_type_code)
    grade = catalog_item(db, "grades", data.grade_code)
    get_or_404(db, Campus, data.campus_id, "Sede")

    age = (date.today() - data.birth_date).days / 365.25
    if not 3 <= age <= 20:
        raise HTTPException(422, "La fecha de nacimiento no corresponde a un estudiante (entre 3 y 20 años).")
    if (
        db.query(Student)
        .filter(Student.document_type_id == document_type.id, Student.document_number == data.document_number)
        .first()
    ):
        raise HTTPException(409, "Ya existe un estudiante con ese documento.")
    if data.route_id:
        get_or_404(db, Route, data.route_id, "Ruta")
    if data.stop_id:
        stop = get_or_404(db, Stop, data.stop_id, "Parada")
        if stop.route_id != data.route_id:
            raise HTTPException(422, "La parada no pertenece a la ruta elegida.")
    if sum(1 for g in data.guardians if g.is_primary) > 1:
        raise HTTPException(422, "Solo un acudiente puede ser el principal.")

    student = Student(
        document_type_id=document_type.id,
        document_number=data.document_number,
        first_name=data.first_name,
        last_name=data.last_name,
        birth_date=data.birth_date,
        grade_id=grade.id,
        campus_id=data.campus_id,
        route_id=data.route_id,
        stop_id=data.stop_id,
        qr_code="RS-" + secrets.token_hex(4).upper(),
    )
    db.add(student)
    db.flush()
    for link in data.guardians:
        guardian = get_or_404(db, User, link.guardian_id, "Acudiente")
        if guardian.role.code != GUARDIAN:
            raise HTTPException(422, f"{guardian.full_name} no tiene el rol de acudiente.")
        kinship = catalog_item(db, "relationships", link.relationship_code)
        db.add(
            StudentGuardian(
                student_id=student.id, guardian_id=guardian.id, relationship_id=kinship.id, is_primary=link.is_primary
            )
        )
    audit(db, user, "create", "students", student.id, student.full_name)
    db.commit()
    db.refresh(student)
    return student_out(student)


@router.get("/{student_id}", response_model=StudentOut, summary="Ver un estudiante")
def get_student(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    student = get_or_404(db, Student, student_id, "Estudiante")
    ensure_can_see_student(db, user, student)
    return student_out(student)


@router.get("/{student_id}/history", response_model=list[AttendanceOut], summary="Historial de abordaje y descenso")
def student_history(
    student_id: int,
    limit: int = Query(60, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = get_or_404(db, Student, student_id, "Estudiante")
    ensure_can_see_student(db, user, student)
    return (
        db.query(Attendance)
        .filter(Attendance.student_id == student_id)
        .order_by(Attendance.timestamp.desc())
        .limit(limit)
        .all()
    )


@router.get(
    "/{student_id}/absence-risk",
    response_model=AbsenceRiskOut,
    summary="IA: riesgo de ausencia del estudiante",
    description="Calcula la tasa histórica de ausencias y la compara con los días de lluvia.",
)
def student_absence_risk(student_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    student = get_or_404(db, Student, student_id, "Estudiante")
    ensure_can_see_student(db, user, student)
    return ai.absence_risk(db, student)
