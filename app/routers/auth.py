from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..auth import EXPIRE_MINUTES, check_lockout, create_access_token, get_current_user, record_attempt, verify_password
from ..database import get_db
from ..models import User, utc_now
from ..schemas import Login, Token, UserOut
from ..services import audit

router = APIRouter()


def authenticate(db: Session, request: Request, email: str, digest: str) -> Token:
    """Validate e-mail + password digest, apply the lockout and issue a 30-minute token."""
    check_lockout(db, email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(digest, user.password_hash):
        record_attempt(db, email, user, False, request)
        raise HTTPException(401, "Correo o contraseña incorrectos.")
    if not user.active:
        record_attempt(db, email, user, False, request)
        raise HTTPException(403, "Su cuenta está desactivada. Comuníquese con el coordinador.")
    record_attempt(db, email, user, True, request)
    user.last_login_at = utc_now()
    audit(db, user, "login", "users", user.id)
    db.commit()
    return Token(access_token=create_access_token(user), token_type="bearer", expires_in=EXPIRE_MINUTES * 60)


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
    description=(
        "Recibe el correo y la contraseña **cifrada en el navegador** (hash SHA-256). "
        "La contraseña real nunca viaja. El token dura 30 minutos. "
        "Tras 5 intentos fallidos la cuenta se bloquea 15 minutos."
    ),
)
def login(data: Login, request: Request, db: Session = Depends(get_db)):
    return authenticate(db, request, data.email, data.password)


@router.post(
    "/token",
    response_model=Token,
    summary="Iniciar sesión desde Swagger (botón Autorizar)",
    description="Swagger cifra la contraseña antes de enviarla. Escriba el correo en el campo username.",
)
def login_form(request: Request, form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        data = Login(email=form.username, password=form.password)
    except ValidationError:
        raise HTTPException(422, "Correo con formato inválido o contraseña sin cifrar.")
    return authenticate(db, request, data.email, data.password)


@router.get(
    "/profile",
    response_model=UserOut,
    summary="Perfil del usuario que inició sesión",
    description=(
        "Devuelve los datos del usuario dueño del token (nombre, rol, documento, correo). "
        "No recibe ningún id: el usuario se identifica con el token, así nadie puede consultar el perfil de otra persona. "
        "La aplicación web lo usa al iniciar sesión para saber qué menú mostrar según el rol."
    ),
)
def current_profile(user: User = Depends(get_current_user)):
    """Return the user identified by the access token."""
    return user
