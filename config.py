import os

class Config:
    # Security
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    ADMIN_REGISTRATION_KEY = os.environ.get('ADMIN_REGISTRATION_KEY') or 'IAMADMIN_CHANGE_ME_IN_PROD'
    
    # AWS Configuration
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # DynamoDB Tables
    USERS_TABLE = os.environ.get('USERS_TABLE', 'Users')
    DOCTORS_TABLE = os.environ.get('DOCTORS_TABLE', 'Doctors')
    APPOINTMENTS_TABLE = os.environ.get('APPOINTMENTS_TABLE', 'Appointments')
    MEDICAL_RECORDS_TABLE = os.environ.get('MEDICAL_RECORDS_TABLE', 'MedicalRecords')
    AUDIT_LOGS_TABLE = os.environ.get('AUDIT_LOGS_TABLE', 'AuditLogs')
    
    # SNS
    # TODO: Update this ARN with your real SNS Topic ARN after detailed setup
    SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'arn:aws:sns:us-east-1:455322615378:healthcarenotification')
    
    # EC2 Tracking
    EC2_APP_TAG_KEY = os.environ.get('EC2_APP_TAG_KEY', 'Application')
    EC2_APP_TAG_VALUE = os.environ.get('EC2_APP_TAG_VALUE', 'HealthCare')
    
    # Uploads
    UPLOAD_FOLDER = 'uploads'
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif'}