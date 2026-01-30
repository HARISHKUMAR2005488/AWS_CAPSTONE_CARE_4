import os
import uuid
import logging
from datetime import datetime
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_me")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Context processor to make current_user available in templates
class CurrentUser:
    def __init__(self):
        self.is_authenticated = "username" in session
        self.username = session.get("username")
        self.user_type = session.get("role", "user")
    
    @property
    def is_anonymous(self):
        return not self.is_authenticated


@app.context_processor
def inject_current_user():
    return dict(current_user=CurrentUser())


# AWS configuration (uses instance/role credentials; no hardcoded keys)
REGION = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client("sns", region_name=REGION)
iam = boto3.client("iam", region_name=REGION)
ec2 = boto3.client("ec2", region_name=REGION)

# DynamoDB table names (override via environment variables if needed)
USERS_TABLE = os.getenv("USERS_TABLE", "Users")
DOCTORS_TABLE = os.getenv("DOCTORS_TABLE", "Doctors")
APPOINTMENTS_TABLE = os.getenv("APPOINTMENTS_TABLE", "Appointments")
MEDICAL_RECORDS_TABLE = os.getenv("MEDICAL_RECORDS_TABLE", "MedicalRecords")

users_table = dynamodb.Table(USERS_TABLE)
doctors_table = dynamodb.Table(DOCTORS_TABLE)
appointments_table = dynamodb.Table(APPOINTMENTS_TABLE)
medical_records_table = dynamodb.Table(MEDICAL_RECORDS_TABLE)

# SNS topic for booking notifications (subscribe email endpoints to this topic)
# TODO: Replace with your actual SNS Topic ARN after creating SNS topic in AWS Console
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:455322615378:healthcarenotifications")

# EC2 instance tags for application tracking
EC2_APP_TAG_KEY = os.getenv("EC2_APP_TAG_KEY", "Application")
EC2_APP_TAG_VALUE = os.getenv("EC2_APP_TAG_VALUE", "HealthCare")


def get_user(username: str):
    resp = users_table.get_item(Key={"username": username})
    return resp.get("Item")


def send_notification(subject: str, message: str) -> None:
    """Send notification via SNS topic"""
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not set; skipping notification")
        return
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
        logger.info(f"Notification sent: {subject}")
    except ClientError as exc:
        logger.error("Error sending notification: %s", exc)


def get_iam_user_role(username: str) -> str:
    """Get IAM role details for a user"""
    try:
        response = iam.get_user(UserName=username)
        return response.get('User', {})
    except ClientError as exc:
        if exc.response['Error']['Code'] == 'NoSuchEntity':
            logger.info(f"IAM user {username} does not exist")
            return None
        logger.error(f"Error fetching IAM user {username}: {exc}")
        return None


def get_ec2_instances() -> list:
    """Get EC2 instances running for the application"""
    try:
        response = ec2.describe_instances(
            Filters=[
                {
                    'Name': f'tag:{EC2_APP_TAG_KEY}',
                    'Values': [EC2_APP_TAG_VALUE]
                },
                {
                    'Name': 'instance-state-name',
                    'Values': ['running']
                }
            ]
        )
        instances = []
        for reservation in response.get('Reservations', []):
            for instance in reservation.get('Instances', []):
                instances.append({
                    'instance_id': instance['InstanceId'],
                    'instance_type': instance['InstanceType'],
                    'state': instance['State']['Name'],
                    'launch_time': instance['LaunchTime'].isoformat(),
                    'public_ip': instance.get('PublicIpAddress', 'N/A')
                })
        logger.info(f"Found {len(instances)} running EC2 instances")
        return instances
    except ClientError as exc:
        logger.error(f"Error fetching EC2 instances: {exc}")
        return []


def save_medical_record(username: str, doctor_id: str, record_data: dict) -> bool:
    """Save medical record to DynamoDB"""
    try:
        record_id = str(uuid.uuid4())
        item = {
            "record_id": record_id,
            "username": username,
            "doctor_id": doctor_id,
            "record_data": record_data,
            "created_at": datetime.utcnow().isoformat(),
        }
        medical_records_table.put_item(Item=item)
        logger.info(f"Medical record {record_id} saved for user {username}")
        return True
    except ClientError as exc:
        logger.error(f"Error saving medical record: {exc}")
        return False


def get_medical_records(username: str) -> list:
    """Retrieve medical records for a user"""
    try:
        response = medical_records_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('username').eq(username)
        )
        return response.get('Items', [])
    except ClientError as exc:
        logger.error(f"Error fetching medical records for {username}: {exc}")
        return []


@lru_cache(maxsize=1)
def has_username_index() -> bool:
    try:
        desc = dynamodb.meta.client.describe_table(TableName=appointments_table.name)
        gsis = desc.get("Table", {}).get("GlobalSecondaryIndexes", [])
        return any(gsi.get("IndexName") == "username-index" for gsi in gsis)
    except ClientError as exc:
        logger.error("Failed to describe table for GSI check: %s", exc)
        return False


