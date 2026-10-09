"""AI endpoints: delay prediction (regression), current weather (Open-Meteo) and the
data-structures map used in the presentation."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import ai
from ..auth import STAFF, COORDINATOR, get_current_user, require_roles
from ..database import get_db
from ..models import DelayPrediction, Route, User
from ..schemas import CatalogRef, CurrentWeatherOut, DelayPredictionOut, DelayPredictionRequest
from ..services import catalog_item, get_or_404

router = APIRouter()


@router.post(
    "/ai/delay",
    response_model=DelayPredictionOut,
    summary="IA: predecir el retraso de un recorrido",
    description=(
        "Entrena una regresión lineal múltiple con los recorridos finalizados (clima, vía, paradas y hora) "
        "y predice el retraso. El clima y la vía se eligen de los catálogos de la base de datos."
    ),
)
def predict_delay(data: DelayPredictionRequest, db: Session = Depends(get_db), user: User = Depends(require_roles(*STAFF))):
    weather = catalog_item(db, "weather_conditions", data.weather_code)
    road = catalog_item(db, "road_conditions", data.road_condition_code)
    if data.route_id:
        get_or_404(db, Route, data.route_id, "Ruta")
    result = ai.predict_delay(db, weather, road, data.stops_remaining, data.hour)
    db.add(
        DelayPrediction(
            route_id=data.route_id,
            weather_id=weather.id,
            road_condition_id=road.id,
            stops_remaining=data.stops_remaining,
            predicted_minutes=result["estimated_delay_minutes"],
            model=result["model"],
            created_by=user.id,
        )
    )
    db.commit()
    return result


@router.get(
    "/ai/weather",
    response_model=CurrentWeatherOut,
    summary="Clima actual real en un punto (Open-Meteo)",
    description="Consulta el servicio meteorológico Open-Meteo y lo traduce al catálogo de climas de la base de datos.",
)
def current_weather(
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        data = ai.fetch_current_weather(latitude, longitude)
    except (OSError, ValueError, KeyError):
        raise HTTPException(503, "No se pudo consultar el servicio del clima. Elija el clima manualmente.")
    condition = ai.weather_condition_for_code(db, data["weather_code"])
    return CurrentWeatherOut(
        **data,
        condition=CatalogRef.model_validate(condition) if condition else None,
        source="Open-Meteo",
    )


STRUCTURES = [
    {"name": "Grafo + Dijkstra", "file": "structures/graph.py", "complexity": "O((V + E) log V)",
     "use": "Camino más corto entre paradas usando los tramos de vía.", "endpoint": "GET /api/routes/{id}/shortest-path"},
    {"name": "Cola (FIFO)", "file": "structures/queue.py", "complexity": "O(1) por operación",
     "use": "Estudiantes que faltan por subir, en orden de parada.", "endpoint": "GET /api/trips/{id}/queue"},
    {"name": "Pila (LIFO)", "file": "structures/stack.py", "complexity": "O(1) por operación",
     "use": "Deshacer el último abordaje o descenso registrado.", "endpoint": "POST /api/trips/{id}/undo"},
    {"name": "Lista enlazada simple", "file": "structures/linked_list.py", "complexity": "O(n) recorrido",
     "use": "Secuencia de paradas para calcular el tiempo de llegada (ETA).", "endpoint": "GET /api/trips/{id}/eta"},
    {"name": "Lista doblemente enlazada", "file": "structures/doubly_linked_list.py", "complexity": "O(n) en ambos sentidos",
     "use": "Itinerario de ida (hacia adelante) y de regreso (hacia atrás).", "endpoint": "GET /api/routes/{id}/itinerary"},
    {"name": "Lista circular", "file": "structures/circular_list.py", "complexity": "O(k) para k turnos",
     "use": "Turnos de monitores por día; tras el último vuelve al primero.", "endpoint": "GET /api/trips/rotation/monitors"},
    {"name": "Lista circular doble", "file": "structures/circular_doubly_list.py", "complexity": "O(1) siguiente/anterior",
     "use": "Rotación de conductores: anterior y siguiente turno.", "endpoint": "GET /api/users/drivers/rotation"},
    {"name": "Árbol binario de búsqueda", "file": "structures/bst.py", "complexity": "O(log n) promedio",
     "use": "Encontrar al estudiante por su código QR al escanear.", "endpoint": "POST /api/attendance/scan"},
    {"name": "Árbol AVL", "file": "structures/avl.py", "complexity": "O(log n) garantizado",
     "use": "Búsqueda de estudiantes por nombre mientras se escribe.", "endpoint": "GET /api/students/search"},
    {"name": "Árbol N-ario", "file": "structures/nary_tree.py", "complexity": "O(n) recorrido",
     "use": "Jerarquía institución → sede → grado → estudiantes.", "endpoint": "GET /api/schools/tree"},
]


@router.get("/structures", summary="Mapa de estructuras de datos y dónde se usan")
def structures_map(user: User = Depends(require_roles(COORDINATOR))):
    return STRUCTURES
