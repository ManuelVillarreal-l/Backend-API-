"""Schools, campuses and vehicles. Includes the school hierarchy as an N-ary tree."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, get_current_user, require_roles
from ..database import get_db
from ..models import Campus, Grade, Route, School, Student, Vehicle
from ..schemas import CampusUpdate, SchoolUpdate, VehicleUpdate, CampusCreate, CampusOut, SchoolCreate, SchoolOut, VehicleCreate, VehicleOut
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


# ---------------------------------------------------------------------------
# Edit / delete (CRUD)
# ---------------------------------------------------------------------------

def apply_changes(item, data) -> list[str]:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(item, field, value)
    return list(changes)


@router.put("/schools/{school_id}", response_model=SchoolOut, summary="Editar institución")
def update_school(school_id: int, data: SchoolUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    school = get_or_404(db, School, school_id, "Institución")
    if data.name and db.query(School).filter(School.name == data.name, School.id != school.id).first():
        raise HTTPException(409, "Ya existe una institución con ese nombre.")
    fields = apply_changes(school, data)
    audit(db, user, "update", "schools", school.id, ", ".join(fields) or None)
    db.commit()
    db.refresh(school)
    return school


@router.delete("/schools/{school_id}", response_model=SchoolOut, summary="Desactivar institución")
def deactivate_school(school_id: int, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    school = get_or_404(db, School, school_id, "Institución")
    school.active = False
    audit(db, user, "deactivate", "schools", school.id)
    db.commit()
    db.refresh(school)
    return school


@router.put("/campuses/{campus_id}", response_model=CampusOut, summary="Editar sede")
def update_campus(campus_id: int, data: CampusUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    campus = get_or_404(db, Campus, campus_id, "Sede")
    fields = apply_changes(campus, data)
    audit(db, user, "update", "campuses", campus.id, ", ".join(fields) or None)
    db.commit()
    db.refresh(campus)
    return campus


@router.delete("/campuses/{campus_id}", summary="Eliminar sede (solo si no tiene estudiantes ni rutas)")
def delete_campus(campus_id: int, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    campus = get_or_404(db, Campus, campus_id, "Sede")
    students = db.query(Student).filter(Student.campus_id == campus.id).count()
    routes = db.query(Route).filter(Route.campus_id == campus.id).count()
    if students or routes:
        raise HTTPException(409, f"No se puede eliminar: la sede tiene {students} estudiante(s) y {routes} ruta(s).")
    db.delete(campus)
    audit(db, user, "delete", "campuses", campus_id)
    db.commit()
    return {"deleted": True, "campus_id": campus_id}


@router.put("/vehicles/{vehicle_id}", response_model=VehicleOut, summary="Editar vehículo")
def update_vehicle(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    vehicle = get_or_404(db, Vehicle, vehicle_id, "Vehículo")
    fields = apply_changes(vehicle, data)
    audit(db, user, "update", "vehicles", vehicle.id, ", ".join(fields) or None)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/vehicles/{vehicle_id}", response_model=VehicleOut, summary="Desactivar vehículo")
def deactivate_vehicle(vehicle_id: int, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    vehicle = get_or_404(db, Vehicle, vehicle_id, "Vehículo")
    vehicle.active = False
    audit(db, user, "deactivate", "vehicles", vehicle.id, vehicle.plate)
    db.commit()
    db.refresh(vehicle)
    return vehicle
