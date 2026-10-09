"""Database tables (SQLAlchemy ORM models).

28 tables grouped in:
  - Catalogs (10): values that used to be hard-coded now live in the database.
  - Organization (3): schools, campuses, vehicles.
  - People (3): users, drivers, student_guardians.
  - Routes (3): routes, stops, route_segments.
  - Operation (5): students, trips, attendance, vehicle_locations, incidents.
  - Security, AI and communication (4): login_attempts, notifications,
    delay_predictions, audit_logs.
"""

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utc_now() -> datetime:
    """Current UTC time without timezone info (portable across SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ======================================================================
# Catalogs
# ======================================================================

class CatalogMixin:
    """Common columns: a stable code used by the program and a display name."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(60))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Role(CatalogMixin, Base):
    __tablename__ = "roles"
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)


class DocumentType(CatalogMixin, Base):
    __tablename__ = "document_types"


class Relationship(CatalogMixin, Base):
    """Kinship between a guardian and a student (mother, father, grandparent...)."""

    __tablename__ = "relationships"


class Grade(CatalogMixin, Base):
    __tablename__ = "grades"
    sort_order: Mapped[int] = mapped_column(Integer)
    __table_args__ = (CheckConstraint("sort_order BETWEEN 0 AND 13", name="ck_grades_sort_order"),)


class TripStatus(CatalogMixin, Base):
    __tablename__ = "trip_statuses"


class EventType(CatalogMixin, Base):
    __tablename__ = "event_types"


class CheckInMethod(CatalogMixin, Base):
    __tablename__ = "check_in_methods"


class WeatherCondition(CatalogMixin, Base):
    """Weather options and how many minutes each one usually adds to a trip."""

    __tablename__ = "weather_conditions"
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    # Open-Meteo WMO weather codes that map to this condition, e.g. "61,63,65".
    weather_codes: Mapped[str | None] = mapped_column(String(120), nullable=True)
    __table_args__ = (CheckConstraint("delay_minutes BETWEEN 0 AND 120", name="ck_weather_delay"),)


class RoadCondition(CatalogMixin, Base):
    """Road state options and how many minutes each one usually adds to a trip."""

    __tablename__ = "road_conditions"
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (CheckConstraint("delay_minutes BETWEEN 0 AND 120", name="ck_road_delay"),)


class IncidentType(CatalogMixin, Base):
    __tablename__ = "incident_types"
    severity: Mapped[int] = mapped_column(Integer, default=1)
    __table_args__ = (CheckConstraint("severity BETWEEN 1 AND 3", name="ck_incident_severity"),)


# ======================================================================
# Organization
# ======================================================================

