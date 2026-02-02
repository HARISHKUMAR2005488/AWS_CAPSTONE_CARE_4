import os
import uuid
import logging
from datetime import datetime, date
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

# Import new modular components
from config import Config
from services.aws_service import AWSService
from services.ai_service import AIService

app = Flask(__name__)
app.config.from_object(Config)

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS Service
aws = AWSService()

# --- Context Processor ---
@app.context_processor
def inject_current_user():
    return dict(current_user={
        "is_authenticated": "username" in session,
        "username": session.get("username"),
        "user_type": session.get("role", "user")
    })

# --- Utils ---
def to_decimal(value, default="0"):
    try:
        return Decimal(str(value) if value else default)
    except:
        return Decimal(default)

# --- Routes ---

@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/about")
def about():
    return render_template("about.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"].strip()
        role = request.form.get("role", "user").strip().lower()
        
        # Security: Check Admin Key from Config
        if role == "admin":
            admin_key = request.form.get("admin_key", "").strip()
            if admin_key != Config.ADMIN_REGISTRATION_KEY:
                flash("Invalid admin access key", "danger")
                return redirect(url_for("signup"))

        # Check existing user
        if aws.get_user(username):
            flash("User already exists", "warning")
            return redirect(url_for("signup"))

        # Create user item
        item = {
            "username": username,
            "password_hash": generate_password_hash(request.form["password"]),
            "role": role,
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
        }

        # Doctor specifics
        if role == "doctor":
            doctor_id = str(uuid.uuid4())
            item["doctor_id"] = doctor_id
            
            doctor_item = {
                "id": doctor_id,
                "name": username,
                "specialization": request.form.get("specialization", "General"),
                "email": item["email"],
                "phone": item["phone"],
                "qualifications": request.form.get("qualifications", ""),
                "experience": int(request.form.get("experience", "0")),
                "consultation_fee": to_decimal(request.form.get("consultation_fee", "0")),
                "available_days": request.form.get("available_days", ""),
                "available_time": request.form.get("available_time", ""),
                "is_available": True
            }
            aws.doctors_table.put_item(Item=doctor_item)

        # Save User (and Log Audit)
        aws.create_user(item)
        
        # Notification
        aws.send_notification("New Registration", f"New {role}: {username}")
        
        flash("Account created. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        user = aws.get_user(username)
        if user and check_password_hash(user.get("password_hash"), password):
            session["username"] = username
            session["role"] = user.get("role", "user")
            session["doctor_id"] = user.get("doctor_id") # Cache if exists
            
            # Audit Log
            aws.log_audit(username, "LOGIN", "Auth")
            
            flash("Logged in.", "success")
            return redirect(url_for("dashboard"))
            
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    username = session.get("username")
    if not username: return redirect(url_for("login"))
    
    role = session.get("role")
    
    if role == "admin":
        # Simplified stats fetch
        return render_template("admin.html", 
                             username=username,
                             doctors=aws.get_all_doctors(),
                             users=aws.users_table.scan().get("Items", []), # Ideally optimize this too
                             upcoming_appointments=[]) # Placeholder for simplicity
                             
    if role == "doctor":
        doctor_id = session.get("doctor_id")
        if not doctor_id:
            # Fallback lookup
            user = aws.get_user(username)
            doctor_id = user.get("doctor_id")
            
        # Use OPTIMIZED query
        appts = aws.get_appointments_for_doctor(doctor_id)
        doctor_profile = aws.get_doctor_by_id(doctor_id)
        
        # Basic filtering for UI (Today vs Upcoming)
        today = date.today()
        # Note: In a real app we'd filter these in python or better query
        
        return render_template("doctor.html",
                             username=username,
                             doctor=doctor_profile,
                             appointments=appts,
                             today_appointments=[], # Populate as needed
                             upcoming_appointments=[],
                             today=today)
                             
    # Patient Dashboard
    appts = aws.get_appointments_for_patient(username)
    return render_template("user.html", username=username, appointments=appts, feedback_dict={})

@app.route("/doctors", endpoint="doctors")
def doctors_list():
    if "username" not in session: return redirect(url_for("login"))
    docs = aws.get_all_doctors()
    # Mock ratings for template compatibility
    doctors_with_ratings = [{"doctor": d, "average_rating": 0, "total_reviews": 0} for d in docs]
    specializations = sorted(list(set(d.get("specialization", "General") for d in docs)))
    return render_template("doctors.html", doctors=docs, doctors_with_ratings=doctors_with_ratings, specializations=specializations)

@app.route("/aws-health")
def aws_health():
    if session.get("role") != "admin": return redirect(url_for("dashboard"))
    
    instances = aws.get_ec2_health()
    return render_template("aws_health.html", ec2_instances=instances, region=Config.AWS_REGION, table_stats={})

@app.route("/user/chat-assistant", methods=["POST"])
def chat_assistant():
    """Refactored AI Symptom Checker"""
    if "username" not in session: return jsonify({"success": False}), 401
    
    data = request.get_json(silent=True) or {}
    symptoms = data.get("symptoms", "")
    
    analysis = AIService.analyze_symptoms(symptoms)
    
    # Audit log if emergency
    if analysis['is_emergency']:
        aws.log_audit(session['username'], "EMERGENCY_SYMPTOMS", "AIService", {"symptoms": symptoms})
    
    return jsonify({"success": True, **analysis})

# --- Essential File Uploads ---
@app.route("/user/upload-document", methods=["POST"])
def upload_document():
    if "username" not in session: return jsonify({"success": False}), 401
    
    file = request.files.get("document")
    if not file: return jsonify({"success": False, "message": "No file"}), 400
    
    filename = secure_filename(file.filename)
    username = session["username"]
    
    # Local Storage (Within Constraints)
    upload_dir = os.path.join(app.instance_path, Config.UPLOAD_FOLDER, username)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)
    
    # DB Record
    record_id = str(uuid.uuid4())
    aws.records_table.put_item(Item={
        "record_id": record_id,
        "username": username,
        "filename": filename,
        "upload_date": datetime.utcnow().isoformat()
    })
    
    aws.log_audit(username, "UPLOAD_FILE", "MedicalRecords", {"filename": filename})
    return jsonify({"success": True, "message": "Uploaded"})

# --- Main ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)