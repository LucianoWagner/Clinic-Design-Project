from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import TokenRead, UserCreate, UserLogin, UserRead
from app.services.auth_service import AuthService, user_to_read

router = APIRouter(tags=["auth"])


@router.post("/auth/register", response_model=TokenRead)
def register(payload: UserCreate, session: Session = Depends(get_session)) -> TokenRead:
    return AuthService(session).register(payload)


@router.post("/auth/login", response_model=TokenRead)
def login(payload: UserLogin, session: Session = Depends(get_session)) -> TokenRead:
    return AuthService(session).login(payload)


@router.get("/auth/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return user_to_read(current_user)
