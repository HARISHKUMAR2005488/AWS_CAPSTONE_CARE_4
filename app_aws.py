import os
import uuid
import logging
from datetime import datetime
from functools import lru_cache
from decimal import Decimal, InvalidOperation

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

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


def to_decimal(value, default="0"):
    """Convert values to Decimal for DynamoDB numeric compatibility."""
    if value is None or value == "":
        value = default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(str(default))


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
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:455322615378:Healthcarenotifications")

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
        records = response.get('Items', [])
        for record in records:
            upload_date = record.get("upload_date")
            if isinstance(upload_date, str):
                try:
                    record["upload_date"] = datetime.fromisoformat(upload_date)
                except ValueError:
                    record["upload_date"] = datetime.utcnow()
            elif upload_date is None:
                record["upload_date"] = datetime.utcnow()
        return records
    except ClientError as exc:
        logger.error(f"Error fetching medical records for {username}: {exc}")
        return []


def analyze_symptoms(symptoms_text: str) -> dict:
    """
    Symptom analysis engine
    Detects emergency conditions, suggests specializations, and calculates severity
    """
    symptoms_text_lower = symptoms_text.lower()

    emergency_indicators = {
        "chest pain": 3,
        "heart attack": 5,
        "stroke": 5,
        "seizure": 4,
        "difficulty breathing": 4,
        "shortness of breath": 4,
        "severe bleeding": 5,
        "unconscious": 5,
        "severe allergic": 4,
        "anaphylaxis": 5,
        "poisoning": 5,
        "overdose": 5,
        "severe trauma": 5,
        "severe burns": 5,
        "loss of consciousness": 5,
        "severe head injury": 4,
        "drowning": 5,
        "choking": 4,
        "unable to breathe": 5,
        "severe abdominal pain": 3,
        "rupture": 4,
        "serious injury": 3,
        "bleeding heavily": 4,
        "gunshot": 5,
        "stab wound": 4,
    }

    specialization_map = {
        "Cardiology": {
            "keywords": ["chest pain", "heart", "palpitation", "arrhythmia", "hypertension", "blood pressure", "cardiac", "angina", "irregular heartbeat", "shortness of breath"],
        },
        "Neurology": {
            "keywords": ["headache", "migraine", "dizziness", "stroke", "seizure", "tremor", "nerve", "neuropathy", "numbness", "paralysis", "vertigo", "brain"],
        },
        "Orthopedics": {
            "keywords": ["fracture", "bone", "joint", "arthritis", "back pain", "knee pain", "shoulder pain", "ankle", "sprain", "ligament"],
        },
        "Gastroenterology": {
            "keywords": ["stomach", "abdominal", "nausea", "vomiting", "diarrhea", "constipation", "acid reflux", "heartburn", "liver", "digestive", "intestinal"],
        },
        "Pulmonology": {
            "keywords": ["cough", "asthma", "lung", "bronchitis", "pneumonia", "respiratory", "breathing", "wheezing", "shortness of breath", "tuberculosis"],
        },
        "Dermatology": {
            "keywords": ["rash", "skin", "acne", "eczema", "psoriasis", "mole", "wart", "itching", "fungal", "allergy"],
        },
        "Ophthalmology": {
            "keywords": ["eye", "vision", "blind", "blurred", "eye pain", "glaucoma", "cataract", "contact lens", "glasses"],
        },
        "ENT (Otolaryngology)": {
            "keywords": ["ear", "nose", "throat", "hearing", "tinnitus", "sinus", "sinusitis", "sore throat", "hoarse", "vertigo"],
        },
        "Pediatrics": {
            "keywords": ["baby", "child", "infant", "kid", "vaccination", "fever", "crying", "development", "growth"],
        },
        "Psychiatry": {
            "keywords": ["depression", "anxiety", "stress", "panic", "mental", "psychological", "emotional", "insomnia", "sleep", "mood"],
        },
    }

    emergency_score = 0
    for emergency_keyword, weight in emergency_indicators.items():
        if emergency_keyword in symptoms_text_lower:
            emergency_score += weight

    is_emergency = emergency_score >= 4
    critical_phrases = ["severe", "sudden", "critical", "emergency", "urgent", "immediate"]
    has_critical_modifier = any(phrase in symptoms_text_lower for phrase in critical_phrases)
    if has_critical_modifier and emergency_score >= 2:
        is_emergency = True

    severity_score = min(emergency_score * 15, 100)
    if symptoms_text_lower.count(" ") > 10:
        severity_score = min(severity_score + 10, 100)

    matching_specializations = []
    for specialty, info in specialization_map.items():
        keyword_matches = sum(1 for keyword in info["keywords"] if keyword in symptoms_text_lower)
        if keyword_matches > 0:
            matching_specializations.append({
                "name": specialty,
                "score": keyword_matches,
                "keywords_matched": keyword_matches,
            })

    matching_specializations.sort(key=lambda x: x["score"], reverse=True)
    top_specializations = matching_specializations[:3] or [{"name": "General Practice", "score": 1, "keywords_matched": 0}]

    formatted_specializations = []
    for spec in top_specializations:
        if spec["name"] != "General Practice":
            keywords_found = [k for k in specialization_map[spec["name"]]["keywords"] if k in symptoms_text_lower]
            if keywords_found:
                reason = f"Based on your mention of {', '.join(keywords_found[:2])}"
                if len(keywords_found) > 2:
                    reason += f" and other {spec['name'].lower()} symptoms"
            else:
                reason = "Recommended for overall assessment"
        else:
            reason = "For general health evaluation and preliminary diagnosis"

        formatted_specializations.append({
            "name": spec["name"],
            "reason": reason,
        })

    response_message = generate_assistant_response(
        symptoms_text,
        is_emergency,
        formatted_specializations,
        severity_score,
    )

    return {
        "response": response_message,
        "is_emergency": is_emergency,
        "specializations": formatted_specializations,
        "severity_score": severity_score,
    }


