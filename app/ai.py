"""Artificial-intelligence module (no external libraries, so every step can be explained).

1. Delay prediction: multiple linear regression trained with the history of finished
   trips (least squares solved with the normal equations and Gaussian elimination).
   Features: weather impact, road impact, number of stops and departure hour.
   If there is not enough history, it falls back to the catalog values.
2. Route optimization: nearest-neighbor heuristic + 2-opt improvement over the real
   GPS distances (a classic approach to the traveling salesman problem).
3. Absence risk: historical absence rate of each student, overall and on rainy days.
4. Current weather: real data from the Open-Meteo service, mapped to the weather catalog.
"""

import json
import urllib.parse
import urllib.request
from datetime import timedelta

from sqlalchemy.orm import Session

from .models import Attendance, EventType, RoadCondition, Stop, Student, Trip, TripStatus, WeatherCondition
from .services import haversine_km, route_stops

MIN_TRAINING_SAMPLES = 8
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


# ---------------------------------------------------------------------------
# Linear algebra helpers
# ---------------------------------------------------------------------------

def solve_linear_system(matrix: list[list[float]], vector: list[float]) -> list[float] | None:
    """Gaussian elimination with partial pivoting. Returns None if the system is singular."""
    n = len(vector)
    a = [row[:] + [vector[i]] for i, row in enumerate(matrix)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(a[r][col]))
        if abs(a[pivot][col]) < 1e-9:
            return None
        a[col], a[pivot] = a[pivot], a[col]
        for row in range(col + 1, n):
            factor = a[row][col] / a[col][col]
            for k in range(col, n + 1):
                a[row][k] -= factor * a[col][k]
    solution = [0.0] * n
    for row in range(n - 1, -1, -1):
        total = a[row][n] - sum(a[row][k] * solution[k] for k in range(row + 1, n))
        solution[row] = total / a[row][row]
    return solution


def fit_linear_regression(features: list[list[float]], targets: list[float], ridge: float = 0.01):
    """Least squares: solve (XᵀX + λI)β = Xᵀy. Returns (coefficients, r²)."""
    rows = [[1.0] + list(x) for x in features]  # intercept column
    k = len(rows[0])
    xtx = [[sum(r[i] * r[j] for r in rows) + (ridge if i == j and i > 0 else 0.0) for j in range(k)] for i in range(k)]
    xty = [sum(r[i] * y for r, y in zip(rows, targets)) for i in range(k)]
    beta = solve_linear_system(xtx, xty)
    if beta is None:
        return None, None
    predictions = [sum(b * v for b, v in zip(beta, r)) for r in rows]
    mean = sum(targets) / len(targets)
    ss_tot = sum((y - mean) ** 2 for y in targets)
    ss_res = sum((y - p) ** 2 for y, p in zip(targets, predictions))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
    return beta, r2


# ---------------------------------------------------------------------------
# 1. Delay prediction
# ---------------------------------------------------------------------------

def planned_minutes(db: Session, route_id: int) -> float:
    """Expected trip duration without delays: travel time of the segments between consecutive stops."""
    from .models import RouteSegment

    segments = {
        frozenset((s.from_stop_id, s.to_stop_id)): s.travel_minutes
        for s in db.query(RouteSegment).filter(RouteSegment.route_id == route_id)
    }
    stops = route_stops(db, route_id)
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        minutes = segments.get(frozenset((a.id, b.id)))
        if minutes is None:  # no segment registered: straight-line distance at 25 km/h
            minutes = haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) / 25 * 60
        total += minutes
    return total


def training_data(db: Session):
    finished = (
        db.query(Trip)
        .join(TripStatus)
        .filter(TripStatus.code == "finished", Trip.started_at.isnot(None), Trip.finished_at.isnot(None))
        .filter(Trip.weather_id.isnot(None), Trip.road_condition_id.isnot(None))
        .all()
    )
    features, targets = [], []
    planned_cache: dict[int, float] = {}
    stops_cache: dict[int, int] = {}
    for trip in finished:
        if trip.route_id not in planned_cache:
            planned_cache[trip.route_id] = planned_minutes(db, trip.route_id)
            stops_cache[trip.route_id] = len(route_stops(db, trip.route_id))
        duration = (trip.finished_at - trip.started_at).total_seconds() / 60
        delay = duration - planned_cache[trip.route_id]
        local_hour = (trip.started_at - timedelta(hours=5)).hour  # Colombia time (UTC-5)
        features.append(
            [trip.weather.delay_minutes, trip.road_condition.delay_minutes, stops_cache[trip.route_id], local_hour]
        )
        targets.append(delay)
    return features, targets


def predict_delay(db: Session, weather: WeatherCondition, road: RoadCondition, stops: int, hour: int) -> dict:
    features, targets = training_data(db)
    factors = []
    if weather.delay_minutes:
        factors.append(f"Clima: {weather.name} (+{weather.delay_minutes} min en el catálogo)")
    if road.delay_minutes:
        factors.append(f"Vía: {road.name} (+{road.delay_minutes} min en el catálogo)")
    if stops:
        factors.append(f"{stops} paradas por recorrer")

    beta, r2 = (None, None)
    if len(targets) >= MIN_TRAINING_SAMPLES:
        beta, r2 = fit_linear_regression(features, targets)

    if beta is not None:
        x = [1.0, weather.delay_minutes, road.delay_minutes, stops, hour]
        estimate = sum(b * v for b, v in zip(beta, x))
        model = "regression"
        factors.append(
            f"Modelo de regresión entrenado con {len(targets)} recorridos reales (R² = {r2:.2f})"
            if r2 is not None
            else f"Modelo de regresión entrenado con {len(targets)} recorridos reales"
        )
    else:
        estimate = weather.delay_minutes + road.delay_minutes + 0.7 * stops
        model = "baseline"
        factors.append("Pocos recorridos en el historial: se usan los valores del catálogo")

    estimate = max(0.0, round(estimate, 1))
    risk = "low" if estimate < 5 else "medium" if estimate < 12 else "high"
    return {
        "estimated_delay_minutes": estimate,
        "risk": risk,
        "model": model,
        "training_samples": len(targets),
        "r_squared": round(r2, 3) if r2 is not None else None,
        "factors": factors or ["Sin factores de riesgo relevantes"],
    }


