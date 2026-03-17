"""Authentication endpoints (JWT, bcrypt)."""

from botocore.exceptions import ClientError
from flask import Blueprint, request

from care4u_api.services.dynamo_service import DynamoService
from care4u_api.utils.responses import error_response, success_response
from care4u_api.utils.security import hash_password, issue_access_token, verify_password
from care4u_api.utils.validators import (
    sanitize_text,
    validate_email,
    validate_login_identifier,
    validate_password,
    validate_phone,
    validate_required_fields,
)

auth_bp = Blueprint('auth', __name__)


@auth_bp.post('/register')
def register_user():
    payload = request.get_json(silent=True) or {}

    ok, missing = validate_required_fields(payload, ['username', 'password'])
    if not ok:
        return error_response(f'Missing required field: {missing}', status_code=400)

    email = sanitize_text((payload.get('email') or '').lower(), max_length=120)
    phone = sanitize_text(payload.get('phone') or '', max_length=20)

    if email and not validate_email(email):
        return error_response('Invalid email format', status_code=400)
    if phone and not validate_phone(phone):
        return error_response('Invalid phone format', status_code=400)
    if not (email or phone):
        return error_response('Either email or phone is required', status_code=400)
    if not validate_password(payload.get('password', '')):
        return error_response('Password must be at least 8 characters', status_code=400)

    service = DynamoService()
    existing = service.get_user_by_email_or_phone(email=email, phone=phone)
    if existing:
        return error_response('User already exists with this email or phone', status_code=409)

    user_input = {
        'username': payload['username'],
        'email': email,
        'phone': phone,
        'password_hash': hash_password(payload['password']),
        'role': payload.get('role', 'patient'),
    }

    try:
        item = service.create_user(user_input)
    except ClientError:
        return error_response('Failed to create user', status_code=500)

    return success_response(
        data={'user_id': item['user_id'], 'username': item['username'], 'role': item['role']},
        message='User registered successfully',
        status_code=201,
    )


@auth_bp.post('/login')
def login_user():
    payload = request.get_json(silent=True) or {}

    password = payload.get('password', '')
    email = sanitize_text((payload.get('email') or '').lower(), max_length=120)
    phone = sanitize_text(payload.get('phone') or '', max_length=20)

    if not password:
        return error_response('Password is required', status_code=400)

    valid_login, _login_type = validate_login_identifier(email=email, phone=phone)
    if not valid_login:
        return error_response('Provide valid email or phone for login', status_code=400)

    service = DynamoService()
    user = service.get_user_by_email_or_phone(email=email, phone=phone)
    if not user:
        return error_response('Invalid credentials', status_code=401)

    if not verify_password(password, user.get('password_hash', '')):
        return error_response('Invalid credentials', status_code=401)

    token = issue_access_token(
        {
            'user_id': user['user_id'],
            'username': user.get('username', ''),
            'role': user.get('role', 'patient'),
        }
    )

    return success_response(
        data={
            'access_token': token,
            'token_type': 'Bearer',
            'user': {
                'user_id': user['user_id'],
                'username': user.get('username', ''),
                'email': user.get('email', ''),
                'phone': user.get('phone', ''),
                'role': user.get('role', 'patient'),
            },
        },
        message='Login successful',
    )
