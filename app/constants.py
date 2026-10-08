"""Fixed values used across the system.

The values stored in the database are in English (they are code).
Everything the user reads (error messages, Swagger titles) stays in Spanish.
"""

from enum import Enum


class Role(str, Enum):
    GUARDIAN = "guardian"        # acudiente
    DRIVER = "driver"            # conductor
    MONITOR = "monitor"          # monitor de ruta
    COORDINATOR = "coordinator"  # coordinador


class TripStatus(str, Enum):
    SCHEDULED = "scheduled"      # programado
    IN_PROGRESS = "in_progress"  # en recorrido
    FINISHED = "finished"        # finalizado


class EventType(str, Enum):
    BOARDING = "boarding"  # abordaje
    DROP_OFF = "drop_off"  # descenso


class CheckInMethod(str, Enum):
    QR = "qr"
    MANUAL = "manual"


class Weather(str, Enum):
    NORMAL = "normal"
    CLOUDY = "cloudy"
    RAIN = "rain"
    STORM = "storm"


class RoadCondition(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    BAD = "bad"
    CLOSED = "closed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"



