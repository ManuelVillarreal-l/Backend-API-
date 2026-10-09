"""Schools, campuses and vehicles. Includes the school hierarchy as an N-ary tree."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, get_current_user, require_roles
from ..database import get_db
from ..models import Campus, Grade, School, Student, Vehicle
from ..schemas import CampusCreate, CampusOut, SchoolCreate, SchoolOut, VehicleCreate, VehicleOut
from ..services import audit, get_or_404
from ..structures.nary_tree import NaryTree

router = APIRouter()
coordinator_only = require_roles(COORDINATOR)


@router.get("/schools", response_model=list[SchoolOut], summary="Listar instituciones y sedes")
def list_schools(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(School).order_by(School.name).all()


@router.post("/schools", response_model=SchoolOut, status_code=201, summary="Crear institución")
def create_school(data: SchoolCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    if db.query(School).filter((School.name == data.name) | (School.dane_code == data.dane_code)).first():
        raise HTTPException(409, "Ya existe una institución con ese nombre o código DANE.")
    school = School(**data.model_dump())
    db.add(school)
    db.flush()
    audit(db, user, "create", "schools", school.id)
    db.commit()
    db.refresh(school)
    return school


@router.post("/campuses", response_model=CampusOut, status_code=201, summary="Crear sede")
def create_campus(data: CampusCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    get_or_404(db, School, data.school_id, "Institución")
    if db.query(Campus).filter(Campus.school_id == data.school_id, Campus.name == data.name).first():
        raise HTTPException(409, "La institución ya tiene una sede con ese nombre.")
    campus = Campus(**data.model_dump())
    db.add(campus)
    db.flush()
    audit(db, user, "create", "campuses", campus.id)
    db.commit()
    db.refresh(campus)
    return campus


@router.get(
    "/schools/tree",
    summary="Jerarquía institución → sede → grado → estudiantes (árbol N-ario)",
    description="Cada nodo puede tener cualquier cantidad de hijos. Las hojas son los estudiantes.",
)
def school_tree(db: Session = Depends(get_db), user=Depends(coordinator_only)):
    tree = NaryTree("RutaSegura", {"type": "root"})
    grades = {g.id: g for g in db.query(Grade).all()}
    for school in db.query(School).order_by(School.name).all():
        school_node = tree.add_child(tree.root, school.name, {"type": "school", "id": school.id})
        for campus in school.campuses:
            campus_node = tree.add_child(school_node, campus.name, {"type": "campus", "id": campus.id})
            students = (
                db.query(Student)
                .filter(Student.campus_id == campus.id, Student.active.is_(True))
                .order_by(Student.last_name)
                .all()
            )
            for student in sorted(students, key=lambda s: grades[s.grade_id].sort_order):
                grade = grades[student.grade_id]
                grade_node = tree.find_child(campus_node, grade.name) or tree.add_child(
                    campus_node, grade.name, {"type": "grade", "id": grade.id}
                )
                tree.add_child(grade_node, student.full_name, {"type": "student", "id": student.id})
    return {"total_leaves": tree.count_leaves(), "tree": tree.to_dict()}


@router.get("/vehicles", response_model=list[VehicleOut], summary="Listar vehículos")
def list_vehicles(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Vehicle).order_by(Vehicle.plate).all()


@router.post("/vehicles", response_model=VehicleOut, status_code=201, summary="Registrar vehículo")
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    if db.query(Vehicle).filter(Vehicle.plate == data.plate).first():
        raise HTTPException(409, "Ya existe un vehículo con esa placa.")
    vehicle = Vehicle(**data.model_dump())
    db.add(vehicle)
    db.flush()
    audit(db, user, "create", "vehicles", vehicle.id, vehicle.plate)
    db.commit()
    db.refresh(vehicle)
    return vehicle
