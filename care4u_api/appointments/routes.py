"""Appointments REST endpoints."""

from botocore.exceptions import ClientError
from flask import Blueprint, g, request

from care4u_api.middleware.auth import jwt_required
from care4u_api.services.dynamo_service import DynamoService
from care4u_api.utils.responses import error_response, success_response
from care4u_api.utils.validators import sanitize_text, validate_required_fields

appointments_bp = Blueprint('appointments', __name__)


@appointments_bp.get('/')
@jwt_required
def list_appointments():
    service = DynamoService()
    items = service.list_appointments_for_user(g.current_identity['user_id'])
    return success_response(data={'appointments': items}, message='Appointments fetched')


@appointments_bp.post('/')
@jwt_required
def create_appointment():
    payload = request.get_json(silent=True) or {}

    ok, missing = validate_required_fields(
        payload,
        ['doctor_id', 'appointment_date', 'appointment_time', 'symptoms'],
    )
    if not ok:
        return error_response(f'Missing required field: {missing}', status_code=400)

    payload['doctor_id'] = sanitize_text(payload.get('doctor_id', ''), max_length=80)
    payload['appointment_date'] = sanitize_text(payload.get('appointment_date', ''), max_length=20)
    payload['appointment_time'] = sanitize_text(payload.get('appointment_time', ''), max_length=20)
    payload['symptoms'] = sanitize_text(payload.get('symptoms', ''), max_length=1200)

    try:
        item = DynamoService().create_appointment(payload, g.current_identity['user_id'])
    except ClientError:
        return error_response('Failed to create appointment', status_code=500)

    return success_response(data={'appointment': item}, message='Appointment created', status_code=201)


@appointments_bp.put('/<appointment_id>')
@jwt_required
def update_appointment(appointment_id: str):
    payload = request.get_json(silent=True) or {}
    for field, max_len in {
        'doctor_id': 80,
        'appointment_date': 20,
        'appointment_time': 20,
        'symptoms': 1200,
        'status': 30,
    }.items():
        if field in payload:
            payload[field] = sanitize_text(str(payload[field]), max_length=max_len)

    service = DynamoService()

    existing = service.get_appointment(appointment_id)
    if not existing:
        return error_response('Appointment not found', status_code=404)
    if existing.get('user_id') != g.current_identity['user_id']:
        return error_response('Forbidden', status_code=403)

    try:
        updated = service.update_appointment(appointment_id, payload)
    except ClientError:
        return error_response('Failed to update appointment', status_code=500)

    return success_response(data={'appointment': updated}, message='Appointment updated')


@appointments_bp.delete('/<appointment_id>')
@jwt_required
def delete_appointment(appointment_id: str):
    service = DynamoService()

    existing = service.get_appointment(appointment_id)
    if not existing:
        return error_response('Appointment not found', status_code=404)
    if existing.get('user_id') != g.current_identity['user_id']:
        return error_response('Forbidden', status_code=403)

    try:
        service.delete_appointment(appointment_id)
    except ClientError:
        return error_response('Failed to delete appointment', status_code=500)

    return success_response(message='Appointment deleted')
