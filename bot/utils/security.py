"""JWT-утилиты для Mini App сессий."""

from __future__ import annotations

import time
from typing import Any, Dict

import jwt
from jwt import InvalidTokenError

from config.settings import get_settings

settings = get_settings()


def issue_session_token(user_id: int, ttl_minutes: int | None = None) -> str:
    """Выдаёт короткоживущий JWT для авторизации в Mini App."""

    ttl = ttl_minutes or settings.security.jwt_ttl_minutes
    now = int(time.time())
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + ttl * 60,
    }
    return jwt.encode(payload, settings.security.jwt_secret.get_secret_value(), algorithm=settings.security.jwt_algorithm)


def decode_session_token(token: str) -> Dict[str, Any]:
    """Валидирует и возвращает payload JWT."""

    try:
        payload = jwt.decode(
            token,
            settings.security.jwt_secret.get_secret_value(),
            algorithms=[settings.security.jwt_algorithm],
        )
    except InvalidTokenError as exc:
        raise ValueError("Недействительный токен Mini App") from exc
    return payload


__all__ = ["issue_session_token", "decode_session_token"]




