from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

from .database import Base, SessionLocal, engine  # noqa: E402
from .docs_es import register_spanish_docs  # noqa: E402
from .errors import register_error_handlers  # noqa: E402
from .routers import (  # noqa: E402
    attendance,
    auth,
    catalogs,
    intelligence,
    monitoring,
    organization,
    routes,
    students,
    trips,
    users,
)
from .seed import seed_demo  # noqa: E402

MAX_BODY_BYTES = 64 * 1024  # 64 KB: no form of this system needs more

# Create tables and demo data on startup (only when the database is empty).
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_demo(db)

app = FastAPI(
    title="RutaSegura API",
    description=(
        "API del sistema inteligente de transporte escolar rural RutaSegura.\n\n"
        "**Seguridad:** las contraseñas viajan cifradas (SHA-256 en el navegador) y se guardan con PBKDF2; "
        "el token dura 30 minutos y la cuenta se bloquea tras 5 intentos fallidos. "
        "Todos los campos se validan con expresiones regulares y límites de longitud."
    ),
    version="2.0.0",
    docs_url=None,  # replaced by the Spanish Swagger page below
    redoc_url=None,
)

register_spanish_docs(app)
register_error_handlers(app)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    """Reject oversized requests before reading them (protects against giant payloads)."""
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "La información enviada es demasiado grande."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tags are the group titles shown in Swagger (Spanish, user-facing).
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios y conductores"])
app.include_router(catalogs.router, prefix="/api/catalogs", tags=["Catálogos"])
app.include_router(organization.router, prefix="/api", tags=["Instituciones y vehículos"])
app.include_router(routes.router, prefix="/api/routes", tags=["Rutas, paradas y tramos"])
app.include_router(students.router, prefix="/api/students", tags=["Estudiantes"])
app.include_router(trips.router, prefix="/api/trips", tags=["Recorridos y GPS"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Abordaje y descenso"])
app.include_router(monitoring.router, prefix="/api", tags=["Incidentes, notificaciones y reportes"])
app.include_router(intelligence.router, prefix="/api", tags=["Inteligencia artificial y estructuras"])


@app.get("/", tags=["Sistema"], summary="Estado de la API")
def root():
    return {"system": "RutaSegura", "status": "online", "version": "2.0.0"}


@app.get("/health", tags=["Sistema"], summary="Verificación de salud")
def health():
    return {"status": "healthy", "service": "rutasegura-api"}
