import os
import uuid
import logging
from datetime import datetime
from functools import lru_cache
from decimal import Decimal, InvalidOperation

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ncFW7IxB9QdiiVyJAVwRNRHgl9GkqO0QipSLcbgT")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Context processor to make current_user available in templates
class CurrentUser:
    def __init__(self):
        self.is_authenticated = "username" in session
        self.username = session.get("username")
        self.user_type = session.get("role", "user")
        self.email = session.get("email", "")
        self.phone = session.get("phone", "")
        self.profile_picture = session.get("profile_picture", "")
        self.full_name = session.get("full_name", "")
        self.age = session.get("age", "")
        self.gender = session.get("gender", "")
    
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
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:455322615378:HealthcareAppServer")

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
    Enhanced symptom analysis engine with comprehensive medical knowledge
    Detects emergency conditions, suggests specializations, provides health tips, and calculates severity
    """
    symptoms_text_lower = symptoms_text.lower()

    # Expanded emergency indicators with more conditions
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
        "coughing blood": 4,
        "vomiting blood": 4,
        "sudden weakness": 3,
        "slurred speech": 4,
        "confusion": 3,
        "blue lips": 4,
        "severe pain": 3,
    }

    specialization_map = {
        "Cardiology": {
            "keywords": ["chest pain", "heart", "palpitation", "arrhythmia", "hypertension", "blood pressure", "cardiac", "angina", "irregular heartbeat", "shortness of breath", "cholesterol", "coronary", "cardiovascular"],
        },
        "Neurology": {
            "keywords": ["headache", "migraine", "dizziness", "stroke", "seizure", "tremor", "nerve", "neuropathy", "numbness", "paralysis", "vertigo", "brain", "memory loss", "confusion", "tingling"],
        },
        "Orthopedics": {
            "keywords": ["fracture", "bone", "joint", "arthritis", "back pain", "knee pain", "shoulder pain", "ankle", "sprain", "ligament", "muscle pain", "hip", "neck pain", "spine"],
        },
        "Gastroenterology": {
            "keywords": ["stomach", "abdominal", "nausea", "vomiting", "diarrhea", "constipation", "acid reflux", "heartburn", "liver", "digestive", "intestinal", "bloating", "gas", "ulcer", "ibs"],
        },
        "Pulmonology": {
            "keywords": ["cough", "asthma", "lung", "bronchitis", "pneumonia", "respiratory", "breathing", "wheezing", "shortness of breath", "tuberculosis", "copd", "chest congestion"],
        },
        "Dermatology": {
            "keywords": ["rash", "skin", "acne", "eczema", "psoriasis", "mole", "wart", "itching", "fungal", "allergy", "hives", "lesion", "blister", "sunburn"],
        },
        "Ophthalmology": {
            "keywords": ["eye", "vision", "blind", "blurred", "eye pain", "glaucoma", "cataract", "contact lens", "glasses", "double vision", "red eyes", "eye discharge"],
        },
        "ENT (Otolaryngology)": {
            "keywords": ["ear", "nose", "throat", "hearing", "tinnitus", "sinus", "sinusitis", "sore throat", "hoarse", "vertigo", "earache", "nasal", "congestion", "tonsils"],
        },
        "Pediatrics": {
            "keywords": ["baby", "child", "infant", "kid", "vaccination", "fever", "crying", "development", "growth", "newborn", "toddler", "teething"],
        },
        "Psychiatry": {
            "keywords": ["depression", "anxiety", "stress", "panic", "mental", "psychological", "emotional", "insomnia", "sleep", "mood", "bipolar", "ptsd", "trauma"],
        },
        "Endocrinology": {
            "keywords": ["diabetes", "thyroid", "hormone", "blood sugar", "insulin", "metabolic", "obesity", "weight gain", "weight loss", "fatigue", "growth"],
        },
        "Urology": {
            "keywords": ["urinary", "bladder", "kidney", "prostate", "urine", "frequent urination", "kidney stone", "uti", "incontinence"],
        },
        "Gynecology": {
            "keywords": ["menstrual", "period", "pregnancy", "pelvic", "ovarian", "uterine", "vaginal", "reproductive", "menopause", "pms"],
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
    
    # Generate health tips based on symptoms
    health_tips = generate_health_tips(symptoms_text_lower, is_emergency)

    return {
        "response": response_message,
        "is_emergency": is_emergency,
        "specializations": formatted_specializations,
        "severity_score": severity_score,
        "health_tips": health_tips,
    }


def handle_health_faq(query: str) -> str:
    """Handle frequently asked health questions"""
    faqs = {
        "book appointment": "To book an appointment, navigate to the 'Doctors' section, select a specialist, and choose your preferred date and time. You can also view all available doctors and their specializations.",
        "cancel appointment": "To cancel an appointment, go to your dashboard, find the appointment in your list, and click the 'Cancel' button. Please note our 24-hour cancellation policy.",
        "medical record": "You can upload and view your medical records in the 'Medical Records' section. Supported formats include PDF, JPG, and PNG. Your records are securely stored and can be shared with your doctor.",
        "doctor availability": "Doctor availability varies by specialist. You can check each doctor's available days and times on their profile page when booking an appointment.",
        "payment": "We accept credit cards, debit cards, and UPI for appointment payments. A consultation fee plus a small processing fee applies. Payment is required when booking.",
        "profile update": "To update your profile, click on the 'Account' section in your dashboard. You can update your email, phone number, and other personal information.",
        "emergency": "For medical emergencies, please call 911 (US) or your local emergency number immediately. This chat is for non-emergency consultations only.",
        "prescription": "Prescriptions are provided by your doctor after your consultation. You can view and download them from your medical records section.",
        "test result": "Test results will be uploaded by your doctor or lab to your medical records. You'll receive a notification when new results are available.",
        "follow up": "For follow-up appointments, you can book another session with the same doctor or a specialist recommended by your physician."
    }
    
    for key, response in faqs.items():
        if key in query or any(word in query for word in key.split()):
            return f"<strong>Answer:</strong><br><br>{response}<br><br><em>If you need more specific help, please provide more details or contact our support team.</em>"
    
    return None


def handle_appointment_query(query: str) -> str:
    """Handle appointment-related queries with helpful guidance"""
    appointment_keywords = {
        "how to book": "<strong>Booking an Appointment:</strong><br>1. Click on 'Doctors' in the navigation menu<br>2. Browse or search for a specialist<br>3. Click 'Book Appointment' on the doctor's card<br>4. Select your preferred date and time<br>5. Fill in your symptoms and payment details<br>6. Confirm your booking<br><br>You'll receive a confirmation and can track your appointment in your dashboard.",
        "reschedule": "<strong>Rescheduling Appointments:</strong><br>Currently, to reschedule an appointment, you'll need to cancel your existing appointment and book a new one. We recommend doing this at least 24 hours in advance.<br><br>To cancel: Dashboard → Find appointment → Cancel button",
        "what bring": "<strong>What to Bring to Your Appointment:</strong><br>• Valid ID<br>• Insurance information (if applicable)<br>• List of current medications<br>• Previous medical records<br>• Any test results related to your condition<br>• List of questions for your doctor",
        "prepare": "<strong>Preparing for Your Appointment:</strong><br>• Write down your symptoms and when they started<br>• Note any medications you're taking<br>• List any allergies<br>• Prepare questions for your doctor<br>• Arrive 10-15 minutes early<br>• Bring relevant medical history"
    }
    
    for key, response in appointment_keywords.items():
        if key in query:
            return response
    
    return None


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

    response += "<strong>What you can do:</strong><br>"
    response += "• Keep a symptom diary noting when symptoms occur<br>"
    response += "• Stay hydrated and get adequate rest<br>"
    response += "• Avoid self-medication without consulting a doctor<br>"
    response += "• Book an appointment through our platform for proper diagnosis<br><br>"
    
    response += (
        "<em>Note: This is an AI-powered preliminary assessment only and does not replace "
        "professional medical advice. Always consult with a qualified healthcare provider for proper diagnosis and treatment.</em>"
    )
    return response


def generate_health_tips(symptoms: str, is_emergency: bool) -> list:
    """Generate relevant health tips based on symptoms"""
    if is_emergency:
        return ["Seek immediate medical attention", "Call emergency services (911)", "Do not delay treatment"]
    
    tips = []
    
    # General tips
    tips.append("Monitor your symptoms and note any changes")
    tips.append("Stay well-hydrated by drinking plenty of water")
    
    # Specific symptom-based tips
    if any(word in symptoms for word in ["headache", "migraine"]):
        tips.extend(["Rest in a quiet, dark room", "Apply cold compress to forehead", "Avoid bright screens"])
    
    if any(word in symptoms for word in ["fever", "temperature"]):
        tips.extend(["Get plenty of rest", "Use over-the-counter fever reducers if appropriate", "Monitor temperature regularly"])
    
    if any(word in symptoms for word in ["cough", "cold", "congestion"]):
        tips.extend(["Use a humidifier", "Drink warm fluids", "Get adequate rest"])
    
    if any(word in symptoms for word in ["stomach", "nausea", "digestive"]):
        tips.extend(["Eat bland, easy-to-digest foods", "Avoid spicy or fatty foods", "Try small, frequent meals"])
    
    if any(word in symptoms for word in ["pain", "ache"]):
        tips.extend(["Apply ice or heat as appropriate", "Avoid strenuous activity", "Maintain good posture"])
    
    if any(word in symptoms for word in ["stress", "anxiety", "sleep"]):
        tips.extend(["Practice relaxation techniques", "Maintain a regular sleep schedule", "Limit caffeine intake"])
    
    # Add general wellness tip
    tips.append("Consult a healthcare professional if symptoms persist or worsen")
    
    # Return unique tips (remove duplicates while preserving order)
    seen = set()
    unique_tips = []
    for tip in tips:
        if tip not in seen:
            seen.add(tip)
            unique_tips.append(tip)
    
    return unique_tips[:6]  # Limit to 6 most relevant tips


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
        # Store relative path from instance directory for portability
        relative_path = os.path.join("uploads", username, safe_name)
        
        medical_records_table.put_item(
            Item={
                "id": record_id,
                "record_id": record_id,
                "patient_username": username,  # Use patient_username for consistency
                "username": username,  # Keep for backwards compatibility
                "filename": safe_name,
                "original_filename": filename,
                "file_path": relative_path,  # Add file path for downloads
                "description": description,
                "file_type": file_type,
                "file_size": file_size,
                "type": "document",  # Mark as document type
                "upload_date": datetime.utcnow().isoformat(),
                "created_at": datetime.utcnow().isoformat(),  # Add created_at for sorting
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
    """Enhanced AI-powered health assistant with symptom analysis, health tips, and FAQs"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401

    role = session.get("role", "user")
    if role not in {"user", "patient"}:
        return jsonify({"success": False, "message": "This feature is for patients only"}), 403

    data = request.get_json(silent=True) or {}
    message = str(data.get("message", data.get("symptoms", ""))).strip()
    if not message:
        return jsonify({"success": False, "message": "Please enter your message or symptoms"}), 400

    message_lower = message.lower()
    
    # Handle common health questions and FAQs
    faq_response = handle_health_faq(message_lower)
    if faq_response:
        return jsonify({
            "success": True,
            "response": faq_response,
            "is_emergency": False,
            "message_type": "faq"
        })
    
    # Handle appointment-related queries
    appointment_response = handle_appointment_query(message_lower)
    if appointment_response:
        return jsonify({
            "success": True,
            "response": appointment_response,
            "is_emergency": False,
            "message_type": "appointment_help"
        })
    
    # Perform symptom analysis
    analysis = analyze_symptoms(message)

    return jsonify({
        "success": True,
        "response": analysis["response"],
        "is_emergency": analysis["is_emergency"],
        "specializations": analysis["specializations"],
        "severity_score": analysis["severity_score"],
        "health_tips": analysis.get("health_tips", []),
        "message_type": "symptom_analysis"
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
                session["email"] = item.get("email", "")
                session["phone"] = item.get("phone", "")
                session["profile_picture"] = item.get("profile_picture", "")
                # Store additional profile data for form auto-fill
                session["full_name"] = item.get("name", "")
                session["age"] = item.get("age", "")
                session["gender"] = item.get("gender", "")
                
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
        appts_resp = appointments_table.scan()
        
        doctors_items = doctors_resp.get("Items", [])
        users_items = users_resp.get("Items", [])
        appts_items = appts_resp.get("Items", [])
        
        total_doctors = len(doctors_items)
        total_appointments = len(appts_items)
        pending_appointments = sum(
            1
            for appt in appts_items
            if (appt.get("status") or "pending").lower() == "pending"
        )
        total_patients = sum(
            1
            for user in users_items
            if (user.get("role") or user.get("user_type") or "user").lower() in {"user", "patient"}
        )
        
        # Get all appointments and normalize them
        from datetime import datetime as dt_class, date as date_class
        all_appointments = []
        for appt in appts_resp.get("Items", []):
            appt.setdefault("appointment_time", appt.get("time"))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("patient", {"username": appt.get("username", "Unknown"), "email": ""})
            appt.setdefault("doctor", {"name": appt.get("doctor_id", "Unknown")})
            
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
                all_appointments.append(appt)
        
        # Separate upcoming appointments (future dates)
        from datetime import date
        today = date.today()
        upcoming_appointments = [a for a in all_appointments if a.get("appointment_date") and a.get("appointment_date") >= today]
        upcoming_appointments.sort(key=lambda x: (x.get("appointment_date") or date.today(), x.get("appointment_time") or ""))
        
        return render_template(
            "admin.html",
            username=username,
            doctors=doctors_items,
            users=users_items,
            recent_appointments=upcoming_appointments[:10],
            upcoming_appointments=upcoming_appointments,
            total_patients=total_patients,
            total_doctors=total_doctors,
            total_appointments=total_appointments,
            pending_appointments=pending_appointments,
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
        # Filter appointments for this doctor - check both by doctor ID (UUID) and by doctor username
        doctor_appts = [a for a in appts_resp.get("Items", []) if a.get("doctor_id") == doctor_id or a.get("doctor_id") == username]
        
        # Normalize doctor appointments for template compatibility
        from datetime import datetime as dt_class, date as date_class
        normalized_doctor_appts = []
        for appt in doctor_appts:
            appt.setdefault("appointment_time", appt.get("time"))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("notes", appt.get("medical_notes", ""))
            
            # Fetch full patient details
            patient_username = appt.get("username", "Unknown")
            patient_details = {"username": patient_username, "email": "", "phone": "", "age": "", "gender": ""}
            if patient_username != "Unknown":
                patient_user = get_user(patient_username)
                if patient_user:
                    patient_details = {
                        "username": patient_username,
                        "email": patient_user.get("email", ""),
                        "phone": patient_user.get("phone", ""),
                        "age": patient_user.get("age", ""),
                        "gender": patient_user.get("gender", ""),
                        "name": patient_user.get("name", patient_username)
                    }
            appt.setdefault("patient", patient_details)
            
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
        
        # Get all pending appointments (not just today's)
        pending_appointments = [a for a in doctor_appts if a.get("status") == "pending"]
        
        # Sort appointments by time (handle None values)
        today_appointments.sort(key=lambda x: (x.get("appointment_time") or "", x.get("id", "")))
        upcoming_appointments.sort(key=lambda x: (x.get("appointment_date") or date.today(), x.get("appointment_time") or "", x.get("id", "")))
        pending_appointments.sort(key=lambda x: (x.get("appointment_date") or date.today(), x.get("appointment_time") or "", x.get("id", "")))

        # Get patient data for patient records view
        patient_usernames = set(a.get("username") for a in doctor_appts if a.get("username"))
        patient_data = []
        for patient_username in patient_usernames:
            patient_user = get_user(patient_username)
            if not patient_user:
                continue
            
            # Get appointments for this patient with this doctor
            patient_appts = [a for a in doctor_appts if a.get("username") == patient_username]
            
            # Get medical records for this patient
            try:
                records_resp = medical_records_table.scan(
                    FilterExpression="patient_username = :username",
                    ExpressionAttributeValues={":username": patient_username}
                )
                medical_records = records_resp.get("Items", [])
            except:
                medical_records = []
            
            # Find last appointment date
            last_appt = None
            if patient_appts:
                from datetime import datetime as dt_class
                dates = []
                for appt in patient_appts:
                    date_val = appt.get("date") or appt.get("appointment_date")
                    if date_val:
                        try:
                            if isinstance(date_val, str):
                                dates.append(dt_class.strptime(date_val, "%Y-%m-%d").date())
                            else:
                                dates.append(date_val)
                        except (ValueError, TypeError):
                            pass
                if dates:
                    last_appt = max(dates)
            
            patient_data.append({
                "patient": {
                    "username": patient_username,
                    "email": patient_user.get("email", ""),
                    "phone": patient_user.get("phone", ""),
                    "id": patient_username
                },
                "total_appointments": len(patient_appts),
                "last_appointment": last_appt,
                "medical_records_count": len(medical_records),
                "medical_records": medical_records
            })
        
        # Sort by total appointments (descending)
        patient_data.sort(key=lambda x: x["total_appointments"], reverse=True)

        return render_template(
            "doctor.html",
            username=username,
            doctor=doctor_profile,
            appointments=doctor_appts,
            today_appointments=today_appointments,
            upcoming_appointments=upcoming_appointments,
            pending_appointments=pending_appointments,
            patient_data=patient_data,
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
    
    # Get assigned doctor if any
    assigned_doctor = None
    if appointments:
        # Get the doctor from the most recent appointment
        latest_appt = max(appointments, key=lambda x: x.get('created_at', dt_class.min))
        doctor_id = latest_appt.get('doctor_id')
        if doctor_id:
            try:
                doctor_resp = doctors_table.get_item(Key={"doctor_id": doctor_id})
                assigned_doctor = doctor_resp.get('Item')
            except Exception as e:
                logger.error(f"Error getting doctor: {e}")
    
    # Calculate task completion (appointments as tasks)
    total_tasks = len(appointments)
    completed_tasks = len([a for a in appointments if a.get('status') == 'completed'])

    return render_template("user_new.html", 
                         username=username, 
                         appointments=appointments, 
                         feedback_dict={},
                         assigned_doctor=assigned_doctor,
                         total_tasks=total_tasks,
                         completed_tasks=completed_tasks)


# Add route aliases for template compatibility
app.add_url_rule("/user-dashboard", "user_dashboard", dashboard)
app.add_url_rule("/admin-dashboard", "admin_dashboard", dashboard)
app.add_url_rule("/doctor-dashboard", "doctor_dashboard", dashboard)

@app.route("/doctor-patients", endpoint="doctor_patients")
def doctor_patients():
    """Redirect to doctor dashboard - patients view is now integrated"""
    if "username" not in session or session.get("role") != "doctor":
        flash("Access denied", "danger")
        return redirect(url_for("login"))
    
    # Redirect to dashboard where patient records view is integrated
    return redirect(url_for("doctor_dashboard"))

@app.route("/doctor/patient-records/<patient_id>", endpoint="doctor_view_patient_records")
def doctor_view_patient_records(patient_id: str):
    """View medical records for a specific patient"""
    if "username" not in session or session.get("role") != "doctor":
        flash("Access denied", "danger")
        return redirect(url_for("login"))
    
    try:
        doctor_username = session["username"]
        logger.info(f"Doctor {doctor_username} viewing records for patient {patient_id}")
        
        # Get patient info
        patient_user = get_user(patient_id)
        if not patient_user:
            flash("Patient not found", "danger")
            return redirect(url_for("doctor_patients"))
        
        # Verify doctor has appointments with this patient
        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) 
                       if (a.get("doctor_id") == doctor_username or a.get("doctor_id") == session.get("doctor_id"))
                       and a.get("username") == patient_id]
        
        if not doctor_appts:
            flash("You don't have access to this patient's records", "danger")
            return redirect(url_for("doctor_patients"))
        
        # Get patient's medical records - query by patient_username or username for backwards compatibility
        records_resp = medical_records_table.scan()
        medical_records = [r for r in records_resp.get("Items", []) 
                          if r.get("patient_username") == patient_id or r.get("username") == patient_id]
        
        # Normalize medical records for template compatibility
        from datetime import datetime as dt_class, date as date_class
        normalized_records = []
        for record in medical_records:
            # Ensure all required fields exist with defaults
            record.setdefault("original_filename", record.get("filename", "Document"))
            record.setdefault("description", "")
            record.setdefault("file_type", record.get("file_type", "unknown"))
            record.setdefault("file_size", 0)
            
            # Handle date/upload_date field
            date_str = record.get("upload_date") or record.get("created_at") or record.get("date")
            if date_str:
                try:
                    if isinstance(date_str, str):
                        record["upload_date"] = dt_class.fromisoformat(date_str.replace("Z", "+00:00"))
                    else:
                        record["upload_date"] = date_str
                except (ValueError, TypeError, AttributeError):
                    record["upload_date"] = dt_class.utcnow()
            else:
                record["upload_date"] = dt_class.utcnow()
            
            normalized_records.append(record)
        
        medical_records = normalized_records
        
        # Sort records by date (newest first)
        def get_record_date(record):
            try:
                return record.get("upload_date", dt_class.min)
            except:
                return dt_class.min
        
        medical_records.sort(key=get_record_date, reverse=True)
        
        logger.info(f"Found {len(medical_records)} medical records for patient {patient_id}")
        
        # Normalize appointments for template compatibility
        normalized_appts = []
        for appt in doctor_appts:
            # Normalize field names
            appt.setdefault("appointment_time", appt.get("time"))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("notes", appt.get("medical_notes", ""))
            
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
            
            normalized_appts.append(appt)
        
        return render_template(
            "patient_records.html",
            patient=patient_user,
            medical_records=medical_records,
            appointments=normalized_appts,
            username=doctor_username
        )
        
    except Exception as exc:
        logger.error(f"Error loading patient records for {patient_id}: {exc}", exc_info=True)
        flash("Error loading patient records", "danger")
        return redirect(url_for("doctor_patients"))

@app.route("/doctor/download-record/<record_id>", endpoint="doctor_download_record")
def doctor_download_record(record_id: str):
    """Download a medical record from local storage"""
    if "username" not in session or session.get("role") != "doctor":
        flash("Access denied", "danger")
        return redirect(url_for("login"))
    
    try:
        doctor_username = session["username"]
        
        # Get the record - try both 'id' and 'record_id' as key
        record = None
        try:
            record = medical_records_table.get_item(Key={"id": record_id}).get("Item")
        except:
            try:
                record = medical_records_table.get_item(Key={"record_id": record_id}).get("Item")
            except Exception as e:
                logger.error(f"Error fetching record {record_id}: {e}")
        
        if not record:
            flash("Medical record not found", "danger")
            return redirect(url_for("doctor_dashboard"))
        
        # Verify doctor has access to this patient's records
        patient_username = record.get("patient_username") or record.get("username")
        if not patient_username:
            flash("Invalid record", "danger")
            return redirect(url_for("doctor_dashboard"))
        
        # Check if doctor has appointments with this patient
        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) 
                       if (a.get("doctor_id") == doctor_username or a.get("doctor_id") == session.get("doctor_id"))
                       and a.get("username") == patient_username]
        
        if not doctor_appts:
            flash("You don't have access to this patient's records", "danger")
            return redirect(url_for("doctor_dashboard"))
        
        # Get file path from record - try multiple sources
        file_path = record.get("file_path")
        
        # If file_path doesn't exist (old records), reconstruct from filename and username
        if not file_path:
            filename_in_db = record.get("filename")
            if not filename_in_db:
                flash("Cannot determine file location", "danger")
                return redirect(url_for("doctor_dashboard"))
            file_path = os.path.join("uploads", patient_username, filename_in_db)
        
        # Construct full path to file
        if file_path.startswith('/'):
            file_path = file_path[1:]
        
        if not os.path.isabs(file_path):
            full_path = os.path.join(app.instance_path, file_path)
        else:
            full_path = file_path
        
        if not os.path.exists(full_path):
            logger.error(f"File not found at path: {full_path}")
            flash("File not found in storage", "danger")
            return redirect(url_for("doctor_dashboard"))
        
        # Get original filename
        filename = record.get("original_filename") or record.get("filename", "medical_record")
        
        # Get content type
        content_type = record.get("content_type")
        if not content_type:
            import mimetypes
            content_type, _ = mimetypes.guess_type(filename)
            if not content_type:
                content_type = 'application/octet-stream'
        
        directory = os.path.dirname(full_path)
        file_name = os.path.basename(full_path)
        
        return send_from_directory(
            directory,
            file_name,
            mimetype=content_type,
            as_attachment=True,
            download_name=filename
        )
            
    except Exception as exc:
        logger.error(f"Error in doctor_download_record: {exc}", exc_info=True)
        flash("Error downloading medical record", "danger")
        return redirect(url_for("doctor_dashboard"))

