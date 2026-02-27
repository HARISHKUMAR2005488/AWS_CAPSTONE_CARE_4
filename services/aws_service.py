import boto3
import logging
import uuid
from datetime import datetime
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr
from config import Config

logger = logging.getLogger(__name__)

class AWSService:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AWSService, cls).__new__(cls)
            cls._instance._init_resources()
        return cls._instance

    def _init_resources(self):
        """Initialize AWS resources using Config"""
        self.region = Config.AWS_REGION
        self.dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.sns = boto3.client('sns', region_name=self.region)
        self.iam = boto3.client('iam', region_name=self.region)
        self.ec2 = boto3.client('ec2', region_name=self.region)
        
        # Tables
        self.users_table = self.dynamodb.Table(Config.USERS_TABLE)
        self.doctors_table = self.dynamodb.Table(Config.DOCTORS_TABLE)
        self.appointments_table = self.dynamodb.Table(Config.APPOINTMENTS_TABLE)
        self.records_table = self.dynamodb.Table(Config.MEDICAL_RECORDS_TABLE)
        self.audit_table = self.dynamodb.Table(Config.AUDIT_LOGS_TABLE)

    # --- Audit Logging ---
    def log_audit(self, actor_username, action, resource, details=None):
        """Log sensitive actions to DynamoDB"""
        try:
            log_id = str(uuid.uuid4())
            item = {
                'id': log_id,
                'actor': actor_username,
                'action': action,
                'resource': resource,
                'details': details or {},
                'timestamp': datetime.utcnow().isoformat()
            }
            self.audit_table.put_item(Item=item)
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    # --- User Management ---
    def get_user(self, username):
        try:
            resp = self.users_table.get_item(Key={'username': username})
            return resp.get('Item')
        except ClientError as e:
            logger.error(f"Db Error get_user: {e}")
            return None

    def create_user(self, user_item):
        try:
            self.users_table.put_item(Item=user_item)
            self.log_audit(user_item['username'], 'CREATE_USER', 'UsersTable')
            return True
        except ClientError as e:
            logger.error(f"Db Error create_user: {e}")
            return False

    def update_user(self, username, updates):
        """Update user attributes"""
        try:
            update_expr = "SET " + ", ".join([f"{k} = :{k}" for k in updates.keys()])
            expr_values = {f":{k}": v for k, v in updates.items()}
            
            self.users_table.update_item(
                Key={'username': username},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
            self.log_audit(username, 'UPDATE_USER', 'UsersTable', updates)
            return True
        except ClientError as e:
            logger.error(f"Error updating user {username}: {e}")
            return False

    def delete_user(self, username):
        """Delete a user"""
        try:
            self.users_table.delete_item(Key={'username': username})
            self.log_audit(username, 'DELETE_USER', 'UsersTable')
            return True
        except ClientError as e:
            logger.error(f"Error deleting user {username}: {e}")
            return False

    def get_all_users(self):
        """Get all users (for admin)"""
        try:
            resp = self.users_table.scan()
            return resp.get('Items', [])
        except ClientError as e:
            logger.error(f"Error fetching users: {e}")
            return []

    # --- Doctor Management ---
    def get_doctor_by_id(self, doctor_id):
        try:
            resp = self.doctors_table.get_item(Key={'id': doctor_id})
            return resp.get('Item')
        except ClientError:
            return None
            
    def get_all_doctors(self):
        resp = self.doctors_table.scan()
        return resp.get('Items', [])

    # --- Appointment Management (Optimized) ---
    def get_appointments_for_doctor(self, doctor_id):
        try:
            resp = self.appointments_table.query(
                IndexName='doctor-index',
                KeyConditionExpression=Key('doctor_id').eq(doctor_id)
            )
            return resp.get('Items', [])
        except ClientError:
            resp = self.appointments_table.scan()
            return [i for i in resp.get('Items', []) if i.get('doctor_id') == doctor_id]

    def get_appointments_for_patient(self, username):
        try:
            resp = self.appointments_table.query(
                IndexName='username-index',
                KeyConditionExpression=Key('username').eq(username)
            )
            return resp.get('Items', [])
        except ClientError:
            resp = self.appointments_table.scan()
            return [i for i in resp.get('Items', []) if i.get('username') == username]

    # --- SNS Notifications ---
    def send_notification(self, subject, message):
        if not Config.SNS_TOPIC_ARN:
            return
        
        if "High Severity" in message or "Emergency" in message:
            subject = f"[URGENT] {subject}"

        try:
            self.sns.publish(
                TopicArn=Config.SNS_TOPIC_ARN,
                Subject=subject,
                Message=message
            )
        except ClientError as e:
            logger.error(f"SNS Error: {e}")

    # --- Infrastructure ---
    def get_ec2_health(self):
        try:
             response = self.ec2.describe_instances(
                Filters=[
                    {'Name': f'tag:{Config.EC2_APP_TAG_KEY}', 'Values': [Config.EC2_APP_TAG_VALUE]},
                    {'Name': 'instance-state-name', 'Values': ['running']}
                ]
            )
             instances = []
             for r in response.get('Reservations', []):
                 for i in r.get('Instances', []):
                     instances.append({
                         'id': i['InstanceId'],
                         'type': i['InstanceType'],
                         'launch_time': i['LaunchTime'].isoformat(),
                         'public_ip': i.get('PublicIpAddress', 'N/A')
                     })
             return instances
        except ClientError as e:
             logger.error(f"EC2 Error: {e}")
             return []
