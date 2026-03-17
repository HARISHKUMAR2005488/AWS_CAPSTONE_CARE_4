"""Configuration values for API runtime."""

import os


class ApiConfig:
    AWS_REGION = os.getenv('AWS_REGION', 'us-east-1')
    USERS_TABLE = os.getenv('USERS_TABLE', 'Users')
    APPOINTMENTS_TABLE = os.getenv('APPOINTMENTS_TABLE', 'Appointments')
    SNS_TOPIC_ARN = os.getenv('SNS_TOPIC_ARN', '')

    JWT_SECRET = os.getenv('JWT_SECRET', os.getenv('FLASK_SECRET_KEY', 'change-me-in-production'))
    JWT_ALGORITHM = 'HS256'
    JWT_EXP_MINUTES = int(os.getenv('JWT_EXP_MINUTES', '60'))

    JSON_SORT_KEYS = False
