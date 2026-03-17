"""Input validation utilities for API requests."""

import re
from typing import Tuple


EMAIL_PATTERN = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_PATTERN = re.compile(r'^\+?[0-9]{10,15}$')
CONTROL_CHARS = re.compile(r'[\x00-\x1f\x7f]')


def validate_email(email: str) -> bool:
    return bool(email and EMAIL_PATTERN.match(email.strip()))


def validate_phone(phone: str) -> bool:
    return bool(phone and PHONE_PATTERN.match(phone.strip()))


def validate_password(password: str) -> bool:
    return bool(password and len(password) >= 8)


def validate_login_identifier(email: str, phone: str) -> Tuple[bool, str]:
    if email and validate_email(email):
        return True, 'email'
    if phone and validate_phone(phone):
        return True, 'phone'
    return False, ''


def validate_required_fields(payload: dict, required_fields: list) -> Tuple[bool, str]:
    for field in required_fields:
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return False, field
    return True, ''


def sanitize_text(value: str, max_length: int = 500) -> str:
    """Trim unsafe control chars and enforce max length."""
    safe = CONTROL_CHARS.sub('', (value or '').strip())
    if len(safe) > max_length:
        safe = safe[:max_length]
    return safe
