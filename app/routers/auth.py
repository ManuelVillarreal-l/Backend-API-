from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..auth import create_access_token, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import Login, Token, UserCreate, UserOut

router = APIRouter()


def normalize_email(email: str) -> str:
    return email.lower().strip()


def authenticate_user(db: Session, email: str, password: str) -> User:
    # Find the user by email and validate the password.
    # Shared by /login (JSON) and /token (Swagger form).
    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    return user


@router.post("/register", response_model=UserOut, summary="Registrar usuario")
def register(data: UserCreate, db: Session = Depends(get_db)):
    email = normalize_email(data.email)
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "El correo ya está registrado")
    user = User(
        name=data.name,
        email=email,
        password_hash=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión (JSON)",
    description="Inicio de sesión para la aplicación: recibe el correo y la contraseña en formato JSON.",
)
def login(data: Login, db: Session = Depends(get_db)):
    # Login used by the frontend: receives JSON with email and password.
    user = authenticate_user(db, data.email, data.password)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.post(
    "/token",
    response_model=Token,
    summary="Iniciar sesión (formulario de Swagger)",
    description="Lo usa el botón Autorizar. Escriba el correo en el campo username.",
)
def login_form(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    # Login used by the Swagger "Authorize" button: receives a form.
    # The email goes in the 'username' field.
    user = authenticate_user(db, form.username, form.password)
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}




