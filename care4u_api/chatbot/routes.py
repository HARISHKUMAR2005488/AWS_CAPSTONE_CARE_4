"""Chatbot API endpoints."""

from flask import Blueprint, request

from care4u_api.middleware.auth import jwt_required
from care4u_api.services.chatbot_service import build_chatbot_response
from care4u_api.utils.responses import error_response, success_response
from care4u_api.utils.validators import sanitize_text, validate_required_fields

chatbot_bp = Blueprint('chatbot', __name__)


@chatbot_bp.post('/message')
@jwt_required
def chatbot_message():
    payload = request.get_json(silent=True) or {}
    ok, missing = validate_required_fields(payload, ['message'])
    if not ok:
        return error_response(f'Missing required field: {missing}', status_code=400)

    message = sanitize_text(payload['message'], max_length=1200)
    if len(message) > 1200:
        return error_response('Message too long', status_code=400)

    result = build_chatbot_response(message)
    return success_response(data=result, message='Chatbot response generated')