@app.route("/aws-health")
def aws_health():
    """Display AWS infrastructure health status"""
    if "username" not in session or session.get("role") != "admin":
        flash("Admin access required", "danger")
        return redirect(url_for("login"))
    
    try:
        ec2_instances = get_ec2_instances()
        
        # Get DynamoDB table stats
        table_stats = {}
        for table_name, table_obj in [
            ("Users", users_table),
            ("Doctors", doctors_table),
            ("Appointments", appointments_table),
            ("MedicalRecords", medical_records_table)
        ]:
            try:
                desc = dynamodb.meta.client.describe_table(TableName=table_obj.name)
                table_stats[table_name] = {
                    "item_count": desc["Table"]["ItemCount"],
                    "size_bytes": desc["Table"]["TableSizeBytes"],
                    "status": desc["Table"]["TableStatus"]
                }
            except ClientError:
                table_stats[table_name] = {"status": "Error fetching stats"}
        
        return render_template(
            "aws_health.html",
            ec2_instances=ec2_instances,
            table_stats=table_stats,
            region=REGION
        )
    except Exception as e:
        logger.error(f"Error in aws_health route: {e}")
        flash("Error fetching AWS health status", "danger")
        return redirect(url_for("dashboard"))


@app.route("/medical-records")
def medical_records():
    """View medical records for a user"""
    if "username" not in session:
        return redirect(url_for("login"))
    
    username = session["username"]
    records = get_medical_records(username)
    
    return render_template("patient_records.html", records=records, username=username)


@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("role", None)
    flash("Logged out", "info")
    return redirect(url_for("index"))

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        role = request.form.get("role", "user").strip().lower()

        allowed_roles = {"user", "doctor", "admin"}
        if role not in allowed_roles:
            role = "user"

        if role == "admin":
            admin_key = request.form.get("admin_key", "").strip()
            if admin_key != "IAMADMIN":
                flash("Invalid admin access key", "danger")
                return redirect(url_for("signup"))

        existing = users_table.get_item(Key={"username": username})
        if "Item" in existing:
            flash("User already exists", "warning")
            return redirect(url_for("signup"))

        item = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "role": role,
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
        }

        if role == "doctor":
            doctor_id = str(uuid.uuid4())
            item["doctor_id"] = doctor_id
            doctors_table.put_item(
                Item={
                    "id": doctor_id,
                    "name": username,
                    "specialization": request.form.get("specialization", "General"),
                    "email": request.form.get("email", ""),
                    "phone": request.form.get("phone", ""),
                }
            )

        users_table.put_item(Item=item)
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Accept both email and username for login
        email = request.form.get("email", "").strip()
        username = request.form.get("username", email).strip()
        password = request.form.get("password", "").strip()

        response = users_table.get_item(Key={"username": username})
        item = response.get("Item")
        if item:
            password_hash = item.get("password_hash")
            password_plain = item.get("password")

            if (password_hash and check_password_hash(password_hash, password)) or (
                password_plain and password_plain == password
            ):
                session["username"] = username
                session["role"] = item.get("role", "user")
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard"))

        flash("Invalid credentials", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/home")
def home():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]

    doctors_resp = doctors_table.scan()
    doctors = doctors_resp.get("Items", [])

    appts_resp = (
        appointments_table.query(
            IndexName="username-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("username").eq(username),
        )
        if has_username_index()
        else appointments_table.scan()
    )

    user_appointments = appts_resp.get("Items", [])
    if not has_username_index():
        user_appointments = [a for a in user_appointments if a.get("username") == username]

    return render_template(
        "home.html",
        username=username,
        doctors=doctors,
        appointments=user_appointments,
    )


@app.route("/dashboard")
@app.route("/user-dashboard")
@app.route("/admin-dashboard")
@app.route("/doctor-dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session.get("username")
    role = session.get("role", "user")

    if role == "admin":
        doctors_resp = doctors_table.scan()
        users_resp = users_table.scan()
        return render_template(
            "admin.html",
            username=username,
            doctors=doctors_resp.get("Items", []),
            users=users_resp.get("Items", []),
        )

    if role == "doctor":
        user_item = get_user(username)
        doctor_id = (user_item or {}).get("doctor_id")

        doctor_profile = doctors_table.get_item(Key={"id": doctor_id}).get("Item") if doctor_id else None

        if not doctor_profile:
            # Fallback: try to match doctor by name
            scan_resp = doctors_table.scan()
            doctor_profile = next((d for d in scan_resp.get("Items", []) if d.get("name") == username), None)
            doctor_id = doctor_profile.get("id") if doctor_profile else None
        
        # Ensure doctor profile has all required fields with defaults
        if doctor_profile:
            doctor_profile.setdefault("consultation_fee", 0.0)
            doctor_profile.setdefault("qualifications", "")
            doctor_profile.setdefault("experience", 0)
            doctor_profile.setdefault("available_days", "")
            doctor_profile.setdefault("available_time", "")

        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) if a.get("doctor_id") == doctor_id]
        
        # Calculate appointment statistics
        from datetime import date
        today = date.today()
        total_appointments = len(doctor_appts)
        pending_count = len([a for a in doctor_appts if a.get("status") == "pending"])
        confirmed_count = len([a for a in doctor_appts if a.get("status") == "confirmed"])
        completed_count = len([a for a in doctor_appts if a.get("status") == "completed"])

        return render_template(
            "doctor.html",
            username=username,
            doctor=doctor_profile,
            appointments=doctor_appts,
            today=today,
            total_appointments=total_appointments,
            pending_count=pending_count,
            confirmed_count=confirmed_count,
            completed_count=completed_count,
        )

    # Default: user/patient view
    appts_resp = (
        appointments_table.query(
            IndexName="username-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("username").eq(username),
        )
        if has_username_index()
        else appointments_table.scan()
    )
    appointments = appts_resp.get("Items", [])
    if not has_username_index():
        appointments = [a for a in appointments if a.get("username") == username]

    return render_template("user.html", username=username, appointments=appointments)