def generate_assistant_response(symptoms: str, is_emergency: bool, specializations: list, severity: int) -> str:
    """Generate a helpful assistant response message"""
    if is_emergency:
        return (
            "🚨 <strong>URGENT: Please Seek Immediate Medical Attention</strong><br><br>"
            "Based on your description, this appears to be a medical emergency. "
            "Please call emergency services (911 in the US) or visit the nearest emergency room immediately. "
            "Do not wait for an appointment.<br><br>"
            f"Your symptoms indicate potential {specializations[0]['name'] if specializations else 'medical'} concerns."
        )

    response = "<strong>Thank you for sharing your symptoms.</strong><br><br>"
    if severity >= 70:
        response += (
            "Your symptoms appear to be significant and require prompt medical attention. "
            "We recommend scheduling an appointment with a specialist as soon as possible.<br><br>"
        )
    elif severity >= 40:
        response += (
            "Your symptoms suggest you would benefit from a medical evaluation. "
            "Please consider scheduling an appointment within the next few days.<br><br>"
        )
    else:
        response += (
            "Based on your description, it's good to get these symptoms evaluated by a medical professional. "
            "You can schedule a consultation when convenient.<br><br>"
        )

    if specializations:
        spec_names = [s["name"] for s in specializations[:2]]
        response += f"<strong>Recommended specialists:</strong> {', '.join(spec_names)}.<br><br>"

    response += (
        "<em>Note: This is an AI-powered preliminary assessment only and does not replace "
        "professional medical advice. Always consult with a qualified healthcare provider.</em>"
    )
    return response


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


