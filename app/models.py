"""Database tables (SQLAlchemy ORM models)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .constants import CheckInMethod, Role, TripStatus
from .database import Base


def utc_now() -> datetime:
    """Current UTC time without timezone info (portable across SQLite and PostgreSQL)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default=Role.GUARDIAN.value)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    students = relationship("Student", back_populates="guardian")


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    stops = relationship("Stop", back_populates="route", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="route")


class Stop(Base):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    name: Mapped[str] = mapped_column(String(150))
    order: Mapped[int] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    route = relationship("Route", back_populates="stops")
    students = relationship("Student", back_populates="stop")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150))
    grade: Mapped[str] = mapped_column(String(50))
    school: Mapped[str] = mapped_column(String(150))
    qr_code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    guardian_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)
    stop_id: Mapped[int | None] = mapped_column(ForeignKey("stops.id"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    guardian = relationship("User", back_populates="students")
    route = relationship("Route", back_populates="students")
    stop = relationship("Stop", back_populates="students")
    attendance = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"))
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default=TripStatus.SCHEDULED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Attendance(Base):
    """A boarding or drop-off event of a student during a trip."""

    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"))
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id"))
    stop_id: Mapped[int | None] = mapped_column(ForeignKey("stops.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(20))
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    method: Mapped[str] = mapped_column(String(30), default=CheckInMethod.QR.value)

    student = relationship("Student", back_populates="attendance")
