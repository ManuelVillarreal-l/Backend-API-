from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from .database import Base, SessionLocal, engine  # noqa: E402
from .docs_es import register_spanish_docs  # noqa: E402
from .errors import register_error_handlers  # noqa: E402
from .routers import ai, attendance, auth, routes, students, trips, users  # noqa: E402
from .seed import seed_demo  # noqa: E402

# Create tables and demo data on startup.
Base.metadata.create_all(bind=engine)
with SessionLocal() as db:
    seed_demo(db)

app = FastAPI(
    title="RutaSegura API",
    description="API del sistema inteligente de transporte escolar rural RutaSegura",
    version="1.0.0",
    docs_url=None,   # replaced by the Spanish Swagger page below
    redoc_url=None,
)

register_spanish_docs(app)
register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tags are the group titles shown in Swagger (Spanish, user-facing).
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(users.router, prefix="/api/users", tags=["Usuarios"])
app.include_router(routes.router, prefix="/api/routes", tags=["Rutas y paradas"])
app.include_router(students.router, prefix="/api/students", tags=["Estudiantes"])
app.include_router(attendance.router, prefix="/api/attendance", tags=["Abordaje y descenso"])
app.include_router(trips.router, prefix="/api/trips", tags=["Recorridos"])
app.include_router(ai.router, prefix="/api/ai", tags=["IA / heurísticas"])


@app.get("/", tags=["Sistema"], summary="Estado de la API")
def root():
    return {"system": "RutaSegura", "status": "online", "version": "1.0.0"}


@app.get("/health", tags=["Sistema"], summary="Verificación de salud")
def health():
    return {"status": "healthy", "service": "rutasegura-api"}
