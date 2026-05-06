from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import TokenRead, UserCreate, UserLogin, UserRead


class AuthService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def register(self, payload: UserCreate) -> TokenRead:
        email = _normalize_email(payload.email)
        document_number = payload.document_number.strip()
        self._ensure_unique_user(email, document_number)

        user = User(
            email=email,
            full_name=payload.full_name.strip(),
            document_number=document_number,
            phone=payload.phone.strip(),
            password_hash=hash_password(payload.password),
        )
        self.session.add(user)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email o DNI.",
            ) from None
        self.session.refresh(user)
        return self._token_for_user(user)

    def login(self, payload: UserLogin) -> TokenRead:
        email = _normalize_email(payload.email)
        user = self.session.exec(select(User).where(User.email == email)).first()
        if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email o contraseña inválidos.",
            )

        user.updated_at = datetime.now(UTC).replace(tzinfo=None)
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return self._token_for_user(user)

    def _ensure_unique_user(self, email: str, document_number: str) -> None:
        existing = self.session.exec(
            select(User).where((User.email == email) | (User.document_number == document_number))
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe un usuario con ese email o DNI.",
            )

    def _token_for_user(self, user: User) -> TokenRead:
        return TokenRead(access_token=create_access_token(str(user.id)), user=user_to_read(user))


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def user_to_read(user: User) -> UserRead:
    return UserRead(
        id=user.id or 0,
        email=user.email,
        full_name=user.full_name,
        document_number=user.document_number,
        phone=user.phone,
        is_active=user.is_active,
    )