@app.route("/user/upload-document", methods=["POST"])
def upload_document():
    """Upload a medical document for a user"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401

    if "document" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    file = request.files["document"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    allowed_extensions = {"pdf", "jpg", "jpeg", "png"}
    if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in allowed_extensions:
        return jsonify({"success": False, "message": "Only PDF, JPG, JPEG, and PNG files are allowed"}), 400

    try:
        username = session["username"]
        description = (request.form.get("description") or "").strip()
        filename = secure_filename(file.filename)
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"

        upload_dir = os.path.join(app.instance_path, "uploads", username)
        os.makedirs(upload_dir, exist_ok=True)

        file_path = os.path.join(upload_dir, safe_name)
        file.save(file_path)

        file_size = os.path.getsize(file_path)
        file_type = filename.rsplit(".", 1)[1].lower() if "." in filename else "unknown"

        record_id = str(uuid.uuid4())
        medical_records_table.put_item(
            Item={
                "id": record_id,
                "record_id": record_id,
                "username": username,
                "filename": safe_name,
                "original_filename": filename,
                "description": description,
                "file_type": file_type,
                "file_size": file_size,
                "upload_date": datetime.utcnow().isoformat(),
            }
        )

        return jsonify({"success": True, "message": "Document uploaded", "description": description})
    except Exception as exc:
        logger.error("Error uploading document: %s", exc)
        return jsonify({"success": False, "message": "Upload failed"}), 500


@app.route("/upload-profile-picture", methods=["POST"])
def upload_profile_picture():
    """Upload profile picture for user (patient/doctor/admin)"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401

    if "profile_picture" not in request.files:
        return jsonify({"success": False, "message": "No file provided"}), 400

    file = request.files["profile_picture"]
    if file.filename == "":
        return jsonify({"success": False, "message": "No file selected"}), 400

    allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
    if "." not in file.filename or file.filename.rsplit(".", 1)[1].lower() not in allowed_extensions:
        return jsonify({"success": False, "message": "Only image files are allowed (png, jpg, jpeg, gif, webp)"}), 400

    try:
        filename = secure_filename(file.filename)
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_profile_{filename}"
        profile_pic_dir = os.path.join(app.instance_path, "uploads", "profile_pictures")
        os.makedirs(profile_pic_dir, exist_ok=True)
        file_path = os.path.join(profile_pic_dir, safe_name)
        file.save(file_path)

        relative_path = f"profile_pictures/{safe_name}"
        username = session["username"]
        role = session.get("role", "user")

        if role == "doctor":
            user = get_user(username)
            doctor_id = user.get("doctor_id") if user else None
            if not doctor_id:
                return jsonify({"success": False, "message": "Doctor profile not found"}), 404

            doctors_table.update_item(
                Key={"id": doctor_id},
                UpdateExpression="SET profile_image = :img",
                ExpressionAttributeValues={":img": relative_path},
            )
        else:
            users_table.update_item(
                Key={"username": username},
                UpdateExpression="SET profile_picture = :img",
                ExpressionAttributeValues={":img": relative_path},
            )

        return jsonify({"success": True, "message": "Profile picture updated successfully"})
    except Exception as exc:
        logger.error("Error uploading profile picture: %s", exc)
        return jsonify({"success": False, "message": "Error uploading file"}), 500


@app.route("/uploads/profile_pictures/<path:filename>")
def serve_profile_picture(filename: str):
    """Serve profile pictures from the instance uploads folder"""
    uploads_dir = os.path.join(app.instance_path, "uploads")
    try:
        return send_from_directory(uploads_dir, f"profile_pictures/{filename}")
    except FileNotFoundError:
        return ("", 404)