# Add route aliases for template compatibility
app.add_url_rule("/user-dashboard", "user_dashboard", dashboard)
app.add_url_rule("/admin-dashboard", "admin_dashboard", dashboard)
app.add_url_rule("/doctor-dashboard", "doctor_dashboard", dashboard)

@app.route("/doctor-patients")
def doctor_patients():
    """View patients for a doctor"""
    if "username" not in session or session.get("role") != "doctor":
        flash("Access denied", "danger")
        return redirect(url_for("login"))
    
    # Placeholder: redirect to doctor dashboard for now
    return redirect(url_for("dashboard"))

@app.route("/add-doctor", methods=["POST"])
def add_doctor():
    """Add a new doctor (admin only)"""
    if "username" not in session or session.get("role") != "admin":
        return {"success": False, "message": "Access denied"}, 403
    
    try:
        data = request.get_json()
        doctor_id = str(uuid.uuid4())
        
        doctors_table.put_item(
            Item={
                "id": doctor_id,
                "name": data.get("name"),
                "specialization": data.get("specialization", "General"),
                "email": data.get("email", ""),
                "phone": data.get("phone", ""),
                "qualifications": data.get("qualifications", ""),
                "experience": int(data.get("experience", 0)),
                "consultation_fee": float(data.get("consultation_fee", 0.0)),
                "available_days": data.get("available_days", ""),
                "available_time": data.get("available_time", ""),
            }
        )
        
        return {"success": True, "message": "Doctor added successfully", "doctor_id": doctor_id}
    except Exception as e:
        logger.error(f"Error adding doctor: {e}")
        return {"success": False, "message": str(e)}, 500

@app.route("/doctors")
def doctors():
    if "username" not in session:
        return redirect(url_for("login"))

    doctors_resp = doctors_table.scan()
    doctors_list = doctors_resp.get("Items", [])
    
    # Extract unique specializations
    specializations = list(set([d.get("specialization", "General") for d in doctors_list if d.get("specialization")]))
    specializations.sort()
    
    return render_template("doctors.html", doctors=doctors_list, specializations=specializations)

@app.route("/book/<doctor_id>", methods=["GET", "POST"])
def book(doctor_id: str):
    if "username" not in session:
        return redirect(url_for("login"))

    doctor = doctors_table.get_item(Key={"id": doctor_id}).get("Item")
    if not doctor:
        flash("Doctor not found", "danger")
        return redirect(url_for("doctors"))

    if request.method == "POST":
        username = session["username"]
        appointment_id = str(uuid.uuid4())
        date = request.form.get("date")
        time = request.form.get("time")
        reason = request.form.get("reason", "").strip()
        medical_notes = request.form.get("medical_notes", "").strip()

        appointments_table.put_item(
            Item={
                "id": appointment_id,
                "doctor_id": doctor_id,
                "doctor_name": doctor.get("name"),
                "username": username,
                "date": date,
                "time": time,
                "reason": reason,
                "medical_notes": medical_notes,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        # Save medical record if notes provided
        if medical_notes:
            save_medical_record(
                username=username,
                doctor_id=doctor_id,
                record_data={
                    "appointment_id": appointment_id,
                    "notes": medical_notes,
                    "date": date
                }
            )

        send_notification(
            subject="Appointment Booked",
            message=f"User {username} booked {doctor.get('name')} on {date} at {time}. Reason: {reason}",
        )

        logger.info(f"Appointment {appointment_id} created for user {username}")
        flash("Appointment booked successfully", "success")
        return redirect(url_for("home"))

    return render_template("bookings.html", doctor=doctor)


@app.route("/appointments")
def my_appointments():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    appts_resp = (
        appointments_table.query(
            IndexName="username-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("username").eq(username),
        )
        if has_username_index()
        else appointments_table.scan()
    )

    appointments = appts_resp.get("Items", [])
    if not has_username_index():
        appointments = [a for a in appointments if a.get("username") == username]

    return render_template("appointments.html", appointments=appointments)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)