@app.route("/api/doctor/patient/<patient_id>/details")
def api_get_patient_details(patient_id: str):
    """API endpoint to get patient details and appointments for expandable view"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        doctor_username = session["username"]
        
        # Get patient info
        patient_user = get_user(patient_id)
        if not patient_user:
            return jsonify({"error": "Patient not found"}), 404
        
        # Get doctor's appointments with this patient
        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) 
                       if (a.get("doctor_id") == doctor_username or a.get("doctor_id") == session.get("doctor_id"))
                       and a.get("username") == patient_id]
        
        if not doctor_appts:
            return jsonify({"error": "No appointments found with this patient"}), 403
        
        # Normalize appointments for JSON response
        from datetime import datetime as dt_class, date as date_class
        normalized_appts = []
        for appt in doctor_appts:
            # Normalize field names
            appt.setdefault("appointment_time", appt.get("time"))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("notes", appt.get("medical_notes", ""))
            
            # Handle appointment_date
            date_val = appt.get("date") or appt.get("appointment_date")
            if isinstance(date_val, str):
                try:
                    appt["appointment_date"] = dt_class.strptime(date_val, "%Y-%m-%d").strftime("%b %d, %Y")
                except (ValueError, TypeError):
                    appt["appointment_date"] = date_class.today().strftime("%b %d, %Y")
            elif isinstance(date_val, date_class):
                appt["appointment_date"] = date_val.strftime("%b %d, %Y")
            else:
                appt["appointment_date"] = date_class.today().strftime("%b %d, %Y")
            
            normalized_appts.append({
                "id": appt.get("id", ""),
                "appointment_date": appt["appointment_date"],
                "appointment_time": appt.get("appointment_time", ""),
                "symptoms": appt.get("symptoms", ""),
                "status": appt.get("status", "pending"),
                "notes": appt.get("notes", "")
            })
        
        # Sort by date (newest first)
        normalized_appts.reverse()
        
        # Get medical records for this patient
        try:
            records_resp = medical_records_table.scan(
                FilterExpression="patient_username = :username",
                ExpressionAttributeValues={":username": patient_id}
            )
            medical_records = records_resp.get("Items", [])
        except:
            medical_records = []
        
        # Normalize medical records for JSON response
        normalized_records = []
        for record in medical_records:
            upload_date = record.get("upload_date") or record.get("created_at") or record.get("date")
            if upload_date:
                try:
                    if isinstance(upload_date, str):
                        upload_date_obj = dt_class.fromisoformat(upload_date.replace("Z", "+00:00"))
                        upload_date_formatted = upload_date_obj.strftime("%b %d, %Y")
                    else:
                        upload_date_formatted = upload_date.strftime("%b %d, %Y") if hasattr(upload_date, 'strftime') else str(upload_date)
                except:
                    upload_date_formatted = "N/A"
            else:
                upload_date_formatted = "N/A"
            
            normalized_records.append({
                "id": record.get("id") or record.get("record_id", ""),
                "filename": record.get("original_filename") or record.get("filename", "Document"),
                "description": record.get("description", ""),
                "file_type": record.get("file_type", "unknown"),
                "file_size": record.get("file_size", 0),
                "upload_date": upload_date_formatted
            })
        
        # Sort records by upload date (newest first)
        normalized_records.reverse()
        
        # Format patient data for JSON
        patient_data = {
            "username": patient_user.get("username", ""),
            "email": patient_user.get("email", ""),
            "phone": patient_user.get("phone", ""),
            "date_of_birth": patient_user.get("date_of_birth", ""),
            "address": patient_user.get("address", "")
        }
        
        return jsonify({
            "patient": patient_data,
            "appointments": normalized_appts,
            "medical_records": normalized_records
        })
        
    except Exception as exc:
        logger.error(f"Error fetching patient details API: {exc}", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    if "username" not in session or session.get("role") != "doctor":
        return "Access denied", 403
    
    try:
        doctor_username = session["username"]
        
        # Get the record - try both 'id' and 'record_id' as key
        record = None
        try:
            record = medical_records_table.get_item(Key={"record_id": record_id}).get("Item")
        except:
            # Fallback to 'id' if 'record_id' doesn't work
            try:
                record = medical_records_table.get_item(Key={"id": record_id}).get("Item")
            except:
                pass
        
        if not record:
            # If get_item fails, scan for the record
            records_resp = medical_records_table.scan()
            for r in records_resp.get("Items", []):
                if r.get("id") == record_id or r.get("record_id") == record_id:
                    record = r
                    break
        
        if not record:
            logger.error(f"Record not found: {record_id}")
            return "Record not found", 404
        
        patient_id = record.get("patient_username") or record.get("username")
        
        # Verify doctor has appointments with this patient
        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) 
                       if (a.get("doctor_id") == doctor_username or a.get("doctor_id") == session.get("doctor_id"))
                       and a.get("username") == patient_id]
        
        if not doctor_appts:
            return "Access denied - no appointments with this patient", 403
        
        # Get filename from record
        filename = record.get("filename")
        if not filename:
            logger.error(f"No filename in record {record_id}")
            return "File information missing", 404
        
        # Get user details to check for numeric ID
        patient_user = get_user(patient_id)
        patient_numeric_id = patient_user.get("id") if patient_user else None
        
        # Construct file path - try multiple possible locations (username, numeric ID, etc.)
        possible_paths = [
            os.path.join(app.instance_path, "uploads", patient_id, filename),
            os.path.join(app.instance_path, "uploads", str(patient_id), filename),
        ]
        
        # Also try numeric user ID if available
        if patient_numeric_id:
            possible_paths.extend([
                os.path.join(app.instance_path, "uploads", str(patient_numeric_id), filename),
                os.path.join(app.instance_path, "uploads", patient_numeric_id, filename),
            ])
        
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        
        # If still not found, scan all subdirectories in uploads folder for the file
        if not file_path:
            uploads_dir = os.path.join(app.instance_path, "uploads")
            if os.path.exists(uploads_dir):
                for subdir in os.listdir(uploads_dir):
                    subdir_path = os.path.join(uploads_dir, subdir)
                    if os.path.isdir(subdir_path):
                        potential_file = os.path.join(subdir_path, filename)
                        if os.path.exists(potential_file):
                            file_path = potential_file
                            logger.info(f"Found file in subdirectory: {subdir}")
                            break
        
        if not file_path:
            logger.error(f"File not found in any location. Tried: {possible_paths}")
            logger.error(f"Record data: filename={filename}, patient_id={patient_id}, patient_numeric_id={patient_numeric_id}")
            logger.error(f"Instance path: {app.instance_path}")
            # List what files actually exist
            upload_dir = os.path.join(app.instance_path, "uploads", patient_id)
            logger.error(f"Checking directory: {upload_dir}")
            if os.path.exists(upload_dir):
                try:
                    files = os.listdir(upload_dir)
                    logger.error(f"Files in {upload_dir}: {files}")
                except Exception as e:
                    logger.error(f"Error listing directory: {e}")
            else:
                logger.error(f"Upload directory does not exist: {upload_dir}")
                # Check parent directory
                parent_dir = os.path.join(app.instance_path, "uploads")
                if os.path.exists(parent_dir):
                    try:
                        subdirs = os.listdir(parent_dir)
                        logger.error(f"Subdirectories in uploads: {subdirs}")
                    except Exception as e:
                        logger.error(f"Error listing parent directory: {e}")
            return f"File not found. Expected: {filename}", 404
        
        logger.info(f"Doctor {doctor_username} downloading record {record_id} for patient {patient_id} from {file_path}")
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=record.get("original_filename", "document")
        )
        
    except Exception as exc:
        logger.error(f"Error downloading record {record_id}: {exc}", exc_info=True)
        return "Error downloading file", 500

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
    
    # Get search and filter parameters
    search_query = request.args.get("search", "").strip().lower()
    specialization_filter = request.args.get("specialization", "all").strip()
    
    # Filter doctors based on search and specialization
    filtered_doctors = []
    for d in doctors_list:
        # Skip if search query doesn't match doctor name
        if search_query and search_query not in d.get("name", "").lower():
            continue
        
        # Skip if specialization filter doesn't match
        if specialization_filter != "all" and d.get("specialization", "") != specialization_filter:
            continue
        
        filtered_doctors.append(d)
    
    # Extract unique specializations from all doctors (for filter dropdown)
    specializations = list(set([d.get("specialization", "General") for d in doctors_list if d.get("specialization")]))
    specializations.sort()
    
    # Ensure defaults for template fields and build ratings wrapper
    doctors_with_ratings = []
    seen_ids = set()  # Track unique doctor IDs to prevent duplicates
    seen_names = set()  # Track unique doctor names to prevent duplicates
    
    for d in filtered_doctors:
        doctor_id = d.get("id")
        doctor_name = d.get("name", "").lower()
        
        # Skip if we've already added this doctor (by ID or name)
        if doctor_id and doctor_id in seen_ids:
            continue
        if doctor_name and doctor_name in seen_names:
            continue
        
        # Skip entries without proper ID or name
        if not doctor_id or not doctor_name:
            continue
            
        seen_ids.add(doctor_id)
        seen_names.add(doctor_name)
        
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
        doctors=filtered_doctors,
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
        
        # Validate required fields
        if not date:
            flash("Appointment date is required", "danger")
            return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        if not time:
            flash("Appointment time is required", "danger")
            return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        if not reason:
            flash("Symptoms/reason for visit is required", "danger")
            return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        # Get payment information
        payment_method = request.form.get("payment_method", "")
        card_number = request.form.get("card_number", "")
        card_holder = request.form.get("card_holder", "")
        upi_id = request.form.get("upi_id", "")
        
        # Validate payment method is selected
        if not payment_method:
            flash("Payment method is required", "danger")
            return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        # Validate payment details based on method
        if payment_method in ["credit_card", "debit_card"]:
            if not card_number or not card_holder:
                flash("Card number and cardholder name are required", "danger")
                return redirect(url_for("book_appointment", doctor_id=doctor_id))
            
            expiry_date = request.form.get("expiry_date", "")
            cvv = request.form.get("cvv", "")
            
            if not expiry_date or not cvv:
                flash("Expiry date and CVV are required", "danger")
                return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        elif payment_method == "upi":
            if not upi_id:
                flash("UPI ID is required", "danger")
                return redirect(url_for("book_appointment", doctor_id=doctor_id))
        
        # Mask card number for security (only last 4 digits)
        masked_card_number = ""
        if card_number:
            card_number_clean = card_number.replace(" ", "")
            masked_card_number = "**** **** **** " + card_number_clean[-4:] if len(card_number_clean) >= 4 else card_number
        
        # Calculate total amount (consultation fee + processing fee)
        consultation_fee = float(doctor.get("consultation_fee", 0))
        processing_fee = 2.0
        total_amount = consultation_fee + processing_fee
        
        # Get doctor's username - use doctor's name as fallback since username might not be in doctors table
        doctor_username = doctor.get("username") or doctor.get("name")
        
        # Also store the doctor's UUID for better querying
        doctor_uuid = doctor_id

        appointments_table.put_item(
            Item={
                "id": appointment_id,
                "doctor_id": doctor_uuid,  # Store doctor's UUID for dashboard filtering
                "doctor_username": doctor_username,  # Also store username for reference
                "doctor_name": doctor.get("name"),
                "username": username,
                "date": date,
                "time": time,
                "reason": reason,
                "medical_notes": medical_notes,
                "payment_method": payment_method,
                "card_number": masked_card_number,
                "card_holder": card_holder,
                "upi_id": upi_id,
                "consultation_fee": to_decimal(consultation_fee),
                "processing_fee": to_decimal(processing_fee),
                "total_amount": to_decimal(total_amount),
                "payment_status": "completed",  # In a real app, this would be "pending" until payment is processed
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        # Save medical record if notes provided
        if medical_notes:
            save_medical_record(
                username=username,
                doctor_id=doctor_uuid,  # Use doctor's UUID
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


@app.route("/api/doctor-availability/<doctor_id>")
def get_doctor_availability(doctor_id: str):
    """Get doctor's available dates and times based on their schedule"""
    try:
        doctor = doctors_table.get_item(Key={"id": doctor_id}).get("Item")
        if not doctor:
            return jsonify({"error": "Doctor not found"}), 404
        
        available_days_str = doctor.get("available_days", "")
        available_time_str = doctor.get("available_time", "")
        
        # Parse available days (format: "Monday, Tuesday, Wednesday")
        available_days = []
        if available_days_str:
            available_days = [d.strip().lower() for d in available_days_str.split(",")]
        
        # Parse available time range (format: "09:00-17:00")
        start_time = None
        end_time = None
        if available_time_str and "-" in available_time_str:
            time_parts = available_time_str.split("-")
            if len(time_parts) == 2:
                start_time = time_parts[0].strip()
                end_time = time_parts[1].strip()
        
        return jsonify({
            "available_days": available_days,
            "start_time": start_time,
            "end_time": end_time,
            "available_days_str": available_days_str,
            "available_time_str": available_time_str
        })
    
    except Exception as e:
        logger.error(f"Error fetching doctor availability: {e}")
        return jsonify({"error": "Failed to fetch availability"}), 500


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

    # Redirect to dashboard which shows appointments
    return redirect(url_for("dashboard"))


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
        return jsonify({"success": False, "message": "Unauthorized - Please login"}), 401

    try:
        doctor_username = session["username"]
        logger.info(f"Doctor {doctor_username} attempting to update appointment {appointment_id}")
        
        # Get the logged-in user's doctor_id
        user_item = get_user(doctor_username)
        if not user_item:
            logger.error(f"User not found: {doctor_username}")
            return jsonify({"success": False, "message": "User not found"}), 404
            
        logged_in_doctor_id = user_item.get("doctor_id")
        logger.info(f"Logged-in doctor - username: {doctor_username}, doctor_id: {logged_in_doctor_id}")
        
        # Get appointment details
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            logger.error(f"Appointment not found: {appointment_id}")
            return jsonify({"success": False, "message": "Appointment not found"}), 404

        appointment_doctor_id = appointment.get("doctor_id")
        appointment_doctor_username = appointment.get("doctor_username")
        logger.info(f"Appointment - doctor_id: {appointment_doctor_id}, doctor_username: {appointment_doctor_username}")
        
        # Verify this appointment is for this doctor (check both UUID and username)
        is_authorized = False
        
        # Check if appointment doctor_id matches logged-in doctor's doctor_id (UUID match)
        if logged_in_doctor_id and appointment_doctor_id == logged_in_doctor_id:
            is_authorized = True
            logger.info("Authorization: UUID match")
        # Check if appointment doctor_id or doctor_username matches logged-in username
        elif appointment_doctor_id == doctor_username or appointment_doctor_username == doctor_username:
            is_authorized = True
            logger.info("Authorization: Username match")
        
        if not is_authorized:
            logger.error(f"Doctor {doctor_username} (ID: {logged_in_doctor_id}) not authorized for appointment {appointment_id}")
            logger.error(f"Appointment doctor_id: {appointment_doctor_id}, doctor_username: {appointment_doctor_username}")
            return jsonify({"success": False, "message": "Unauthorized - This appointment is not assigned to you"}), 403

        # Get the new status from request
        status = request.form.get("status", "").strip()
        notes = request.form.get("notes", "").strip()
        
        if status not in ["confirmed", "cancelled", "completed"]:
            logger.error(f"Invalid status: {status}")
            return jsonify({"success": False, "message": "Invalid status"}), 400
        
        # Validate that notes/prescription is provided when completing appointment
        if status == "completed" and not notes:
            logger.error(f"Attempted to complete appointment {appointment_id} without prescription")
            return jsonify({"success": False, "message": "Prescription is required to complete appointment"}), 400

        # Prepare update expression for appointment
        update_expr = "SET #status = :status"
        expr_names = {"#status": "status"}
        expr_values = {":status": status}
        
        # Add notes if provided
        if notes:
            update_expr += ", #notes = :notes"
            expr_names["#notes"] = "notes"
            expr_values[":notes"] = notes

        # Update appointment status and notes
        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
        )
        
        logger.info(f"Appointment {appointment_id} status updated to {status} by doctor {doctor_username}")
        
        # If notes/prescription provided, save to medical records
        if notes:
            patient_username = appointment.get("username")
            save_medical_record(
                username=patient_username,
                doctor_id=doctor_username,
                record_data={
                    "appointment_id": appointment_id,
                    "type": "prescription",
                    "prescription": notes,
                    "date": appointment.get("date", datetime.utcnow().strftime("%Y-%m-%d")),
                    "created_by": doctor_username,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            logger.info(f"Prescription saved to medical records for patient {patient_username}")

        # Get doctor info for notification
        doctor = doctors_table.get_item(Key={"id": doctor_username}).get("Item")
        doctor_name = doctor.get("name", "Doctor") if doctor else "Doctor"
        
        # Send notification
        message_map = {
            "confirmed": f"Your appointment has been confirmed by {doctor_name}",
            "cancelled": f"Your appointment has been cancelled by {doctor_name}",
            "completed": f"Your appointment has been marked as completed by {doctor_name}. Prescription: {notes[:50]}..." if notes else "Your appointment has been marked as completed"
        }
        
        send_notification(
            subject=f"Appointment {status.title()}",
            message=message_map.get(status, f"Appointment status updated to {status}"),
        )

        return jsonify({
            "success": True,
            "message": f"Appointment {status} successfully" + (" and prescription saved" if notes else "")
        })

    except ClientError as exc:
        logger.error(f"ClientError updating appointment {appointment_id}: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating appointment {appointment_id}: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/doctor/add-prescription", methods=["POST"])
def doctor_add_prescription():
    """Add prescription to an appointment"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")
        prescription = data.get("prescription", "").strip()
        
        if not appointment_id or not prescription:
            return jsonify({"success": False, "message": "Missing required fields"}), 400
        
        doctor_username = session["username"]
        
        # Get appointment
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            return jsonify({"success": False, "message": "Appointment not found"}), 404
        
        # Verify authorization
        user_item = get_user(doctor_username)
        logged_in_doctor_id = user_item.get("doctor_id") if user_item else None
        appointment_doctor_id = appointment.get("doctor_id")
        
        is_authorized = (
            (logged_in_doctor_id and appointment_doctor_id == logged_in_doctor_id) or
            appointment_doctor_id == doctor_username or
            appointment.get("doctor_username") == doctor_username
        )
        
        if not is_authorized:
            return jsonify({"success": False, "message": "Not authorized"}), 403
        
        # Update appointment with prescription
        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression="SET notes = :notes, prescription = :prescription",
            ExpressionAttributeValues={
                ":notes": prescription,
                ":prescription": prescription
            }
        )
        
        # Save to medical records
        patient_username = appointment.get("username")
        save_medical_record(
            username=patient_username,
            doctor_id=doctor_username,
            record_data={
                "appointment_id": appointment_id,
                "type": "prescription",
                "prescription": prescription,
                "date": appointment.get("appointment_date", datetime.utcnow().strftime("%Y-%m-%d")),
                "created_by": doctor_username,
                "created_at": datetime.utcnow().isoformat()
            }
        )
        
        return jsonify({"success": True, "message": "Prescription added successfully"})
        
    except Exception as exc:
        logger.error(f"Error adding prescription: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/doctor/complete-appointment", methods=["POST"])
def doctor_complete_appointment():
    """Mark an appointment as completed"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        data = request.get_json()
        appointment_id = data.get("appointment_id")
        
        if not appointment_id:
            return jsonify({"success": False, "message": "Missing appointment ID"}), 400
        
        doctor_username = session["username"]
        
        # Get appointment
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            return jsonify({"success": False, "message": "Appointment not found"}), 404
        
        # Verify authorization
        user_item = get_user(doctor_username)
        logged_in_doctor_id = user_item.get("doctor_id") if user_item else None
        appointment_doctor_id = appointment.get("doctor_id")
        
        is_authorized = (
            (logged_in_doctor_id and appointment_doctor_id == logged_in_doctor_id) or
            appointment_doctor_id == doctor_username or
            appointment.get("doctor_username") == doctor_username
        )
        
        if not is_authorized:
            return jsonify({"success": False, "message": "Not authorized"}), 403
        
        # Update appointment status to completed
        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": "completed"}
        )
        
        # Send notification
        send_notification(
            subject="Appointment Completed",
            message=f"Your appointment has been marked as completed.",
        )
        
        return jsonify({"success": True, "message": "Appointment marked as completed"})
        
    except Exception as exc:
        logger.error(f"Error completing appointment: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/admin/update-appointment/<appointment_id>", methods=["POST"])
def admin_update_appointment(appointment_id: str):
    """Admin: Update appointment status (confirm, cancel)"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        admin_username = session["username"]
        logger.info(f"Admin {admin_username} attempting to update appointment {appointment_id}")
        
        # Get appointment details
        appointment = appointments_table.get_item(Key={"id": appointment_id}).get("Item")
        if not appointment:
            logger.error(f"Appointment not found: {appointment_id}")
            return jsonify({"success": False, "message": "Appointment not found"}), 404

        # Get the new status from request
        status = request.form.get("status", "").strip()
        
        if status not in ["confirmed", "cancelled"]:
            logger.error(f"Invalid status for admin: {status}")
            return jsonify({"success": False, "message": "Invalid status"}), 400

        # Update appointment status
        appointments_table.update_item(
            Key={"id": appointment_id},
            UpdateExpression="SET #status = :status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={":status": status},
        )
        
        logger.info(f"Appointment {appointment_id} status updated to {status} by admin {admin_username}")
        
        # Send notification to doctor
        doctor_id = appointment.get("doctor_id")
        if doctor_id:
            try:
                doctor = doctors_table.get_item(Key={"id": doctor_id}).get("Item") if len(doctor_id) == 36 else None
                if not doctor:
                    # Try looking up by username
                    scan_resp = doctors_table.scan(FilterExpression="username = :username", ExpressionAttributeValues={":username": doctor_id})
                    doctor = scan_resp.get("Items", [None])[0] if scan_resp.get("Items") else None
                
                if doctor and doctor.get("email"):
                    subject = f"Appointment Status Updated"
                    message = f"Admin has {status} an appointment (ID: {appointment_id}). Please check your dashboard for details."
                    sns_client.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
            except Exception as e:
                logger.error(f"Error sending notification to doctor: {e}")

        return jsonify({
            "success": True,
            "message": f"Appointment {status} successfully"
        })

    except ClientError as exc:
        logger.error(f"ClientError updating appointment {appointment_id}: {exc}")
        return jsonify({" success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating appointment {appointment_id}: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


# ===== DOCTOR PROFILE MANAGEMENT ROUTES =====

@app.route("/doctor/update-profile", methods=["POST"])
def doctor_update_profile():
    """Update doctor profile information (name, specialization, qualifications, experience)"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        doctor_username = session["username"]
        
        # Get form data
        name = request.form.get("name", "").strip()
        specialization = request.form.get("specialization", "").strip()
        qualifications = request.form.get("qualifications", "").strip()
        experience = request.form.get("experience", "").strip()
        
        # Validate required fields
        if not name or not specialization:
            return jsonify({"success": False, "message": "Name and specialization are required"}), 400
        
        # Build update expression
        update_expr = "SET #name = :name, #spec = :spec"
        expr_names = {
            "#name": "name",
            "#spec": "specialization"
        }
        expr_values = {
            ":name": name,
            ":spec": specialization
        }
        
        # Add optional fields if provided
        if qualifications:
            update_expr += ", qualifications = :qual"
            expr_values[":qual"] = qualifications
        
        if experience:
            update_expr += ", experience = :exp"
            expr_values[":exp"] = experience
        
        # Update doctor record in database
        doctors_table.update_item(
            Key={"id": doctor_username},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        
        logger.info(f"Doctor {doctor_username} updated profile successfully")
        
        return jsonify({
            "success": True,
            "message": "Profile updated successfully"
        })
    
    except ClientError as exc:
        logger.error(f"ClientError updating doctor profile: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating doctor profile: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/doctor/update-contact", methods=["POST"])
def doctor_update_contact():
    """Update doctor contact information (email, phone)"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        doctor_username = session["username"]
        
        # Get form data
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        
        # Validate at least one field is provided
        if not email and not phone:
            return jsonify({"success": False, "message": "At least one contact field is required"}), 400
        
        # Build update expression
        update_parts = []
        expr_values = {}
        
        if email:
            update_parts.append("email = :email")
            expr_values[":email"] = email
        
        if phone:
            update_parts.append("phone = :phone")
            expr_values[":phone"] = phone
        
        update_expr = "SET " + ", ".join(update_parts)
        
        # Update doctor record in database
        doctors_table.update_item(
            Key={"id": doctor_username},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        # Update session if email was changed
        if email:
            session["email"] = email
        if phone:
            session["phone"] = phone
        
        logger.info(f"Doctor {doctor_username} updated contact info successfully")
        
        return jsonify({
            "success": True,
            "message": "Contact information updated successfully"
        })
    
    except ClientError as exc:
        logger.error(f"ClientError updating doctor contact: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating doctor contact: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/doctor/update-schedule", methods=["POST"])
def doctor_update_schedule():
    """Update doctor availability (schedule, hours, consultation fee)"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        doctor_username = session["username"]
        
        # Get the doctor's actual ID from the users table
        user_item = get_user(doctor_username)
        doctor_id = (user_item or {}).get("doctor_id")
        
        if not doctor_id:
            # Fallback: try to find doctor by name
            scan_resp = doctors_table.scan()
            doctor_profile = next((d for d in scan_resp.get("Items", []) if d.get("name") == doctor_username), None)
            doctor_id = doctor_profile.get("id") if doctor_profile else None
        
        if not doctor_id:
            return jsonify({"success": False, "message": "Doctor profile not found"}), 404
        
        # Get form data
        available_days = request.form.get("available_days", "").strip()
        available_time = request.form.get("available_time", "").strip()
        consultation_fee = request.form.get("consultation_fee", "").strip()
        
        # Validate required fields
        if not available_days or not available_time or not consultation_fee:
            return jsonify({"success": False, "message": "All schedule fields are required"}), 400
        
        # Validate time format (HH:MM-HH:MM)
        if "-" not in available_time:
            return jsonify({"success": False, "message": "Time format should be HH:MM-HH:MM"}), 400
        
        # Validate consultation fee is a number
        try:
            fee = Decimal(str(consultation_fee))
            if fee < 0:
                return jsonify({"success": False, "message": "Consultation fee must be positive"}), 400
        except (ValueError, InvalidOperation):
            return jsonify({"success": False, "message": "Invalid consultation fee"}), 400
        
        # Build update expression
        update_expr = "SET available_days = :days, available_time = :time, consultation_fee = :fee"
        expr_values = {
            ":days": available_days,
            ":time": available_time,
            ":fee": fee
        }
        
        # Update doctor record in database
        doctors_table.update_item(
            Key={"id": doctor_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )
        
        # Update session
        session["available_days"] = available_days
        session["available_time"] = available_time
        session["consultation_fee"] = float(fee)
        
        logger.info(f"Doctor {doctor_username} (ID: {doctor_id}) updated schedule successfully: days={available_days}, time={available_time}, fee={fee}")
        
        return jsonify({
            "success": True,
            "message": "Schedule updated successfully"
        })
    
    except ClientError as exc:
        logger.error(f"ClientError updating doctor schedule: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception updating doctor schedule: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


@app.route("/doctor/change-password", methods=["POST"])
def doctor_change_password():
    """Change doctor password"""
    if "username" not in session or session.get("role") != "doctor":
        return jsonify({"success": False, "message": "Unauthorized"}), 401
    
    try:
        doctor_username = session["username"]
        
        # Get form data
        current_password = request.form.get("currentPassword", "").strip()
        new_password = request.form.get("newPassword", "").strip()
        confirm_password = request.form.get("confirmPassword", "").strip()
        
        # Validate required fields
        if not current_password or not new_password or not confirm_password:
            return jsonify({"success": False, "message": "All password fields are required"}), 400
        
        # Validate new password matches confirmation
        if new_password != confirm_password:
            return jsonify({"success": False, "message": "New passwords do not match"}), 400
        
        # Validate password length
        if len(new_password) < 6:
            return jsonify({"success": False, "message": "Password must be at least 6 characters long"}), 400
        
        # Get current doctor record
        doctor_resp = doctors_table.get_item(Key={"id": doctor_username})
        doctor = doctor_resp.get("Item")
        
        if not doctor:
            return jsonify({"success": False, "message": "Doctor not found"}), 404
        
        # Verify current password
        stored_password = doctor.get("password", "")
        if not check_password_hash(stored_password, current_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 400
        
        # Hash new password
        new_password_hash = generate_password_hash(new_password)
        
        # Update password in database
        doctors_table.update_item(
            Key={"id": doctor_username},
            UpdateExpression="SET password = :password",
            ExpressionAttributeValues={":password": new_password_hash}
        )
        
        logger.info(f"Doctor {doctor_username} changed password successfully")
        
        return jsonify({
            "success": True,
            "message": "Password changed successfully"
        })
    
    except ClientError as exc:
        logger.error(f"ClientError changing doctor password: {exc}")
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        logger.error(f"Exception changing doctor password: {exc}", exc_info=True)
        return jsonify({"success": False, "message": "An error occurred"}), 500


# ===== ADMIN USER MANAGEMENT ROUTES =====

@app.route("/admin/add-user", methods=["POST"])
def admin_add_user():
    """Admin route to add a new user"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Admin access required"}), 403
    
    try:
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "user").strip().lower()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        
        if not username or not password:
            return jsonify({"success": False, "message": "Username and password required"}), 400
        
        # Check if user exists
        existing = users_table.get_item(Key={"username": username})
        if "Item" in existing:
            return jsonify({"success": False, "message": "User already exists"}), 400
        
        # Create user
        user_item = {
            "username": username,
            "password_hash": generate_password_hash(password),
            "role": role,
            "email": email,
            "phone": phone
        }
        
        users_table.put_item(Item=user_item)
        logger.info(f"Admin {session['username']} created user {username}")
        
        send_notification(
            subject=f"New User Created by Admin",
            message=f"Admin {session['username']} created user: {username} (Role: {role})"
        )
        
        return jsonify({"success": True, "message": "User created successfully"})
    
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return jsonify({"success": False, "message": "Failed to create user"}), 500


@app.route("/admin/update-user/<username>", methods=["POST"])
def admin_update_user(username):
    """Admin route to update user details"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Admin access required"}), 403
    
    try:
        # Check if user exists
        user = users_table.get_item(Key={"username": username})
        if "Item" not in user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Build update expression
        updates = {}
        
        # Basic fields
        if request.form.get("fullname"):
            updates["fullname"] = request.form.get("fullname").strip()
        if request.form.get("email"):
            updates["email"] = request.form.get("email").strip()
        if request.form.get("phone"):
            updates["phone"] = request.form.get("phone").strip()
        if request.form.get("age"):
            updates["age"] = int(request.form.get("age"))
        if request.form.get("gender"):
            updates["gender"] = request.form.get("gender").strip()
        if request.form.get("address"):
            updates["address"] = request.form.get("address").strip()
        if request.form.get("role"):
            updates["role"] = request.form.get("role").strip().lower()
        
        # Doctor-specific fields
        if request.form.get("specialization"):
            updates["specialization"] = request.form.get("specialization").strip()
        if request.form.get("qualifications"):
            updates["qualifications"] = request.form.get("qualifications").strip()
        if request.form.get("experience"):
            updates["experience"] = int(request.form.get("experience"))
        if request.form.get("consultation_fee"):
            updates["consultation_fee"] = float(request.form.get("consultation_fee"))
        if request.form.get("available_days"):
            updates["available_days"] = request.form.get("available_days").strip()
        if request.form.get("available_time"):
            updates["available_time"] = request.form.get("available_time").strip()
        
        # Patient-specific fields
        if request.form.get("blood_group"):
            updates["blood_group"] = request.form.get("blood_group").strip()
        if request.form.get("medical_history"):
            updates["medical_history"] = request.form.get("medical_history").strip()
        if request.form.get("emergency_contact"):
            updates["emergency_contact"] = request.form.get("emergency_contact").strip()
        
        # Update password if provided
        if request.form.get("password"):
            updates["password_hash"] = generate_password_hash(request.form.get("password"))
        
        if not updates:
            return jsonify({"success": False, "message": "No fields to update"}), 400
        
        # Build update expression with attribute name mapping for reserved keywords
        expr_attr_names = {}
        update_parts = []
        
        for k in updates.keys():
            # Handle reserved keywords by using expression attribute names
            if k in ["role", "status", "name", "timestamp", "date", "time"]:
                placeholder = f"#{k}"
                expr_attr_names[placeholder] = k
                update_parts.append(f"{placeholder} = :{k}")
            else:
                update_parts.append(f"{k} = :{k}")
        
        update_expr = "SET " + ", ".join(update_parts)
        expr_values = {f":{k}": v for k, v in updates.items()}
        
        # Perform update with ExpressionAttributeNames if needed
        update_params = {
            "Key": {"username": username},
            "UpdateExpression": update_expr,
            "ExpressionAttributeValues": expr_values
        }
        
        if expr_attr_names:
            update_params["ExpressionAttributeNames"] = expr_attr_names
        
        users_table.update_item(**update_params)
        
        logger.info(f"Admin {session['username']} updated user {username}")
        return jsonify({"success": True, "message": "User updated successfully"})
    
    except Exception as e:
        logger.error(f"Error updating user {username}: {e}")
        return jsonify({"success": False, "message": "Failed to update user"}), 500


@app.route("/admin/delete-user/<username>", methods=["POST"])
def admin_delete_user(username):
    """Admin route to delete a user"""
    if "username" not in session or session.get("role") != "admin":
        return jsonify({"success": False, "message": "Admin access required"}), 403
    
    try:
        # Prevent admin from deleting themselves
        if username == session["username"]:
            return jsonify({"success": False, "message": "Cannot delete your own account"}), 400
        
        # Check if user exists
        user = users_table.get_item(Key={"username": username})
        if "Item" not in user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Delete user
        users_table.delete_item(Key={"username": username})
        
        logger.info(f"Admin {session['username']} deleted user {username}")
        send_notification(
            subject=f"User Deleted by Admin",
            message=f"Admin {session['username']} deleted user: {username}"
        )
        
        return jsonify({"success": True, "message": "User deleted successfully"})
    
    except Exception as e:
        logger.error(f"Error deleting user {username}: {e}")
        return jsonify({"success": False, "message": "Failed to delete user"}), 500


@app.route("/api/health-info", methods=["GET", "POST"])
def health_info_api():
    """API endpoint for user health information"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    username = session["username"]
    
    if request.method == "GET":
        try:
            user = get_user(username)
            if not user:
                return jsonify({"success": False, "message": "User not found"}), 404
            
            return jsonify({
                "success": True,
                "weight": user.get("weight"),
                "height": user.get("height"),
                "blood_group": user.get("blood_group"),
                "age": user.get("age"),
                "gender": user.get("gender"),
                "allergies": user.get("allergies"),
                "conditions": user.get("conditions")
            })
        except Exception as e:
            logger.error(f"Error getting health info: {e}")
            return jsonify({"success": False, "message": "Failed to get health info"}), 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            
            updates = {}
            if data.get("weight"):
                updates["weight"] = to_decimal(data.get("weight"))
            if data.get("height"):
                updates["height"] = to_decimal(data.get("height"))
            if data.get("blood_group"):
                updates["blood_group"] = data.get("blood_group")
            if data.get("age"):
                updates["age"] = int(data.get("age"))
            if data.get("gender"):
                updates["gender"] = data.get("gender")
            if data.get("allergies"):
                updates["allergies"] = data.get("allergies")
            if data.get("conditions"):
                updates["conditions"] = data.get("conditions")
            
            if not updates:
                return jsonify({"success": False, "message": "No data to update"}), 400
            
            # Update user in DynamoDB
            update_expr = "SET " + ", ".join([f"{k} = :{k}" for k in updates.keys()])
            expr_values = {f":{k}": v for k, v in updates.items()}
            
            users_table.update_item(
                Key={"username": username},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values
            )
            
            logger.info(f"User {username} updated health information")
            return jsonify({"success": True, "message": "Health information updated successfully"})
        
        except Exception as e:
            logger.error(f"Error updating health info: {e}")
            return jsonify({"success": False, "message": "Failed to update health info"}), 500


@app.route("/api/medical-records", methods=["GET"])
def get_medical_records_api():
    """Get medical records for the current user"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401
    
    try:
        username = session["username"]
        
        # Scan for records belonging to this user
        response = medical_records_table.scan(
            FilterExpression="patient_username = :username",
            ExpressionAttributeValues={":username": username}
        )
        
        records = response.get("Items", [])
        
        # Convert datetime to strings for JSON serialization
        for record in records:
            if "upload_date" in record:
                record["upload_date"] = record["upload_date"].isoformat() if hasattr(record["upload_date"], "isoformat") else str(record["upload_date"])
        
        return jsonify({
            "success": True,
            "records": records
        })
    
    except Exception as e:
        logger.error(f"Error fetching medical records: {e}")
        return jsonify({"success": False, "message": "Failed to fetch records"}), 500


@app.route("/api/view-record/<record_id>", methods=["GET"])
def view_record(record_id):
    """View a specific medical record document"""
    if "username" not in session:
        return redirect(url_for("login"))
    
    try:
        username = session["username"]
        
        # Get the record from database
        response = medical_records_table.get_item(Key={"id": record_id})
        record = response.get("Item")
        
        if not record or record.get("patient_username") != username:
            return ("Unauthorized", 403)
        
        # Serve the file
        file_path = record.get("file_path")
        if file_path and os.path.exists(file_path):
            directory = os.path.dirname(file_path)
            filename = os.path.basename(file_path)
            return send_from_directory(directory, filename)
        else:
            return ("File not found", 404)
    
    except Exception as e:
        logger.error(f"Error viewing record: {e}")
        return ("Error viewing record", 500)


@app.route("/api/appointments", methods=["GET"])
def get_appointments_api():
    """Get appointments for the current user"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401
    
    try:
        username = session["username"]
        
        # Scan for appointments belonging to this user
        response = appointments_table.scan(
            FilterExpression="username = :username",
            ExpressionAttributeValues={":username": username}
        )
        
        appointments = response.get("Items", [])
        
        # Normalize appointments for frontend
        from datetime import datetime as dt_class, date as date_class
        normalized_appointments = []
        
        for appt in appointments:
            # Handle date conversion
            date_val = appt.get("date") or appt.get("appointment_date")
            if isinstance(date_val, str):
                try:
                    appt["appointment_date"] = date_val
                except Exception:
                    appt["appointment_date"] = str(date_class.today())
            elif isinstance(date_val, (date_class, dt_class)):
                appt["appointment_date"] = date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val)
            else:
                appt["appointment_date"] = str(date_class.today())
            
            # Ensure required fields
            appt.setdefault("appointment_time", appt.get("time", ""))
            appt.setdefault("status", "pending")
            appt.setdefault("symptoms", appt.get("reason", ""))
            appt.setdefault("doctor_name", "")
            
            normalized_appointments.append(appt)
        
        return jsonify({
            "success": True,
            "appointments": normalized_appointments
        })
    
    except Exception as e:
        logger.error(f"Error fetching appointments: {e}")
        return jsonify({"success": False, "message": "Failed to fetch appointments"}), 500


@app.route("/api/update-profile", methods=["POST"])
def update_profile():
    """Update user profile information"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401
    
    try:
        username = session["username"]
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        full_name = request.form.get("full_name", "").strip()
        age = request.form.get("age", "").strip()
        gender = request.form.get("gender", "").strip()
        
        # Handle profile picture upload
        profile_picture_path = None
        if "profile_picture" in request.files:
            file = request.files["profile_picture"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
                
                upload_dir = os.path.join(app.instance_path, "uploads", "profile_pictures")
                os.makedirs(upload_dir, exist_ok=True)
                
                file_path = os.path.join(upload_dir, safe_name)
                file.save(file_path)
                profile_picture_path = f"profile_pictures/{safe_name}"
        
        # Build update expression
        update_parts = []
        expr_values = {}
        
        if email:
            update_parts.append("email = :email")
            expr_values[":email"] = email
            session["email"] = email  # Update session
        
        if phone:
            update_parts.append("phone = :phone")
            expr_values[":phone"] = phone
            session["phone"] = phone  # Update session
        
        if full_name:
            update_parts.append("#name = :name")
            expr_values[":name"] = full_name
            session["full_name"] = full_name  # Update session
        
        if age:
            update_parts.append("age = :age")
            expr_values[":age"] = age
            session["age"] = age  # Update session
        
        if gender:
            update_parts.append("gender = :gender")
            expr_values[":gender"] = gender
            session["gender"] = gender  # Update session
        
        if profile_picture_path:
            update_parts.append("profile_picture = :pp")
            expr_values[":pp"] = profile_picture_path
            session["profile_picture"] = profile_picture_path  # Update session
        
        if update_parts:
            update_expr = "SET " + ", ".join(update_parts)
            attr_names = {}
            if "#name" in update_expr:
                attr_names["#name"] = "name"
            
            users_table.update_item(
                Key={"username": username},
                UpdateExpression=update_expr,
                ExpressionAttributeValues=expr_values,
                ExpressionAttributeNames=attr_names if attr_names else None
            )
        
        return jsonify({"success": True, "message": "Profile updated successfully"})
    
    except Exception as e:
        logger.error(f"Error updating profile: {e}")
        return jsonify({"success": False, "message": "Failed to update profile"}), 500


@app.route("/api/change-password", methods=["POST"])
def change_password():
    """Change user password"""
    if "username" not in session:
        return jsonify({"success": False, "message": "Please log in"}), 401
    
    try:
        username = session["username"]
        data = request.get_json()
        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")
        
        if not current_password or not new_password:
            return jsonify({"success": False, "message": "All fields are required"}), 400
        
        # Get user from database
        response = users_table.get_item(Key={"username": username})
        user = response.get("Item")
        
        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404
        
        # Verify current password
        if not check_password_hash(user.get("password_hash", ""), current_password):
            return jsonify({"success": False, "message": "Current password is incorrect"}), 400
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        users_table.update_item(
            Key={"username": username},
            UpdateExpression="SET password_hash = :ph",
            ExpressionAttributeValues={":ph": new_password_hash}
        )
        
        logger.info(f"Password changed for user: {username}")
        return jsonify({"success": True, "message": "Password changed successfully"})
    
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        return jsonify({"success": False, "message": "Failed to change password"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