# ---------------------------------------------------------------------------
# 2. Route optimization (nearest neighbor + 2-opt)
# ---------------------------------------------------------------------------

def path_length(points: list[Stop]) -> float:
    return sum(
        haversine_km(a.latitude, a.longitude, b.latitude, b.longitude) for a, b in zip(points, points[1:])
    )


def optimize_route(db: Session, route_id: int) -> dict:
    stops = route_stops(db, route_id)
    if len(stops) < 4:
        order = stops
        return _optimization_result(route_id, stops, order, "Muy pocas paradas para optimizar")

    first, school = stops[0], stops[-1]
    pending = stops[1:-1]

    # Nearest neighbor: always go to the closest stop not visited yet.
    order = [first]
    while pending:
        last = order[-1]
        nearest = min(pending, key=lambda s: haversine_km(last.latitude, last.longitude, s.latitude, s.longitude))
        order.append(nearest)
        pending.remove(nearest)
    order.append(school)

    # 2-opt: reverse a section when that shortens the path (first and last stay fixed).
    improved = True
    while improved:
        improved = False
        for i in range(1, len(order) - 2):
            for j in range(i + 1, len(order) - 1):
                candidate = order[:i] + order[i : j + 1][::-1] + order[j + 1 :]
                if path_length(candidate) + 1e-9 < path_length(order):
                    order = candidate
                    improved = True

    return _optimization_result(route_id, stops, order, "Vecino más cercano + mejora 2-opt (distancias GPS reales)")


def _optimization_result(route_id: int, original: list[Stop], suggested: list[Stop], method: str) -> dict:
    original_km = path_length(original)
    suggested_km = path_length(suggested)
    saving = (original_km - suggested_km) / original_km * 100 if original_km else 0.0
    return {
        "route_id": route_id,
        "original_order": [s.name for s in original],
        "suggested_order": [s.name for s in suggested],
        "original_km": round(original_km, 2),
        "suggested_km": round(suggested_km, 2),
        "saving_percent": round(max(saving, 0.0), 1),
        "method": method,
    }


# ---------------------------------------------------------------------------
# 3. Absence risk
# ---------------------------------------------------------------------------

def absence_risk(db: Session, student: Student) -> dict:
    if not student.route_id:
        return _absence_result(student.id, 0, 0, None, "El estudiante no tiene ruta asignada.")

    trips = (
        db.query(Trip)
        .join(TripStatus)
        .filter(Trip.route_id == student.route_id, TripStatus.code == "finished", Trip.direction == "outbound")
        .all()
    )
    boarded_trip_ids = {
        row[0]
        for row in db.query(Attendance.trip_id)
        .join(EventType)
        .filter(Attendance.student_id == student.id, EventType.code == "boarding")
        .all()
    }
    absences = [t for t in trips if t.id not in boarded_trip_ids]
    rainy = [t for t in trips if t.weather and t.weather.code in ("rain", "storm")]
    rainy_absences = [t for t in rainy if t.id not in boarded_trip_ids]
    rainy_rate = len(rainy_absences) / len(rainy) if rainy else None

    explanation = (
        f"Faltó a {len(absences)} de {len(trips)} recorridos de ida."
        if trips
        else "Todavía no hay recorridos finalizados en su ruta."
    )
    if rainy_rate is not None and trips and rainy_rate > len(absences) / len(trips) + 0.1:
        explanation += " Falta más los días de lluvia."
    return _absence_result(student.id, len(trips), len(absences), rainy_rate, explanation)


def _absence_result(student_id: int, total: int, absent: int, rainy_rate: float | None, explanation: str) -> dict:
    rate = absent / total if total else 0.0
    risk = "low" if rate < 0.15 else "medium" if rate < 0.35 else "high"
    return {
        "student_id": student_id,
        "trips_analyzed": total,
        "absences": absent,
        "absence_rate": round(rate, 3),
        "rainy_absence_rate": round(rainy_rate, 3) if rainy_rate is not None else None,
        "risk": risk,
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# 4. Current weather (Open-Meteo)
# ---------------------------------------------------------------------------

def fetch_current_weather(latitude: float, longitude: float) -> dict:
    """Ask Open-Meteo for the current weather. Raises OSError/ValueError on failure."""
    query = urllib.parse.urlencode(
        {
            "latitude": f"{latitude:.4f}",
            "longitude": f"{longitude:.4f}",
            "current": "temperature_2m,precipitation,weather_code,wind_speed_10m",
            "timezone": "America/Bogota",
        }
    )
    with urllib.request.urlopen(f"{OPEN_METEO_URL}?{query}", timeout=6) as response:
        data = json.loads(response.read().decode("utf-8"))
    current = data["current"]
    return {
        "temperature_c": current.get("temperature_2m"),
        "precipitation_mm": current.get("precipitation"),
        "wind_kmh": current.get("wind_speed_10m"),
        "weather_code": int(current["weather_code"]),
    }


def weather_condition_for_code(db: Session, code: int) -> WeatherCondition | None:
    for condition in db.query(WeatherCondition).filter(WeatherCondition.active.is_(True)).all():
        codes = {int(c) for c in (condition.weather_codes or "").split(",") if c}
        if code in codes:
            return condition
    return None
