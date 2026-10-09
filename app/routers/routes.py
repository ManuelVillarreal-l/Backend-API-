"""Routes, stops and road segments. Uses the graph (Dijkstra), the doubly linked list
(outbound/return itinerary) and the AI route optimizer."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import ai
from ..auth import COORDINATOR, get_current_user, require_roles
from ..database import get_db
from ..models import Campus, Route, RouteSegment, Stop, Vehicle
from ..schemas import RouteCreate, RouteOptimizationOut, RouteOut, SegmentCreate, SegmentOut, StopCreate, StopOut
from ..services import audit, get_or_404, route_or_404, route_stops
from ..structures.doubly_linked_list import DoublyLinkedList
from ..structures.graph import Graph

router = APIRouter()
coordinator_only = require_roles(COORDINATOR)


@router.get("/", response_model=list[RouteOut], summary="Listar rutas")
def list_routes(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(Route).order_by(Route.id).all()


@router.post("/", response_model=RouteOut, status_code=201, summary="Crear ruta")
def create_route(data: RouteCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    get_or_404(db, Campus, data.campus_id, "Sede")
    if data.vehicle_id:
        get_or_404(db, Vehicle, data.vehicle_id, "Vehículo")
    if db.query(Route).filter(Route.name == data.name).first():
        raise HTTPException(409, "Ya existe una ruta con ese nombre.")
    route = Route(**data.model_dump())
    db.add(route)
    db.flush()
    audit(db, user, "create", "routes", route.id, route.name)
    db.commit()
    db.refresh(route)
    return route


@router.get("/{route_id}/stops", response_model=list[StopOut], summary="Paradas de una ruta, en orden")
def list_stops(route_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    route_or_404(db, route_id)
    return route_stops(db, route_id)


@router.post("/stops", response_model=StopOut, status_code=201, summary="Agregar parada al final de la ruta")
def create_stop(data: StopCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    route_or_404(db, data.route_id)
    last_order = db.query(func.max(Stop.order)).filter(Stop.route_id == data.route_id).scalar() or 0
    if last_order >= 50:
        raise HTTPException(422, "Una ruta puede tener máximo 50 paradas.")
    stop = Stop(**data.model_dump(), order=last_order + 1)
    db.add(stop)
    db.flush()
    audit(db, user, "create", "stops", stop.id, stop.name)
    db.commit()
    db.refresh(stop)
    return stop


@router.get("/{route_id}/segments", response_model=list[SegmentOut], summary="Tramos de vía entre paradas")
def list_segments(route_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    route_or_404(db, route_id)
    return db.query(RouteSegment).filter(RouteSegment.route_id == route_id).order_by(RouteSegment.id).all()


@router.post("/{route_id}/segments", response_model=SegmentOut, status_code=201, summary="Agregar tramo de vía")
def create_segment(route_id: int, data: SegmentCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    route_or_404(db, route_id)
    if data.from_stop_id == data.to_stop_id:
        raise HTTPException(422, "Un tramo debe unir dos paradas distintas.")
    for stop_id in (data.from_stop_id, data.to_stop_id):
        stop = get_or_404(db, Stop, stop_id, "Parada")
        if stop.route_id != route_id:
            raise HTTPException(422, "Las dos paradas deben pertenecer a la ruta.")
    exists = (
        db.query(RouteSegment)
        .filter(
            ((RouteSegment.from_stop_id == data.from_stop_id) & (RouteSegment.to_stop_id == data.to_stop_id))
            | ((RouteSegment.from_stop_id == data.to_stop_id) & (RouteSegment.to_stop_id == data.from_stop_id))
        )
        .first()
    )
    if exists:
        raise HTTPException(409, "Ese tramo ya está registrado.")
    segment = RouteSegment(route_id=route_id, **data.model_dump())
    db.add(segment)
    db.flush()
    audit(db, user, "create", "route_segments", segment.id)
    db.commit()
    db.refresh(segment)
    return segment


@router.get(
    "/{route_id}/shortest-path",
    summary="Camino más corto entre dos paradas (grafo + Dijkstra)",
    description="Cada parada es un nodo y cada tramo de vía una arista con su distancia en km.",
)
def shortest_path(
    route_id: int,
    from_stop_id: int = Query(ge=1),
    to_stop_id: int = Query(ge=1),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    route_or_404(db, route_id)
    stops = {s.id: s for s in route_stops(db, route_id)}
    if from_stop_id not in stops or to_stop_id not in stops:
        raise HTTPException(422, "Las paradas deben pertenecer a la ruta.")
    graph = Graph()
    for segment in db.query(RouteSegment).filter(RouteSegment.route_id == route_id).all():
        graph.add_edge(segment.from_stop_id, segment.to_stop_id, segment.distance_km)
    path, distance = graph.shortest_path(from_stop_id, to_stop_id)
    if not path:
        raise HTTPException(404, "No hay un camino registrado entre esas paradas.")
    minutes = 0
    for a, b in zip(path, path[1:]):
        segment = (
            db.query(RouteSegment)
            .filter(
                ((RouteSegment.from_stop_id == a) & (RouteSegment.to_stop_id == b))
                | ((RouteSegment.from_stop_id == b) & (RouteSegment.to_stop_id == a))
            )
            .first()
        )
        minutes += segment.travel_minutes
    return {
        "path": [{"id": stop_id, "name": stops[stop_id].name} for stop_id in path],
        "distance_km": round(distance, 2),
        "travel_minutes": minutes,
        "algorithm": "Dijkstra con cola de prioridad",
    }


@router.get(
    "/{route_id}/itinerary",
    summary="Itinerario de ida o de regreso (lista doblemente enlazada)",
    description="La ida recorre la lista hacia adelante; el regreso la recorre hacia atrás, sin copiarla.",
)
def itinerary(
    route_id: int,
    direction: str = Query("outbound", pattern="^(outbound|return)$"),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    route_or_404(db, route_id)
    stops = DoublyLinkedList()
    for stop in route_stops(db, route_id):
        stops.append({"id": stop.id, "name": stop.name, "order": stop.order})
    ordered = stops.forward() if direction == "outbound" else stops.backward()
    return {"direction": direction, "stops": ordered}


@router.post(
    "/{route_id}/optimize",
    response_model=RouteOptimizationOut,
    summary="IA: sugerir el mejor orden de paradas",
    description="Vecino más cercano + 2-opt sobre las distancias GPS. La primera parada y el colegio se mantienen fijos.",
)
def optimize(route_id: int, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    route_or_404(db, route_id)
    return ai.optimize_route(db, route_id)
