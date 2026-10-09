"""Catalogs: every list of options comes from the database (roles, weather, road conditions...).

Weather and road conditions can be added or edited by the coordinator, so nothing
about them is hard-coded in the program.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import COORDINATOR, get_current_user, require_roles
from ..database import get_db
from ..models import RoadCondition, WeatherCondition
from ..schemas import CatalogItemOut, ConditionCreate, ConditionUpdate
from ..services import CATALOG_MODELS, audit, get_or_404

router = APIRouter()
coordinator_only = require_roles(COORDINATOR)

CONDITION_MODELS = {"weather_conditions": WeatherCondition, "road_conditions": RoadCondition}


def to_out(item) -> CatalogItemOut:
    return CatalogItemOut(
        id=item.id,
        code=item.code,
        name=item.name,
        active=item.active,
        delay_minutes=getattr(item, "delay_minutes", None),
        weather_codes=getattr(item, "weather_codes", None),
        severity=getattr(item, "severity", None),
        sort_order=getattr(item, "sort_order", None),
        description=getattr(item, "description", None),
    )


@router.get(
    "/",
    response_model=dict[str, list[CatalogItemOut]],
    summary="Todos los catálogos",
    description="Roles, tipos de documento, parentescos, grados, estados, eventos, métodos, climas, estados de vía e incidentes.",
)
def all_catalogs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    result = {}
    for key, model in CATALOG_MODELS.items():
        order = model.sort_order if hasattr(model, "sort_order") else model.id
        result[key] = [to_out(item) for item in db.query(model).order_by(order).all()]
    return result


def _condition_model(catalog: str):
    model = CONDITION_MODELS.get(catalog)
    if not model:
        raise HTTPException(404, "Solo se pueden editar los catálogos de clima y estado de la vía.")
    return model


@router.post(
    "/{catalog}",
    response_model=CatalogItemOut,
    status_code=201,
    summary="Agregar clima o estado de vía",
    description="`catalog` es `weather_conditions` o `road_conditions`.",
)
def create_condition(catalog: str, data: ConditionCreate, db: Session = Depends(get_db), user=Depends(coordinator_only)):
    model = _condition_model(catalog)
    if db.query(model).filter(model.code == data.code).first():
        raise HTTPException(409, "Ya existe una opción con ese código.")
    values = data.model_dump()
    if model is RoadCondition:
        values.pop("weather_codes", None)
    item = model(**values)
    db.add(item)
    db.flush()
    audit(db, user, "create", catalog, item.id, data.name)
    db.commit()
    db.refresh(item)
    return to_out(item)


@router.put("/{catalog}/{item_id}", response_model=CatalogItemOut, summary="Editar clima o estado de vía")
def update_condition(
    catalog: str, item_id: int, data: ConditionUpdate, db: Session = Depends(get_db), user=Depends(coordinator_only)
):
    model = _condition_model(catalog)
    item = get_or_404(db, model, item_id, "Opción")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "weather_codes" and model is RoadCondition:
            continue
        setattr(item, key, value)
    audit(db, user, "update", catalog, item.id)
    db.commit()
    db.refresh(item)
    return to_out(item)
