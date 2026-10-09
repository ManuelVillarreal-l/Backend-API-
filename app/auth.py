"""Password hashing, 30-minute JWT tokens, login lockout and role checks.

How passwords travel and are stored:
  1. The browser computes SHA-256("<email>:<password>") and sends only that digest.
     The real password never leaves the user's device.
  2. The server applies PBKDF2-SHA256 with a random salt and 310,000 iterations
     to the digest and stores the result.
  Both steps are one-way hashes: nobody (not even the developers) can recover the password.
"""

import hashlib
import hmac
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session

from .database import get_db
from .models import LoginAttempt, User, utc_now

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
ALGORITHM = "HS256"
EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
PBKDF2_ITERATIONS = 310_000
MAX_FAILED_ATTEMPTS = 5
LOCK_MINUTES = 15

# The Swagger "Autorizar" button sends a form to this URL (see routers/auth.py -> /token).
# auto_error=False lets us return our own Spanish message when there is no token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def client_digest(email: str, password: str) -> str:
    """Same SHA-256 the browser computes. Used only by the seed data and the tests."""
    return hashlib.sha256(f"{email.strip().lower()}:{password}".encode("utf-8")).hexdigest()


def hash_password(digest: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", digest.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def verify_password(digest: str, stored: str) -> bool:
    try:
        scheme, iterations, salt_hex, derived_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        calculated = hashlib.pbkdf2_hmac(
            "sha256", digest.encode("utf-8"), bytes.fromhex(salt_hex), int(iterations)
        )
        return hmac.compare_digest(calculated.hex(), derived_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Login lockout
# ---------------------------------------------------------------------------

def check_lockout(db: Session, email: str) -> None:
    """Block the account for 15 minutes after 5 failed attempts in a row."""
    window_start = utc_now() - timedelta(minutes=LOCK_MINUTES)
    recent = (
        db.query(LoginAttempt)
        .filter(LoginAttempt.email == email, LoginAttempt.created_at >= window_start)
        .order_by(LoginAttempt.created_at.desc())
        .limit(MAX_FAILED_ATTEMPTS)
        .all()
    )
    if len(recent) == MAX_FAILED_ATTEMPTS and not any(attempt.success for attempt in recent):
        unlock_at = recent[0].created_at + timedelta(minutes=LOCK_MINUTES)
        minutes = max(1, int((unlock_at - utc_now()).total_seconds() // 60) + 1)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Cuenta bloqueada por {MAX_FAILED_ATTEMPTS} intentos fallidos. Intente de nuevo en {minutes} minutos.",
        )


def record_attempt(db: Session, email: str, user: User | None, success: bool, request: Request | None) -> None:
    ip = request.client.host if request and request.client else None
    db.add(LoginAttempt(email=email, user_id=user.id if user else None, success=success, ip_address=ip))
    db.commit()


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "role": user.role.code,
        "iat": now,
        "exp": now + timedelta(minutes=EXPIRE_MINUTES),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(token: str | None = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    if not token:
        raise _unauthorized("No autenticado. Inicie sesión con el botón Autorizar.")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
    except ExpiredSignatureError:
        raise _unauthorized("Su sesión venció (dura 30 minutos). Inicie sesión de nuevo.")
    except (JWTError, TypeError, ValueError):
        raise _unauthorized("Token inválido.")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise _unauthorized("El usuario no existe o está inactivo.")
    return user


def require_roles(*role_codes: str):
    """Dependency that only lets users with one of the given role codes through."""
    allowed = set(role_codes)

    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role.code not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta operación.")
        return user

    return dependency


COORDINATOR = "coordinator"
DRIVER = "driver"
MONITOR = "monitor"
GUARDIAN = "guardian"
STAFF = (COORDINATOR, DRIVER, MONITOR)
