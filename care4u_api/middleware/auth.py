"""JWT auth middleware for protected routes."""

from functools import wraps

import jwt
from flask import g, request

from care4u_api.utils.responses import error_response
from care4u_api.utils.security import decode_access_token


def jwt_required(fn):
    """Protect route using bearer JWT token."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return error_response('Missing bearer token', status_code=401)

        token = auth_header.replace('Bearer ', '', 1).strip()
        if not token:
            return error_response('Missing bearer token', status_code=401)

        try:
            payload = decode_access_token(token)
            g.current_identity = payload.get('sub', {})
        except jwt.ExpiredSignatureError:
            return error_response('Token expired', status_code=401)
        except jwt.InvalidTokenError:
            return error_response('Invalid token', status_code=401)

        return fn(*args, **kwargs)

    return wrapper
