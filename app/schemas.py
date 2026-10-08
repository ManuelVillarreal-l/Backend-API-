"""Request and response schemas (Pydantic). They define the JSON shown in Swagger."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .constants import CheckInMethod, EventType, RiskLevel, Role, RoadCondition, TripStatus, Weather


class Schema(BaseModel):
    # Store enum members as plain strings so they can be saved directly in the database.
    model_config = ConfigDict(use_enum_values=True)


class OrmSchema(Schema):
    model_config = ConfigDict(use_enum_values=True, from_attributes=True)


# ---------- Authentication ----------

class Token(Schema):
    access_token: str
    token_type: str


class Login(Schema):
    email: str
    password: str


# ---------- Users ----------

class UserCreate(Schema):
    name: str
    email: str
    password: str = Field(min_length=6)
    role: Role = Role.GUARDIAN


class UserOut(OrmSchema):
    id: int
    name: str
    email: str
    role: Role
    active: bool


# ---------- Routes and stops ----------

class RouteCreate(Schema):
    name: str
    description: str | None = None


class RouteOut(RouteCreate, OrmSchema):
    id: int
    active: bool


class StopCreate(Schema):
    route_id: int
    name: str
    order: int
    latitude: float | None = None
    longitude: float | None = None


class StopOut(StopCreate, OrmSchema):
    id: int


# ---------- Students ----------

class StudentCreate(Schema):
    full_name: str
    grade: str
    school: str
    guardian_id: int | None = None
    route_id: int | None = None
    stop_id: int | None = None
    qr_code: str | None = None


class StudentOut(StudentCreate, OrmSchema):
    id: int
    active: bool
    qr_code: str


# ---------- Attendance (boarding / drop-off) ----------

class AttendanceCreate(Schema):
    student_id: int
    trip_id: int
    stop_id: int | None = None
    event_type: EventType
    method: CheckInMethod = CheckInMethod.QR


class ScanCreate(Schema):
    qr_code: str
    trip_id: int
    stop_id: int | None = None
    event_type: EventType


class AttendanceOut(AttendanceCreate, OrmSchema):
    id: int
    timestamp: datetime


# ---------- Trips ----------

class TripCreate(Schema):
    route_id: int
    driver_id: int | None = None


class TripOut(TripCreate, OrmSchema):
    id: int
    status: TripStatus
    started_at: datetime | None
    finished_at: datetime | None


# ---------- AI / heuristics ----------

class DelayPredictionRequest(Schema):
    weather: Weather = Weather.NORMAL
    road_condition: RoadCondition = RoadCondition.GOOD
    historical_delay_minutes: float = Field(default=0, ge=0)
    stops_remaining: int = Field(default=0, ge=0)


class DelayPredictionOut(Schema):
    estimated_delay_minutes: float
    risk: RiskLevel
    factors: list[str]


class RouteOptimizationRequest(Schema):
    stops: list[str]


class RouteOptimizationOut(Schema):
    suggested_order: list[str]
    method: str
