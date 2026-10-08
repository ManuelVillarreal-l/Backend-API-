"""Demo data created automatically the first time the database is empty."""

from .auth import hash_password
from .constants import Role
from .models import Route, Stop, Student, User


def seed_demo(db):
    if db.query(User).first():
        return

    coordinator = User(
        name="Coordinador RutaSegura",
        email="admin@rutasegura.com",
        password_hash=hash_password("Admin123*"),
        role=Role.COORDINATOR.value,
    )
    driver = User(
        name="Carlos Conductor",
        email="conductor@rutasegura.com",
        password_hash=hash_password("Conductor123*"),
        role=Role.DRIVER.value,
    )
    guardian = User(
        name="Laura Acudiente",
        email="acudiente@rutasegura.com",
        password_hash=hash_password("Acudiente123*"),
        role=Role.GUARDIAN.value,
    )
    db.add_all([coordinator, driver, guardian])
    db.commit()

    route = Route(name="Ruta Rural 01", description="Veredas cercanas a la institución")
    db.add(route)
    db.commit()

    stops = [
        Stop(route_id=route.id, name="Vereda El Encano", order=1, latitude=1.145, longitude=-77.079),
        Stop(route_id=route.id, name="Vereda La Laguna", order=2, latitude=1.162, longitude=-77.088),
        Stop(route_id=route.id, name="Institución Educativa", order=3, latitude=1.213, longitude=-77.281),
    ]
    db.add_all(stops)
    db.commit()

    student = Student(
        full_name="Juan Pérez Demo",
        grade="8°",
        school="Institución Educativa Rural",
        qr_code="RS-DEMO-0001",
        guardian_id=guardian.id,
        route_id=route.id,
        stop_id=stops[0].id,
    )
    db.add(student)
    db.commit()
