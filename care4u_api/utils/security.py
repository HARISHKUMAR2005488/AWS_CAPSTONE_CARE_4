"""JWT and password security helpers."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import current_app


def hash_password(raw_password: str) -> str:
    """Hash password using bcrypt."""
    return bcrypt.hashpw(raw_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(raw_password: str, hashed_password: str) -> bool:
    """Validate password hash safely."""
    try:
        return bcrypt.checkpw(raw_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except ValueError:
        return False


def issue_access_token(identity: dict) -> str:
    """Create short-lived JWT token."""
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=current_app.config['JWT_EXP_MINUTES'])

    payload = {
        'sub': identity,
        'iat': int(now.timestamp()),
        'exp': int(exp.timestamp()),
    }

    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET'],
        algorithm=current_app.config['JWT_ALGORITHM'],
    )


def decode_access_token(token: str) -> dict:
    """Decode and validate JWT token."""
    return jwt.decode(
        token,
        current_app.config['JWT_SECRET'],
        algorithms=[current_app.config['JWT_ALGORITHM']],
    )
