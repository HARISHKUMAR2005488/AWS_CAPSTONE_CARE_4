import os
import uuid
from datetime import datetime
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash, generate_password_hash

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

users_table = dynamodb.Table(USERS_TABLE)
doctors_table = dynamodb.Table(DOCTORS_TABLE)
appointments_table = dynamodb.Table(APPOINTMENTS_TABLE)

# SNS topic for booking notifications (subscribe email endpoints to this topic)
SNS_TOPIC_ARN = os.getenv("SNS_TOPIC_ARN")


def get_user(username: str):
    resp = users_table.get_item(Key={"username": username})
    return resp.get("Item")


def send_notification(subject: str, message: str) -> None:
    if not SNS_TOPIC_ARN:
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
        else appointments_table.scan()
    )

    appointments = appts_resp.get("Items", [])
    if not has_username_index():
        appointments = [a for a in appointments if a.get("username") == username]

    return render_template("appointments.html", appointments=appointments)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)