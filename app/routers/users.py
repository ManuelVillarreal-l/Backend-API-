from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import User
from ..schemas import UserOut

router = APIRouter()


@router.get("/me", response_model=UserOut, summary="Ver mi usuario")
def me(user: User = Depends(get_current_user)):
    return user


@router.get("/", response_model=list[UserOut], summary="Listar usuarios")
def list_users(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(User).order_by(User.id).all()