@app.route("/user/chat-assistant", methods=["POST"])
def chat_assistant():
    """AI-powered health symptom analyzer and doctor recommendation engine"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401

    role = session.get("role", "user")
    if role not in {"user", "patient"}:
        return jsonify({"success": False, "message": "This feature is for patients only"}), 403

    data = request.get_json(silent=True) or {}
    symptoms = str(data.get("symptoms", "")).lower().strip()
    if not symptoms:
        return jsonify({"success": False, "message": "Please describe your symptoms"}), 400

    analysis = analyze_symptoms(symptoms)

    return jsonify({
        "success": True,
        "response": analysis["response"],
        "is_emergency": analysis["is_emergency"],
        "specializations": analysis["specializations"],
        "severity_score": analysis["severity_score"],
    })


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
            
            # Get doctor-specific fields from form
            specialization = request.form.get("specialization", "General")
            qualifications = request.form.get("qualifications", "")
            experience = request.form.get("experience", "0")
            consultation_fee = request.form.get("consultation_fee", "0")
            available_days = request.form.get("available_days", "")
            available_time = request.form.get("available_time", "")
            
            doctors_table.put_item(
                Item={
                    "id": doctor_id,
                    "name": username,
                    "specialization": specialization,
                    "email": request.form.get("email", ""),
                    "phone": request.form.get("phone", ""),
                    "qualifications": qualifications,
                    "experience": int(experience) if experience.isdigit() else 0,
                    "consultation_fee": to_decimal(consultation_fee, "0"),
                    "available_days": available_days,
                    "available_time": available_time,
                    "is_available": True,
                }
            )
            logger.info(f"Doctor profile created: {doctor_id} for user {username}")

        users_table.put_item(Item=item)
        
        # Send notification for new signup
        role_display = "Doctor" if role == "doctor" else "Admin" if role == "admin" else "Patient"
        send_notification(
            subject=f"New {role_display} Registration",
            message=f"New {role_display} registered:\nUsername: {username}\nEmail: {item.get('email')}\nRole: {role}"
        )
        
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
                
                # Send notification for successful login
                role_display = item.get("role", "user").capitalize()
                send_notification(
                    subject=f"User Login - {username}",
                    message=f"User logged in:\nUsername: {username}\nRole: {role_display}\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
                )
                
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
            doctor_profile.setdefault("consultation_fee", Decimal("0"))
            doctor_profile.setdefault("qualifications", "")
            doctor_profile.setdefault("experience", 0)
            doctor_profile.setdefault("available_days", "")
            doctor_profile.setdefault("available_time", "")

        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) if a.get("doctor_id") == doctor_id]
        
        # Normalize doctor appointments for template compatibility
        from datetime import datetime as dt_class, date as date_class
        normalized_doctor_appts = []
        for appt in doctor_appts:
            appt.setdefault("appointment_time", appt.get("time"))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("notes", appt.get("medical_notes", ""))
            appt.setdefault("patient", {"username": appt.get("username", "Unknown"), "email": ""})
            
            # Handle appointment_date
            date_val = appt.get("date") or appt.get("appointment_date")
            if isinstance(date_val, str):
                try:
                    appt["appointment_date"] = dt_class.strptime(date_val, "%Y-%m-%d").date()
                except (ValueError, TypeError):
                    appt["appointment_date"] = date_class.today()
            elif isinstance(date_val, date_class):
                appt["appointment_date"] = date_val
            else:
                appt["appointment_date"] = date_class.today()
            
            if appt.get("appointment_date"):
                normalized_doctor_appts.append(appt)
        
        doctor_appts = normalized_doctor_appts
        
        # Calculate appointment statistics and separate into today/upcoming
        from datetime import date
        today = date.today()
        total_appointments = len(doctor_appts)
        pending_count = len([a for a in doctor_appts if a.get("status") == "pending"])
        confirmed_count = len([a for a in doctor_appts if a.get("status") == "confirmed"])
        completed_count = len([a for a in doctor_appts if a.get("status") == "completed"])
        
        # Separate today's appointments and upcoming appointments
        today_appointments = [a for a in doctor_appts if a.get("appointment_date") == today]
        upcoming_appointments = [a for a in doctor_appts if a.get("appointment_date") and a.get("appointment_date") > today]
        
        # Sort appointments by time (handle None values)
        today_appointments.sort(key=lambda x: (x.get("appointment_time") or "", x.get("id", "")))
        upcoming_appointments.sort(key=lambda x: (x.get("appointment_date") or date.today(), x.get("appointment_time") or "", x.get("id", "")))

        return render_template(
            "doctor.html",
            username=username,
            doctor=doctor_profile,
            appointments=doctor_appts,
            today_appointments=today_appointments,
            upcoming_appointments=upcoming_appointments,
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

    # Normalize appointment fields for template compatibility
    from datetime import datetime as dt_class, date as date_class
    normalized_appointments = []
    for appt in appointments:
        appt.setdefault("appointment_time", appt.get("time"))
        appt.setdefault("status", "pending")
        appt.setdefault("symptoms", appt.get("reason", ""))
        appt.setdefault("notes", appt.get("medical_notes", ""))
        appt.setdefault("doctor", {"name": appt.get("doctor_name", "Unknown"), "specialization": "General"})
        
        # Handle appointment_date carefully
        date_val = appt.get("date") or appt.get("appointment_date")
        if isinstance(date_val, str):
            try:
                appt["appointment_date"] = dt_class.strptime(date_val, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                appt["appointment_date"] = date_class.today()
        elif isinstance(date_val, date_class):
            appt["appointment_date"] = date_val
        else:
            appt["appointment_date"] = date_class.today()
        
        # Handle created_at (convert ISO string to datetime)
        created_at = appt.get("created_at")
        if isinstance(created_at, str):
            try:
                appt["created_at"] = dt_class.fromisoformat(created_at)
            except (ValueError, TypeError):
                appt["created_at"] = dt_class.utcnow()
        elif not isinstance(created_at, dt_class):
            appt["created_at"] = dt_class.utcnow()
        
        # Only include appointments with valid dates
        if appt.get("appointment_date"):
            normalized_appointments.append(appt)
    
    appointments = normalized_appointments

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
        data = request.get_json(silent=True) or request.form
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        doctor_name = (data.get("name") or "").strip()

        if not username or not password or not doctor_name:
            return {"success": False, "message": "Username, password, and name are required"}, 400

        existing_user = users_table.get_item(Key={"username": username}).get("Item")
        if existing_user:
            return {"success": False, "message": "Username already exists"}, 400

        doctor_id = str(uuid.uuid4())

        doctors_table.put_item(
            Item={
                "id": doctor_id,
                "name": doctor_name,
                "username": username,
                "specialization": data.get("specialization", "General"),
                "email": data.get("email", ""),
                "phone": data.get("phone", ""),
                "qualifications": data.get("qualifications", ""),
                "experience": int(data.get("experience", 0) or 0),
                "consultation_fee": to_decimal(data.get("consultation_fee", "0"), "0"),
                "available_days": data.get("available_days", ""),
                "available_time": data.get("available_time", ""),
                "is_available": True,
            }
        )

        users_table.put_item(
            Item={
                "username": username,
                "password_hash": generate_password_hash(password),
                "role": "doctor",
                "email": data.get("email", ""),
                "phone": data.get("phone", ""),
                "doctor_id": doctor_id,
            }
        )

        return {"success": True, "message": "Doctor added successfully", "doctor_id": doctor_id}
    except Exception as e:
        logger.error(f"Error adding doctor: {e}")
        return {"success": False, "message": str(e)}, 500

@app.route("/admin/delete-doctor/<doctor_id>", methods=["POST"])
def delete_doctor(doctor_id: str):
    """Delete a doctor (admin only)"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Access denied"}), 403
    
    try:
        # Check if doctor exists first
        doctor = doctors_table.get_item(Key={"id": doctor_id}).get("Item")
        if not doctor:
            return jsonify({"success": False, "message": "Doctor not found"}), 404
        
        # Delete from doctors table
        doctors_table.delete_item(Key={"id": doctor_id})
        logger.info(f"Doctor {doctor_id} ({doctor.get('name')}) deleted by admin {session['username']}")
        
        # Send notification
        send_notification(
            subject="Doctor Profile Removed",
            message=f"Doctor removed from system:\nName: {doctor.get('name')}\nID: {doctor_id}\nRemoved by: {session['username']}"
        )
        
        return jsonify({"success": True, "message": "Doctor removed successfully"})
    except ClientError as e:
        logger.error(f"Error deleting doctor {doctor_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500
    except Exception as e:
        logger.error(f"Unexpected error deleting doctor {doctor_id}: {e}")
        return jsonify({"success": False, "message": "An unexpected error occurred"}), 500

@app.route("/doctors")
def doctors():
    if "username" not in session:
        return redirect(url_for("login"))

    doctors_resp = doctors_table.scan()
    doctors_list = doctors_resp.get("Items", [])
    
    # Extract unique specializations
    specializations = list(set([d.get("specialization", "General") for d in doctors_list if d.get("specialization")]))
    specializations.sort()
    
    # Ensure defaults for template fields and build ratings wrapper
    doctors_with_ratings = []
    for d in doctors_list:
        d.setdefault("qualifications", "")
        d.setdefault("experience", 0)
        d.setdefault("available_days", "")
        d.setdefault("available_time", "")
        d.setdefault("phone", "")
        d.setdefault("consultation_fee", Decimal("0"))
        d.setdefault("is_available", True)
        doctors_with_ratings.append(
            {
                "doctor": d,
                "average_rating": 0,
                "total_reviews": 0,
            }
        )
    
    return render_template(
        "doctors.html",
        doctors=doctors_list,
        doctors_with_ratings=doctors_with_ratings,
        specializations=specializations,
    )

@app.route("/book/<doctor_id>", methods=["GET", "POST"], endpoint="book_appointment")
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
        date = request.form.get("appointment_date")
        time = request.form.get("appointment_time")
        reason = request.form.get("symptoms", "").strip()
        medical_notes = request.form.get("symptoms", "").strip()

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
        return redirect(url_for("dashboard"))

    from datetime import date as date_class
    
    # Generate available time slots (standard 30-minute intervals during typical working hours)
    available_slots = [
        "9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM",
        "11:00 AM", "11:30 AM", "2:00 PM", "2:30 PM",
        "3:00 PM", "3:30 PM", "4:00 PM", "4:30 PM"
    ]
    
    return render_template(
        "appointments.html", 
        doctor=doctor, 
        date=date_class,
        available_slots=available_slots,
        min_date=date_class.today()
    )


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


@app.route("/cancel-appointment/<appointment_id>", methods=["GET", "POST"])
def cancel_appointment(appointment_id: str):
    """Cancel an appointment"""
    if "username" not in session:
        return redirect(url_for("login"))

    try:
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            flash("Appointment not found", "danger")
            return redirect(url_for("dashboard"))

        username = session["username"]
        if appointment.get("username") != username:
            flash("You can only cancel your own appointments", "danger")
            return redirect(url_for("dashboard"))

        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "cancelled"},
        )

        send_notification(
            subject="Appointment Cancelled",
            message=f"Appointment {appointment_id} has been cancelled by user {username}",
        )

        flash("Appointment cancelled successfully", "success")
    except ClientError as exc:
        logger.error(f"Error cancelling appointment {appointment_id}: {exc}")
        flash("Error cancelling appointment", "danger")

    return redirect(url_for("dashboard"))


