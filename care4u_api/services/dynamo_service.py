"""DynamoDB data access and validation layer."""

import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key, Attr
from flask import current_app


class DynamoService:
    """Wrap DynamoDB interactions for users and appointments."""

    def __init__(self):
        region = current_app.config['AWS_REGION']
        self._dynamodb = boto3.resource('dynamodb', region_name=region)
        self.users_table = self._dynamodb.Table(current_app.config['USERS_TABLE'])
        self.appointments_table = self._dynamodb.Table(current_app.config['APPOINTMENTS_TABLE'])

    def create_user(self, payload: dict) -> dict:
        user_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        item = {
            'user_id': user_id,
            'username': payload['username'].strip(),
            'email': payload.get('email', '').strip().lower(),
            'phone': payload.get('phone', '').strip(),
            'password_hash': payload['password_hash'],
            'role': payload.get('role', 'patient'),
            'created_at': now,
            'updated_at': now,
        }

        self.users_table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(user_id)'
        )
        return item

    def get_user_by_email_or_phone(self, email: str = '', phone: str = '') -> dict:
        filter_expression = None
        if email and phone:
            filter_expression = Attr('email').eq(email.lower()) | Attr('phone').eq(phone)
        elif email:
            filter_expression = Attr('email').eq(email.lower())
        elif phone:
            filter_expression = Attr('phone').eq(phone)

        if filter_expression is None:
            return {}

        response = self.users_table.scan(FilterExpression=filter_expression, Limit=1)
        items = response.get('Items', [])
        return items[0] if items else {}

    def create_appointment(self, payload: dict, user_id: str) -> dict:
        appointment_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        item = {
            'appointment_id': appointment_id,
            'user_id': user_id,
            'doctor_id': payload['doctor_id'],
            'appointment_date': payload['appointment_date'],
            'appointment_time': payload['appointment_time'],
            'symptoms': payload['symptoms'],
            'status': payload.get('status', 'pending'),
            'created_at': now,
            'updated_at': now,
        }

        self.appointments_table.put_item(
            Item=item,
            ConditionExpression='attribute_not_exists(appointment_id)'
        )
        return item

    def list_appointments_for_user(self, user_id: str) -> list:
        # GSI expected: user_id-index with partition key user_id.
        response = self.appointments_table.query(
            IndexName='user_id-index',
            KeyConditionExpression=Key('user_id').eq(user_id),
        )
        return response.get('Items', [])

    def get_appointment(self, appointment_id: str) -> dict:
        response = self.appointments_table.get_item(Key={'appointment_id': appointment_id})
        return response.get('Item', {})

    def update_appointment(self, appointment_id: str, payload: dict) -> dict:
        update_parts = []
        expr_values = {}

        for field in ['appointment_date', 'appointment_time', 'symptoms', 'status', 'doctor_id']:
            if field in payload:
                update_parts.append(f'{field} = :{field}')
                expr_values[f':{field}'] = payload[field]

        expr_values[':updated_at'] = datetime.now(timezone.utc).isoformat()
        update_parts.append('updated_at = :updated_at')

        if not update_parts:
            return self.get_appointment(appointment_id)

        response = self.appointments_table.update_item(
            Key={'appointment_id': appointment_id},
            UpdateExpression='SET ' + ', '.join(update_parts),
            ExpressionAttributeValues=expr_values,
            ReturnValues='ALL_NEW',
            ConditionExpression='attribute_exists(appointment_id)',
        )
        return response.get('Attributes', {})

    def delete_appointment(self, appointment_id: str):
        self.appointments_table.delete_item(
            Key={'appointment_id': appointment_id},
            ConditionExpression='attribute_exists(appointment_id)',
        )
