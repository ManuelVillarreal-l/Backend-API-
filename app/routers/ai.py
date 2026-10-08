"""Simple rule-based heuristics (first version of the AI module).

The factor descriptions are returned in Spanish because the user reads them.
"""

from fastapi import APIRouter, Depends

from ..auth import get_current_user
from ..constants import RiskLevel, RoadCondition, Weather
from ..schemas import (
    DelayPredictionOut,
    DelayPredictionRequest,
    RouteOptimizationOut,
    RouteOptimizationRequest,
)

router = APIRouter()

# Extra minutes and the Spanish description shown to the user.
WEATHER_IMPACT = {
    Weather.CLOUDY.value: (2, "clima moderadamente adverso"),
    Weather.RAIN.value: (8, "clima adverso"),
    Weather.STORM.value: (8, "clima adverso"),
}
ROAD_IMPACT = {
    RoadCondition.FAIR.value: (4, "estado de vía regular"),
    RoadCondition.BAD.value: (10, "estado de vía desfavorable"),
    RoadCondition.CLOSED.value: (10, "estado de vía desfavorable"),
}
MINUTES_PER_REMAINING_STOP = 0.7


def risk_level(delay_minutes: float) -> RiskLevel:
    if delay_minutes < 5:
        return RiskLevel.LOW
    if delay_minutes < 12:
        return RiskLevel.MEDIUM
    return RiskLevel.HIGH


@router.post("/delay", response_model=DelayPredictionOut, summary="Predecir retraso de un recorrido")
def predict_delay(data: DelayPredictionRequest, user=Depends(get_current_user)):
    delay = float(data.historical_delay_minutes)
    factors: list[str] = []

    for impact in (WEATHER_IMPACT.get(data.weather), ROAD_IMPACT.get(data.road_condition)):
        if impact:
            minutes, description = impact
            delay += minutes
            factors.append(description)

    if data.stops_remaining:
        delay += data.stops_remaining * MINUTES_PER_REMAINING_STOP
        factors.append("paradas restantes")

    return {
        "estimated_delay_minutes": round(delay, 1),
        "risk": risk_level(delay),
        "factors": factors or ["sin factores de riesgo relevantes"],
    }


@router.post("/route-order", response_model=RouteOptimizationOut, summary="Sugerir orden de paradas")
def optimize_route(data: RouteOptimizationRequest, user=Depends(get_current_user)):
    # Initial academic heuristic: keep the last stop (the school) at the end
    # and sort the remaining stops in a stable way.
    stops = [stop.strip() for stop in data.stops if stop.strip()]
    if len(stops) <= 2:
        suggestion = stops
    else:
        suggestion = sorted(stops[:-1], key=str.lower) + [stops[-1]]
    return {"suggested_order": suggestion, "method": "heurística de ordenamiento inicial"}