@app.route("/doctor/update-appointment/<appointment_id>", methods=["POST"])
def update_appointment_status(appointment_id: str):
    """Update appointment status (confirm, cancel, complete)"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        doctor_username = session["username"]
        
        # Get appointment details
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            logger.error(f"Appointment not found: {appointment_id}")
            return jsonify({"success": False, "message": "Appointment not found"}), 404

        # Verify this appointment is for this doctor
        if appointment.get("doctor_id") != doctor_username:
            logger.error(f"Doctor {doctor_username} not authorized for appointment {appointment_id}")
            return jsonify({"success": False, "message": "Unauthorized"}), 403

        # Get the new status from request
        status = request.form.get("status", "").strip()
        
        if status not in ["confirmed", "cancelled", "completed"]:
            logger.error(f"Invalid status: {status}")
            return jsonify({"success": False, "message": "Invalid status"}), 400

        # Update appointment status
        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
        )
        
        logger.info(f"Appointment {appointment_id} status updated to {status} by doctor {doctor_username}")

        # Get doctor info for notification
        doctor = doctors_table.get_item(Key={"id": doctor_username}).get("Item")
        doctor_name = doctor.get("name", "Doctor") if doctor else "Doctor"
        
        # Send notification
        message_map = {
            "confirmed": f"Your appointment has been confirmed by {doctor_name}",
            "cancelled": f"Your appointment has been cancelled by {doctor_name}",
            "completed": "Your appointment has been marked as completed"
        }
        
        send_notification(
            subject=f"Appointment {status.title()}",
            message=message_map.get(status, f"Appointment status updated to {status}"),
        )

        return jsonify({
            "success": True,
            "message": f"Appointment {status} successfully"
        })

    except ClientError as exc:
        logger.error(f"ClientError updating appointment {appointment_id}: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating appointment {appointment_id}: {exc}")
        return jsonify({"success": False, "message": "An error occurred"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)