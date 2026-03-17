"""API response helpers."""

from typing import Any

from flask import jsonify


def success_response(data: Any = None, message: str = 'OK', status_code: int = 200):
    payload = {
        'success': True,
        'message': message,
        'data': data,
    }
    return jsonify(payload), status_code


def error_response(message: str = 'Error', status_code: int = 400, details: Any = None):
    payload = {
        'success': False,
        'message': message,
        'details': details,
    }
    return jsonify(payload), status_code
