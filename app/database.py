"""Database connection.

The API tries the database in DATABASE_URL (PostgreSQL in production). If it cannot
connect (for example, the free Render database expired), the API does NOT go down:
it switches to a local SQLite database with the demo data, so the system keeps
working, and /health reports which database is in use.
"""

import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

log = logging.getLogger("rutasegura.database")

SQLITE_FALLBACK_URL = "sqlite:///./rutasegura_fallback.db"
CONNECT_TIMEOUT_SECONDS = 8


def normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def build_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
    return create_engine(
        url,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        pool_pre_ping=True,
        pool_recycle=300,
    )


def connect() -> tuple:
    """Return (engine, mode, error). mode is 'postgresql', 'sqlite' or 'sqlite-fallback'."""
    url = normalize_url(os.getenv("DATABASE_URL", "sqlite:///./rutasegura.db"))
    engine = build_engine(url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return engine, ("sqlite" if url.startswith("sqlite") else "postgresql"), None
    except Exception as error:  # noqa: BLE001 - any connection problem means fallback
        if url.startswith("sqlite"):
            raise
        engine.dispose()
        message = f"{type(error).__name__}: {str(error).splitlines()[0][:200]}"
        log.error("Could not connect to DATABASE_URL (%s). Using SQLite fallback.", message)
        return build_engine(SQLITE_FALLBACK_URL), "sqlite-fallback", message


engine, DB_MODE, DB_ERROR = connect()
DATABASE_URL = str(engine.url)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Columns added after the first version. create_all() only creates missing tables, so an
# existing database receives these columns here (nullable, so no data is lost).
NEW_COLUMNS = {
    "vehicles": {"campus_id": "INTEGER REFERENCES campuses(id) ON DELETE SET NULL"},
    "drivers": {"campus_id": "INTEGER REFERENCES campuses(id) ON DELETE SET NULL"},
}


def add_missing_columns(bind) -> list[str]:
    """ALTER TABLE ... ADD COLUMN for every column of NEW_COLUMNS that does not exist yet."""
    from sqlalchemy import inspect

    inspector = inspect(bind)
    added = []
    with bind.begin() as connection:
        for table, columns in NEW_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {definition}"))
                    added.append(f"{table}.{column}")
    if added:
        log.info("Added columns: %s", ", ".join(added))
    return added