class School(Base):
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    dane_code: Mapped[str] = mapped_column(String(12), unique=True)
    municipality: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str | None] = mapped_column(String(10), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    campuses = relationship("Campus", back_populates="school", order_by="Campus.id")


class Campus(Base):
    __tablename__ = "campuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(150), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    school = relationship("School", back_populates="campuses")
    __table_args__ = (UniqueConstraint("school_id", "name", name="uq_campuses_school_name"),)


class Vehicle(Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plate: Mapped[str] = mapped_column(String(6), unique=True)
    brand: Mapped[str] = mapped_column(String(40))
    model_year: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        CheckConstraint("capacity BETWEEN 1 AND 60", name="ck_vehicles_capacity"),
        CheckConstraint("model_year BETWEEN 1990 AND 2100", name="ck_vehicles_year"),
    )


# ======================================================================
# People
# ======================================================================

class User(Base):
    """Everyone who logs in. The password is never stored: only a PBKDF2 hash of the
    SHA-256 digest computed in the browser."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"))
    document_number: Mapped[str] = mapped_column(String(10))
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    email: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(10))
    password_hash: Mapped[str] = mapped_column(String(200))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    role = relationship("Role", lazy="joined")
    document_type = relationship("DocumentType", lazy="joined")

    __table_args__ = (
        UniqueConstraint("document_type_id", "document_number", name="uq_users_document"),
        Index("ix_users_role_id", "role_id"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Driver(Base):
    """Extra data for users with the driver role."""

    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    license_number: Mapped[str] = mapped_column(String(12), unique=True)
    license_category: Mapped[str] = mapped_column(String(2))
    license_expires_on: Mapped[date] = mapped_column(Date)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)

    user = relationship("User", lazy="joined")
    vehicle = relationship("Vehicle", lazy="joined")
    __table_args__ = (CheckConstraint("license_category IN ('B1','B2','B3','C1','C2','C3')", name="ck_drivers_category"),)


class StudentGuardian(Base):
    """Many-to-many: a student can have several guardians and a guardian several students."""

    __tablename__ = "student_guardians"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    guardian_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    relationship_id: Mapped[int] = mapped_column(ForeignKey("relationships.id"))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    guardian = relationship("User", lazy="joined")
    kinship = relationship("Relationship", lazy="joined")
    __table_args__ = (
        UniqueConstraint("student_id", "guardian_id", name="uq_student_guardians"),
        Index("ix_student_guardians_guardian", "guardian_id"),
    )


# ======================================================================
# Routes
# ======================================================================

class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    stops = relationship("Stop", back_populates="route", order_by="Stop.order", cascade="all, delete-orphan")


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    order: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)

    route = relationship("Route", back_populates="stops")
    __table_args__ = (
        UniqueConstraint("route_id", "order", name="uq_stops_route_order"),
        CheckConstraint('"order" BETWEEN 1 AND 50', name="ck_stops_order"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_stops_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_stops_longitude"),
    )


class RouteSegment(Base):
    """A road between two stops: the edges of the route graph."""

    __tablename__ = "route_segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id", ondelete="CASCADE"))
    from_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="CASCADE"))
    to_stop_id: Mapped[int] = mapped_column(ForeignKey("stops.id", ondelete="CASCADE"))
    distance_km: Mapped[float] = mapped_column(Float)
    travel_minutes: Mapped[int] = mapped_column(Integer)

    __table_args__ = (
        UniqueConstraint("from_stop_id", "to_stop_id", name="uq_route_segments_pair"),
        CheckConstraint("from_stop_id <> to_stop_id", name="ck_route_segments_distinct"),
        CheckConstraint("distance_km > 0 AND distance_km <= 200", name="ck_route_segments_distance"),
        CheckConstraint("travel_minutes BETWEEN 1 AND 300", name="ck_route_segments_minutes"),
    )


# ======================================================================
# Operation
# ======================================================================

class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_type_id: Mapped[int] = mapped_column(ForeignKey("document_types.id"))
    document_number: Mapped[str] = mapped_column(String(10))
    first_name: Mapped[str] = mapped_column(String(50))
    last_name: Mapped[str] = mapped_column(String(50))
    birth_date: Mapped[date] = mapped_column(Date)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"))
    campus_id: Mapped[int] = mapped_column(ForeignKey("campuses.id"))
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL"), nullable=True)
    stop_id: Mapped[int | None] = mapped_column(ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    qr_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    grade = relationship("Grade", lazy="joined")
    document_type = relationship("DocumentType", lazy="joined")
    guardians = relationship("StudentGuardian", cascade="all, delete-orphan", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("document_type_id", "document_number", name="uq_students_document"),
        Index("ix_students_route_id", "route_id"),
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    driver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    monitor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True)
    status_id: Mapped[int] = mapped_column(ForeignKey("trip_statuses.id"))
    weather_id: Mapped[int | None] = mapped_column(ForeignKey("weather_conditions.id"), nullable=True)
    road_condition_id: Mapped[int | None] = mapped_column(ForeignKey("road_conditions.id"), nullable=True)
    direction: Mapped[str] = mapped_column(String(10), default="outbound")
    scheduled_date: Mapped[date] = mapped_column(Date)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status = relationship("TripStatus", lazy="joined")
    weather = relationship("WeatherCondition", lazy="joined")
    road_condition = relationship("RoadCondition", lazy="joined")

    __table_args__ = (
        CheckConstraint("direction IN ('outbound','return')", name="ck_trips_direction"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at", name="ck_trips_times"),
        Index("ix_trips_route_id", "route_id"),
        Index("ix_trips_status_id", "status_id"),
    )


class Attendance(Base):
    """A boarding or drop-off event of a student during a trip."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    stop_id: Mapped[int | None] = mapped_column(ForeignKey("stops.id", ondelete="SET NULL"), nullable=True)
    event_type_id: Mapped[int] = mapped_column(ForeignKey("event_types.id"))
    method_id: Mapped[int] = mapped_column(ForeignKey("check_in_methods.id"))
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Random id generated by the phone, so an event sent twice (offline sync) is saved once.
    client_event_id: Mapped[str | None] = mapped_column(String(36), unique=True, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    event_type = relationship("EventType", lazy="joined")
    method = relationship("CheckInMethod", lazy="joined")

    __table_args__ = (
        Index("ix_attendance_student_time", "student_id", "timestamp"),
        Index("ix_attendance_trip_id", "trip_id"),
    )


class VehicleLocation(Base):
    """GPS positions sent by the driver's phone during a trip."""

    __tablename__ = "vehicle_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_locations_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_locations_longitude"),
        CheckConstraint("speed_kmh IS NULL OR speed_kmh BETWEEN 0 AND 200", name="ck_locations_speed"),
        Index("ix_vehicle_locations_trip_time", "trip_id", "recorded_at"),
    )


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), nullable=True)
    incident_type_id: Mapped[int] = mapped_column(ForeignKey("incident_types.id"))
    reported_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(String(500))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    incident_type = relationship("IncidentType", lazy="joined")


# ======================================================================
# Security, AI and communication
# ======================================================================

class LoginAttempt(Base):
    """Every login attempt; used to lock an account after repeated failures."""

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(30))
    title: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    __table_args__ = (Index("ix_notifications_user_created", "user_id", "created_at"),)


class DelayPrediction(Base):
    """History of the AI delay predictions (also used to evaluate the model)."""

    __tablename__ = "delay_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id", ondelete="SET NULL"), nullable=True)
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), nullable=True)
    weather_id: Mapped[int] = mapped_column(ForeignKey("weather_conditions.id"))
    road_condition_id: Mapped[int] = mapped_column(ForeignKey("road_conditions.id"))
    stops_remaining: Mapped[int] = mapped_column(Integer)
    predicted_minutes: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class AuditLog(Base):
    """Who did what and when (create, start, finish, undo, login...)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(40))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (Index("ix_audit_logs_created", "created_at"),)
