"""SNS notification endpoints."""

from botocore.exceptions import ClientError
from flask import Blueprint, request

from care4u_api.middleware.auth import jwt_required
from care4u_api.services.sns_service import SnsService
from care4u_api.utils.responses import error_response, success_response
from care4u_api.utils.validators import sanitize_text, validate_required_fields

notifications_bp = Blueprint('notifications', __name__)


@notifications_bp.post('/publish')
@jwt_required
def publish_notification():
    payload = request.get_json(silent=True) or {}
    ok, missing = validate_required_fields(payload, ['subject', 'message'])
    if not ok:
        return error_response(f'Missing required field: {missing}', status_code=400)

    subject = sanitize_text(payload.get('subject', ''), max_length=120)
    message = sanitize_text(payload.get('message', ''), max_length=2000)

    try:
        publish_result = SnsService().publish(
            subject=subject,
            message=message,
        )
    except ValueError as exc:
        return error_response(str(exc), status_code=400)
    except ClientError:
        return error_response('Failed to publish notification', status_code=500)

    return success_response(data=publish_result, message='Notification published', status_code=201)
