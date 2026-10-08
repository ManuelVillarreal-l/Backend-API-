from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..constants import Role, TripStatus
from ..database import get_db
from ..models import Route, Trip, User, utc_now
from ..schemas import TripCreate, TripOut

router = APIRouter()

TRIP_MANAGERS = (Role.DRIVER, Role.COORDINATOR)


def get_trip_or_404(db: Session, trip_id: int) -> Trip:
    trip = db.get(Trip, trip_id)
    if not trip:
        raise HTTPException(404, "Recorrido no encontrado")
    return trip


@router.get("/", response_model=list[TripOut], summary="Listar recorridos")
def list_trips(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Trip).order_by(Trip.id.desc()).all()


@router.post("/", response_model=TripOut, summary="Crear recorrido")
def create_trip(
    data: TripCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*TRIP_MANAGERS)),
):
    if not db.get(Route, data.route_id):
        raise HTTPException(404, "Ruta no encontrada")
    if data.driver_id is not None:
        driver = db.get(User, data.driver_id)
        if not driver or driver.role != Role.DRIVER.value:
            raise HTTPException(404, "Conductor no encontrado")
    trip = Trip(**data.model_dump())
    db.add(trip)
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/start", response_model=TripOut, summary="Iniciar recorrido")
def start_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*TRIP_MANAGERS)),
):
    trip = get_trip_or_404(db, trip_id)
    if trip.status == TripStatus.FINISHED.value:
        raise HTTPException(400, "El recorrido ya finalizó")
    trip.status = TripStatus.IN_PROGRESS.value
    trip.started_at = utc_now()
    db.commit()
    db.refresh(trip)
    return trip


@router.post("/{trip_id}/finish", response_model=TripOut, summary="Finalizar recorrido")
def finish_trip(
    trip_id: int,
    db: Session = Depends(get_db),
    user=Depends(require_roles(*TRIP_MANAGERS)),
):
    trip = get_trip_or_404(db, trip_id)
    trip.status = TripStatus.FINISHED.value
    trip.finished_at = utc_now()
    db.commit()
    db.refresh(trip)
    return trip
