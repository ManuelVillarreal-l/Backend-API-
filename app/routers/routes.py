from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_roles
from ..constants import Role
from ..database import get_db
from ..models import Route, Stop
from ..schemas import RouteCreate, RouteOut, StopCreate, StopOut

router = APIRouter()


@router.get("/", response_model=list[RouteOut], summary="Listar rutas")
def list_routes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Route).order_by(Route.id).all()


@router.post("/", response_model=RouteOut, summary="Crear ruta")
def create_route(
    data: RouteCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.COORDINATOR)),
):
    if db.query(Route).filter(Route.name == data.name).first():
        raise HTTPException(409, "Ya existe una ruta con ese nombre")
    route = Route(**data.model_dump())
    db.add(route)
    db.commit()
    db.refresh(route)
    return route


@router.get("/{route_id}/stops", response_model=list[StopOut], summary="Ver paradas de una ruta")
def route_stops(route_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    if not db.get(Route, route_id):
        raise HTTPException(404, "Ruta no encontrada")
    return db.query(Stop).filter(Stop.route_id == route_id).order_by(Stop.order).all()


@router.post("/stops", response_model=StopOut, summary="Crear parada")
def create_stop(
    data: StopCreate,
    db: Session = Depends(get_db),
    user=Depends(require_roles(Role.COORDINATOR)),
):
    if not db.get(Route, data.route_id):
        raise HTTPException(404, "Ruta no encontrada")
    stop = Stop(**data.model_dump())
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop



