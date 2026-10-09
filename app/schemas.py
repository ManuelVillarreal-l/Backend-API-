"""Request and response schemas (Pydantic). They define and validate the JSON in Swagger.

Every text field has a length limit and a regular expression (see validation.py),
so oversized or malformed values are rejected with a 422 error before reaching the database.
"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .validation import (
    CatalogCode,
    CatalogName,
    ClientEventId,
    DaneCode,
    DelayMinutes,
    DocumentNumber,
    Email,
    Id,
    Label,
    Latitude,
    LicenseNumber,
    LongText,
    Longitude,
    PasswordDigest,
    PersonName,
    Phone,
    Plate,
    QrCode,
    ShortText,
    WeatherCodes,
)


class Schema(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def lower_email(value: str) -> str:
    return value.strip().lower() if isinstance(value, str) else value


# ---------------------------------------------------------------------------
# Catalogs
# ---------------------------------------------------------------------------

class CatalogRef(OrmSchema):
    id: int
    code: str
    name: str


class CatalogItemOut(CatalogRef):
    active: bool
    delay_minutes: int | None = None
    weather_codes: str | None = None
    severity: int | None = None
    sort_order: int | None = None
    description: str | None = None


class ConditionCreate(Schema):
    """Weather or road condition (stored in the database, never hard-coded)."""

    code: CatalogCode
    name: CatalogName
    delay_minutes: DelayMinutes
    weather_codes: WeatherCodes | None = None


class ConditionUpdate(Schema):
    name: CatalogName | None = None
    delay_minutes: DelayMinutes | None = None
    weather_codes: WeatherCodes | None = None
    active: bool | None = None


# ---------------------------------------------------------------------------
# Authentication and users
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int = Field(description="Segundos que dura el token (30 minutos).")


class Login(Schema):
    email: Email
    password: PasswordDigest

    _email = field_validator("email", mode="before")(lower_email)


class UserCreate(Schema):
    role_code: CatalogCode
    document_type_code: CatalogCode
    document_number: DocumentNumber
    first_name: PersonName
    last_name: PersonName
    email: Email
    phone: Phone
    password: PasswordDigest

    _email = field_validator("email", mode="before")(lower_email)


class UserOut(OrmSchema):
    """The password hash is never part of any response."""

    id: int
    first_name: str
    last_name: str
    email: str
    phone: str
    document_number: str
    role: CatalogRef
    document_type: CatalogRef
    active: bool
    last_login_at: datetime | None


class UserStatusUpdate(Schema):
    active: bool


class DriverCreate(Schema):
    user_id: Id
    license_number: LicenseNumber
    license_category: str = Field(pattern=r"^(B1|B2|B3|C1|C2|C3)$", min_length=2, max_length=2)
    license_expires_on: date
    vehicle_id: Id | None = None


class DriverOut(OrmSchema):
    id: int
    user_id: int
    full_name: str
    license_number: str
    license_category: str
    license_expires_on: date
    license_valid: bool
    vehicle_plate: str | None


# ---------------------------------------------------------------------------
# Schools, vehicles
# ---------------------------------------------------------------------------

class SchoolCreate(Schema):
    name: Label
    dane_code: DaneCode
    municipality: PersonName
    phone: Phone | None = None


class CampusOut(OrmSchema):
    id: int
    school_id: int
    name: str
    address: str | None
    latitude: float | None
    longitude: float | None


class SchoolOut(OrmSchema):
    id: int
    name: str
    dane_code: str
    municipality: str
    phone: str | None
    campuses: list[CampusOut]


class CampusCreate(Schema):
    school_id: Id
    name: Label
    address: ShortText | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None


class VehicleCreate(Schema):
    plate: Plate
    brand: Label
    model_year: int = Field(ge=1990, le=2100)
    capacity: int = Field(ge=1, le=60)

    @field_validator("plate", mode="before")
    @classmethod
    def upper_plate(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value


class VehicleOut(OrmSchema):
    id: int
    plate: str
    brand: str
    model_year: int
    capacity: int
    active: bool


# ---------------------------------------------------------------------------
# Routes, stops and segments
# ---------------------------------------------------------------------------

class RouteCreate(Schema):
    name: Label
    description: ShortText | None = None
    campus_id: Id
    vehicle_id: Id | None = None


class RouteOut(OrmSchema):
    id: int
    name: str
    description: str | None
    campus_id: int
    vehicle_id: int | None
    active: bool


class StopCreate(Schema):
    route_id: Id
    name: Label
    latitude: Latitude
    longitude: Longitude


class StopOut(OrmSchema):
    id: int
    route_id: int
    name: str
    order: int
    latitude: float
    longitude: float


class SegmentCreate(Schema):
    from_stop_id: Id
    to_stop_id: Id
    distance_km: float = Field(gt=0, le=200)
    travel_minutes: int = Field(ge=1, le=300)


class SegmentOut(OrmSchema):
    id: int
    route_id: int
    from_stop_id: int
    to_stop_id: int
    distance_km: float
    travel_minutes: int


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

class GuardianLink(Schema):
    guardian_id: Id
    relationship_code: CatalogCode
    is_primary: bool = False


class StudentCreate(Schema):
    document_type_code: CatalogCode
    document_number: DocumentNumber
    first_name: PersonName
    last_name: PersonName
    birth_date: date
    grade_code: CatalogCode
    campus_id: Id
    route_id: Id | None = None
    stop_id: Id | None = None
    guardians: list[GuardianLink] = Field(min_length=1, max_length=4)


class GuardianOut(BaseModel):
    guardian_id: int
    full_name: str
    phone: str
    relationship: str
    is_primary: bool


class StudentOut(OrmSchema):
    id: int
    first_name: str
    last_name: str
    full_name: str
    document_number: str
    document_type: CatalogRef
    birth_date: date
    grade: CatalogRef
    campus_id: int
    route_id: int | None
    stop_id: int | None
    qr_code: str
    active: bool
    guardians: list[GuardianOut] = []


# ---------------------------------------------------------------------------
# Trips, attendance, tracking, incidents
# ---------------------------------------------------------------------------

class TripCreate(Schema):
    route_id: Id
    driver_id: Id
    monitor_id: Id | None = None
    vehicle_id: Id | None = None
    direction: str = Field(default="outbound", pattern=r"^(outbound|return)$")
    scheduled_date: date | None = None


class TripStart(Schema):
    weather_code: CatalogCode
    road_condition_code: CatalogCode


class TripOut(OrmSchema):
    id: int
    route_id: int
    driver_id: int
    monitor_id: int | None
    vehicle_id: int | None
    status: CatalogRef
    weather: CatalogRef | None
    road_condition: CatalogRef | None
    direction: str
    scheduled_date: date
    started_at: datetime | None
    finished_at: datetime | None


class AttendanceCreate(Schema):
    student_id: Id
    trip_id: Id
    event_type_code: CatalogCode
    method_code: CatalogCode = "manual"
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    client_event_id: ClientEventId | None = None


class ScanCreate(Schema):
    qr_code: QrCode
    trip_id: Id
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    client_event_id: ClientEventId | None = None

    @field_validator("qr_code", mode="before")
    @classmethod
    def upper_qr(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value


class OfflineEvent(Schema):
    client_event_id: ClientEventId
    trip_id: Id
    student_id: Id
    event_type_code: CatalogCode
    method_code: CatalogCode
    occurred_at: datetime
    latitude: Latitude | None = None
    longitude: Longitude | None = None


class OfflineSync(Schema):
    events: list[OfflineEvent] = Field(min_length=1, max_length=200)


class SyncResult(BaseModel):
    saved: int
    duplicated: int
    rejected: list[str]


class AttendanceOut(OrmSchema):
    id: int
    student_id: int
    trip_id: int
    stop_id: int | None
    event_type: CatalogRef
    method: CatalogRef
    latitude: float | None
    longitude: float | None
    timestamp: datetime


class LocationCreate(Schema):
    latitude: Latitude
    longitude: Longitude
    speed_kmh: float | None = Field(default=None, ge=0, le=200)
    accuracy_m: float | None = Field(default=None, ge=0, le=10_000)


class LocationOut(OrmSchema):
    trip_id: int
    latitude: float
    longitude: float
    speed_kmh: float | None
    accuracy_m: float | None
    recorded_at: datetime


class EtaOut(BaseModel):
    trip_id: int
    stop_id: int
    stop_name: str
    distance_km: float
    eta_minutes: int
    speed_used_kmh: float
    bus_location: LocationOut | None


class IncidentCreate(Schema):
    trip_id: Id | None = None
    incident_type_code: CatalogCode
    description: LongText
    latitude: Latitude | None = None
    longitude: Longitude | None = None


class IncidentOut(OrmSchema):
    id: int
    trip_id: int | None
    incident_type: CatalogRef
    reported_by: int
    description: str
    latitude: float | None
    longitude: float | None
    created_at: datetime
    resolved_at: datetime | None


class NotificationOut(OrmSchema):
    id: int
    kind: str
    title: str
    message: str
    created_at: datetime
    read_at: datetime | None


# ---------------------------------------------------------------------------
# AI
# ---------------------------------------------------------------------------

class DelayPredictionRequest(Schema):
    route_id: Id | None = None
    weather_code: CatalogCode
    road_condition_code: CatalogCode
    stops_remaining: int = Field(ge=0, le=50)
    hour: int = Field(default=6, ge=0, le=23)


class DelayPredictionOut(BaseModel):
    estimated_delay_minutes: float
    risk: str
    model: str
    training_samples: int
    r_squared: float | None
    factors: list[str]


class AbsenceRiskOut(BaseModel):
    student_id: int
    trips_analyzed: int
    absences: int
    absence_rate: float
    rainy_absence_rate: float | None
    risk: str
    explanation: str


class RouteOptimizationOut(BaseModel):
    route_id: int
    original_order: list[str]
    suggested_order: list[str]
    original_km: float
    suggested_km: float
    saving_percent: float
    method: str


class CurrentWeatherOut(BaseModel):
    temperature_c: float | None
    precipitation_mm: float | None
    wind_kmh: float | None
    weather_code: int
    condition: CatalogRef | None
    source: str
