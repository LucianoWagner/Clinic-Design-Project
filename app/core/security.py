import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import settings


password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def generate_checkin_token(appointment_id: int) -> str:
    """Genera un token único firmado con HMAC-SHA256.

    El token combina:
    - El appointment_id (para vincularlo al turno).
    - Un salt aleatorio de 16 bytes (para unicidad incluso con el mismo ID).
    - La JWT_SECRET_KEY (para que no sea falsificable sin la clave).

    El resultado es un hex string de 64 caracteres, URL-safe.
    """
    salt = os.urandom(16)
    message = f"{appointment_id}:{salt.hex()}".encode()
    signature = hmac.new(
        settings.jwt_secret_key.encode(),
        message,
        hashlib.sha256,
    ).hexdigest()
    # Prefijo legible + firma: "chk_<sha256hex>"
    return f"chk_{signature}"
