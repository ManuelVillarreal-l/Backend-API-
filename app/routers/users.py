from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, DRIVER, hash_password, require_roles
from ..database import get_db
from ..models import Campus, Driver, Role, User, Vehicle
from ..schemas import UserUpdate, DriverCreate, DriverOut, UserCreate, UserOut, UserPage, UserStatusUpdate
from ..services import audit, catalog_item, get_or_404, paginate
from ..structures.circular_doubly_list import CircularDoublyList

router = APIRouter()
coordinator_only = require_roles(COORDINATOR)


@router.get("/", response_model=list[UserOut], summary="Listar usuarios (solo coordinador)")
def list_users(role: str | None = None, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    query = db.query(User).join(Role)
    if role:
        query = query.filter(Role.code == role)
    return query.order_by(User.last_name, User.first_name).all()


@router.get(
    "/paged",
    response_model=UserPage,
    summary="Listar usuarios por páginas (solo coordinador)",
    description="Trae solo la página pedida. Filtros opcionales: rol, texto (nombre, correo o documento) y estado.",
)
def list_users_paged(
    page: int = Query(1, ge=1, le=100000),
    page_size: int = Query(10, ge=5, le=100),
    role: str | None = Query(None, max_length=30, pattern=r"^[a-z_]*$"),
    q: str | None = Query(None, max_length=60, pattern=r"^[A-Za-zÁÉÍÓÚáéíóúÑñÜü0-9@._ -]*$"),
    active: bool | None = None,
    db: Session = Depends(get_db),
    user=Depends(coordinator_only),
):
    query = db.query(User).join(Role)
    if role:
        query = query.filter(Role.code == role)
    if q and q.strip():
        for word in q.split():
            pattern = f"%{word}%"
            query = query.filter(
                User.first_name.ilike(pattern)
                | User.last_name.ilike(pattern)
                | User.email.ilike(pattern)
                | User.document_number.ilike(pattern)
            )
    if active is not None:
        query = query.filter(User.active.is_(active))
    result = paginate(query.order_by(User.last_name, User.first_name, User.id), page, page_size)
    return UserPage(
        items=[UserOut.model_validate(u) for u in result["rows"]],
        total=result["total"],
        page=result["page"],
        page_size=page_size,
        pages=result["pages"],
    )


@router.post("/", response_model=UserOut, status_code=201, summary="Crear usuario (solo coordinador)")
def create_user(data: UserCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    role = catalog_item(db, "roles", data.role_code)
    document_type = catalog_item(db, "document_types", data.document_type_code)
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(409, "Ya existe un usuario con ese correo.")
    if (
        db.query(User)
        .filter(User.document_type_id == document_type.id, User.document_number == data.document_number)
        .first()
    ):
        raise HTTPException(409, "Ya existe un usuario con ese documento.")
    new_user = User(
        role_id=role.id,
        document_type_id=document_type.id,
        document_number=data.document_number,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
    )
    db.add(new_user)
    db.flush()
    audit(db, user, "create", "users", new_user.id, f"Rol {role.code}")
    db.commit()
    db.refresh(new_user)
    return new_user


@router.put("/{user_id}", response_model=UserOut, summary="Editar datos de un usuario")
def update_user(user_id: int, data: UserUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    target = get_or_404(db, User, user_id, "Usuario")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "email" in changes and changes["email"] != target.email:
        raise HTTPException(
            422,
            "El correo no se puede cambiar porque la contraseña está cifrada junto con él. "
            "Cree un usuario nuevo y desactive este.",
        )
    for field, value in changes.items():
        setattr(target, field, value)
    audit(db, user, "update", "users", target.id, ", ".join(changes) or None)
    db.commit()
    db.refresh(target)
    return target


@router.patch("/{user_id}/status", response_model=UserOut, summary="Activar o desactivar un usuario")
def set_status(user_id: int, data: UserStatusUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    target = get_or_404(db, User, user_id, "Usuario")
    if target.id == user.id and not data.active:
        raise HTTPException(409, "No puede desactivar su propia cuenta.")
    target.active = data.active
    audit(db, user, "activate" if data.active else "deactivate", "users", target.id)
    db.commit()
    db.refresh(target)
    return target


# ---------------------------------------------------------------------------
# Drivers (license data) and driver rotation (circular doubly linked list)
# ---------------------------------------------------------------------------

def driver_out(driver: Driver) -> DriverOut:
    return DriverOut(
        id=driver.id,
        user_id=driver.user_id,
        full_name=driver.user.full_name,
        license_number=driver.license_number,
        license_category=driver.license_category,
        license_expires_on=driver.license_expires_on,
        license_valid=driver.license_expires_on >= date.today(),
        vehicle_plate=driver.vehicle.plate if driver.vehicle else None,
        campus_id=driver.campus_id,
        campus_name=driver.campus.name if driver.campus else None,
    )


@router.get("/drivers", response_model=list[DriverOut], summary="Conductores y sus licencias")
def list_drivers(
    campus_id: int | None = Query(None, ge=1, description="Solo los conductores de esta sede"),
    db: Session = Depends(get_db),
    user=Depends(coordinator_only),
):
    query = db.query(Driver).join(User, Driver.user_id == User.id).filter(User.active.is_(True))
    if campus_id:
        query = query.filter(Driver.campus_id == campus_id)
    return [driver_out(d) for d in query.order_by(Driver.id).all()]


@router.post("/drivers", response_model=DriverOut, status_code=201, summary="Registrar licencia de un conductor")
def create_driver(data: DriverCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    target = get_or_404(db, User, data.user_id, "Usuario")
    if target.role.code != DRIVER:
        raise HTTPException(422, "El usuario no tiene el rol de conductor.")
    if db.query(Driver).filter(Driver.user_id == target.id).first():
        raise HTTPException(409, "Ese conductor ya tiene licencia registrada.")
    if db.query(Driver).filter(Driver.license_number == data.license_number).first():
        raise HTTPException(409, "Ese número de licencia ya está registrado.")
    if data.license_expires_on < date.today():
        raise HTTPException(422, "La licencia está vencida.")
    if data.campus_id:
        get_or_404(db, Campus, data.campus_id, "Sede")
    if data.vehicle_id:
        vehicle = get_or_404(db, Vehicle, data.vehicle_id, "Vehículo")
        if data.campus_id and vehicle.campus_id and vehicle.campus_id != data.campus_id:
            raise HTTPException(422, f"El vehículo {vehicle.plate} pertenece a otra sede.")
    driver = Driver(**data.model_dump())
    db.add(driver)
    db.flush()
    audit(db, user, "create", "drivers", driver.id)
    db.commit()
    db.refresh(driver)
    return driver_out(driver)


@router.get(
    "/drivers/rotation",
    summary="Rotación de conductores (lista circular doble)",
    description="Desde el conductor indicado devuelve el anterior y el siguiente turno. Después del último sigue el primero.",
)
def driver_rotation(driver_user_id: int, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    ring = CircularDoublyList()
    for driver in db.query(Driver).order_by(Driver.id).all():
        ring.append({"user_id": driver.user_id, "full_name": driver.user.full_name})
    if not ring.find(lambda d: d["user_id"] == driver_user_id):
        raise HTTPException(404, "Conductor no encontrado en la rotación.")
    current = ring.current.data
    following = ring.next()
    ring.prev()
    previous = ring.prev()
    return {"current": current, "previous": previous, "next": following, "ring": ring.to_list()}
