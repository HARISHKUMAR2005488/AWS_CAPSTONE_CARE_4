import os
import uuid
import base64
from datetime import datetime
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "change_me")

# AWS configuration (uses instance/role credentials; no hardcoded keys)
REGION = os.getenv("AWS_REGION", "us-east-1")
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns = boto3.client("sns", region_name=REGION)

# DynamoDB table names (override via environment variables if needed)
USERS_TABLE = os.getenv("USERS_TABLE", "Users")
DOCTORS_TABLE = os.getenv("DOCTORS_TABLE", "Doctors")
APPOINTMENTS_TABLE = os.getenv("APPOINTMENTS_TABLE", "Appointments")
MEDICAL_RECORDS_TABLE = os.getenv("MEDICAL_RECORDS_TABLE", "MedicalRecords")

users_table = dynamodb.Table(USERS_TABLE)
doctors_table = dynamodb.Table(DOCTORS_TABLE)
appointments_table = dynamodb.Table(APPOINTMENTS_TABLE)
medical_records_table = dynamodb.Table(MEDICAL_RECORDS_TABLE)

# File upload configuration
MAX_FILE_SIZE = 1 * 1024 * 1024  # 1MB limit for DynamoDB storage
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'doc', 'docx'}

# SNS topic for booking notifications (subscribe email endpoints to this topic)
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")


def get_user(username: str):
    resp = users_table.get_item(Key={"username": username})
    return resp.get("Item")


def send_notification(subject: str, message: str) -> None:
    if not SNS_TOPIC_ARN:


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
        app.logger.warning("SNS_TOPIC_ARN not set; skipping notification")
        return
    try:
        sns.publish(TopicArn=SNS_TOPIC_ARN, Subject=subject, Message=message)
    except ClientError as exc:
        app.logger.error("Error sending notification: %s", exc)


@lru_cache(maxsize=1)
def has_username_index() -> bool:
    try:
        desc = dynamodb.meta.client.describe_table(TableName=appointments_table.name)
        gsis = desc.get("Table", {}).get("GlobalSecondaryIndexes", [])
        return any(gsi.get("IndexName") == "username-index" for gsi in gsis)
    except ClientError as exc:
        app.logger.error("Failed to describe table for GSI check: %s", exc)
        return False

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
        username = request.form["username"].strip()
        password = request.form["password"].strip()

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

        appts_resp = appointments_table.scan()
        doctor_appts = [a for a in appts_resp.get("Items", []) if a.get("doctor_id") == doctor_id]

        return render_template(
            "doctor.html",
            username=username,
            doctor=doctor_profile,
            appointments=doctor_appts,
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

@app.route("/doctors")
def doctors_list():
    if "username" not in session:
        return redirect(url_for("login"))

    doctors_resp = doctors_table.scan()
    doctors = doctors_resp.get("Items", [])
    return render_template("doctors.html", doctors=doctors)

@app.route("/book/<doctor_id>", methods=["GET", "POST"])
def book(doctor_id: str):
    if "username" not in session:
        return redirect(url_for("login"))

    doctor = doctors_table.get_item(Key={"id": doctor_id}).get("Item")
    if not doctor:
        flash("Doctor not found", "danger")
        return redirect(url_for("doctors_list"))

    if request.method == "POST":
        username = session["username"]
        appointment_id = str(uuid.uuid4())
        date = request.form.get("date")
        time = request.form.get("time")
        reason = request.form.get("reason", "").strip()

        appointments_table.put_item(
            Item={
                "id": appointment_id,
                "doctor_id": doctor_id,
                "doctor_name": doctor.get("name"),
                "username": username,
                "date": date,
                "time": time,
                "reason": reason,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        send_notification(
            subject="Appointment Booked",
            message=f"User {username} booked {doctor.get('name')} on {date} at {time}.",
        )

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
@app.route("/user/upload-document", methods=["POST"])
def upload_document():
    if "username" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    username = session["username"]
    user = get_user(username)
    
    if not user or user.get("role") != "user":
        return jsonify({"success": False, "message": "Access denied"}), 403

    file = request.files.get("document")
    description = request.form.get("description", "").strip()

    if not file or file.filename == "":
        return jsonify({"success": False, "message": "No file provided"}), 400

    if not allowed_file(file.filename):
        return jsonify({
            "success": False, 
            "message": f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        }), 400

    try:
        # Read file content
        file_content = file.read()
        file_size = len(file_content)

        # Check file size (DynamoDB has 400KB item limit, we set 1MB app limit)
        if file_size > MAX_FILE_SIZE:
            return jsonify({
                "success": False,
                "message": f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
            }), 400

        # Encode file as base64 for storage in DynamoDB
        file_base64 = base64.b64encode(file_content).decode('utf-8')
        
        filename = secure_filename(file.filename)
        file_type = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
        
        # Create medical record
        record_id = str(uuid.uuid4())
        medical_records_table.put_item(
            Item={
                "id": record_id,
                "username": username,
                "filename": filename,
                "description": description,
                "file_type": file_type,
                "file_size": file_size,
                "file_data": file_base64,  # Base64 encoded file
                "upload_date": datetime.utcnow().isoformat(),
            }
        )

        return jsonify({
            "success": True,
            "message": "Document uploaded successfully",
            "description": description
        })

    except ClientError as exc:
        app.logger.error("DynamoDB error: %s", exc)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        app.logger.error("Upload error: %s", exc)
        return jsonify({"success": False, "message": str(exc)}), 500


@app.route("/user/medical-records")
def medical_records():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    
    try:
        # Query medical records for this user
        response = medical_records_table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr("username").eq(username)
        )
        
        records = response.get("Items", [])
        
        # Remove file_data from response to avoid sending large base64 in list view
        for record in records:
            if "file_data" in record:
                del record["file_data"]
        
        # Sort by upload date (newest first)
        records.sort(key=lambda x: x.get("upload_date", ""), reverse=True)
        
        return render_template("patient_records.html", medical_records=records)
        
    except ClientError as exc:
        app.logger.error("Error fetching medical records: %s", exc)
        flash("Error loading medical records", "danger")
        return redirect(url_for("home"))


@app.route("/user/download-document/<record_id>")
def download_document(record_id):
    if "username" not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    username = session["username"]
    
    try:
        # Get the medical record
        response = medical_records_table.get_item(Key={"id": record_id})
        record = response.get("Item")
        
        if not record:
            return jsonify({"success": False, "message": "Record not found"}), 404
        
        # Verify ownership
        if record.get("username") != username:
            return jsonify({"success": False, "message": "Access denied"}), 403
        
        # Decode base64 file data
        file_data = base64.b64decode(record.get("file_data", ""))
        
        from flask import send_file
        import io
        
        return send_file(
            io.BytesIO(file_data),
            download_name=record.get("filename", "document"),
            as_attachment=True,
            mimetype=f'application/{record.get("file_type", "octet-stream")}'
        )
        
    except ClientError as exc:
        app.logger.error("Error downloading document: %s", exc)
        return jsonify({"success": False, "message": "Database error"}), 500
    except Exception as exc:
        app.logger.error("Download error: %s", exc)
        return jsonify({"success": False, "message": str(exc)}), 500


        else appointments_table.scan()
    )

    appointments = appts_resp.get("Items", [])
    if not has_username_index():
        appointments = [a for a in appointments if a.get("username") == username]

    return render_template("appointments.html", appointments=appointments)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)