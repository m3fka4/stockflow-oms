from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password
from app.deps import get_current_user, require_roles
from app.models import RoleEnum, User
from app.schemas import UserCreate, UserRead
from app.services import create_user

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.get("", response_model=list[UserRead])
def list_users(
    _: User = Depends(require_roles(RoleEnum.admin, RoleEnum.manager)),
    db: Session = Depends(get_db),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_endpoint(
    payload: UserCreate,
    _: User = Depends(require_roles(RoleEnum.admin)),
    db: Session = Depends(get_db),
) -> User:
    return create_user(
        db,
        email=payload.email,
        full_name=payload.full_name,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
