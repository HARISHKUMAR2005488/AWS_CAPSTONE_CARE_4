from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
import mimetypes
import json
import os
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload, selectinload

try:
    from flask_caching import Cache
except ImportError:
    Cache = None

try:
    import boto3
except ImportError:
    boto3 = None

try:
    from PIL import Image
except ImportError:
    Image = None

from config import Config
from database import db, User, Doctor, Appointment, TimeSlot, MedicalRecord, Feedback, DoctorAvailability, Prescription, Report, AuditLog, Notification

# ---------------------------------------------------------------------------
# APPOINTMENT STATUS LIFECYCLE
# Valid statuses: pending, approved, rejected, completed, cancelled
# Legacy DB value 'confirmed' is treated as 'approved' everywhere.
# ---------------------------------------------------------------------------
VALID_STATUSES = {'pending', 'approved', 'rejected', 'completed', 'cancelled'}

ALLOWED_REPORT_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
MAX_REPORT_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Maps (current_status, role) → set of allowed next statuses
ALLOWED_TRANSITIONS = {
    # Patient can only cancel a pending appointment
    ('pending',   'patient'):  {'cancelled'},
    # Doctor: pending → approved or rejected; approved → completed (only if past)
    ('pending',   'doctor'):   {'approved', 'rejected'},
    ('approved',  'doctor'):   {'completed'},
    ('confirmed', 'doctor'):   {'completed'},     # legacy compat
    # Admin has broad control; cannot move completed → pending
    ('pending',   'admin'):    {'approved', 'rejected', 'cancelled'},
    ('approved',  'admin'):    {'completed', 'cancelled'},
    ('confirmed', 'admin'):    {'completed', 'cancelled'},  # legacy compat
    ('rejected',  'admin'):    {'pending'},
    ('cancelled', 'admin'):    {'pending'},
}


def validate_transition(appointment, new_status, role):
    """
    Returns (ok: bool, error_message: str).
    Normalises 'confirmed' to 'approved' for lookup.
    """
    current = appointment.status or 'pending'
    # normalise legacy value for transition lookup
    lookup_current = 'approved' if current == 'confirmed' else current

    allowed = ALLOWED_TRANSITIONS.get((lookup_current, role), set())
    if new_status not in allowed:
        return False, (
            f"Cannot move appointment from '{current}' to '{new_status}' "
            f"as a {role}."
        )

    # Doctor can only mark 'completed' if the appointment date has passed
    if role == 'doctor' and new_status == 'completed':
        appt_datetime = datetime.combine(appointment.appointment_date, datetime.min.time())
        if appt_datetime >= datetime.utcnow():
            return False, (
                "Appointment can only be marked Completed after the scheduled time has passed."
            )

    return True, ''


def send_notification_email(user, title, message):
    """SES-ready stub: currently logs notification email details for future AWS integration."""
    app.logger.info(
        '[NotificationEmailStub] to=%s title=%s message=%s',
        user.email,
        title,
        message
    )


def create_notification(user_id, title, message, notification_type='info', related_id=None, send_email=False):
    """Create an in-app notification and optionally trigger the SES-ready email stub."""
    user = User.query.get(user_id)
    if not user:
        return None

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=notification_type,
        related_id=related_id,
        is_read=False
    )
    db.session.add(notification)

    if send_email and user.email:
        send_notification_email(user, title, message)

    return notification


def log_action(user, action, target_type=None, target_id=None):
    """Write an audit trail row for critical user actions."""
    if not user or not getattr(user, 'id', None) or not action:
        return

    raw_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '')
    client_ip = raw_ip.split(',')[0].strip() if raw_ip else None
    role = (user.user_type or '').strip().lower()
    if role == 'user':
        role = 'patient'

    db.session.add(AuditLog(
        user_id=user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        ip_address=client_ip,
        role=role or 'patient'
    ))


def upload_to_s3(file_obj, filename, bucket_name=None, region_name=None):
    """Optional S3 helper. Not required for local mode, but ready for future switch."""
    if boto3 is None:
        raise RuntimeError('boto3 is not installed in this environment.')

    bucket = bucket_name or os.getenv('AWS_S3_BUCKET')
    region = region_name or os.getenv('AWS_REGION', 'us-east-1')
    if not bucket:
        raise RuntimeError('AWS_S3_BUCKET is not configured.')

    s3_client = boto3.client('s3', region_name=region)
    file_obj.seek(0)
    s3_client.upload_fileobj(
        file_obj,
        bucket,
        filename,
        ExtraArgs={
            'ContentType': file_obj.mimetype or 'application/octet-stream'
        }
    )

    # Public URL example (keep object ACL/policy aligned with your security policy).
    return f'https://{bucket}.s3.{region}.amazonaws.com/{filename}'


def save_file(file_storage, user_id):
    """Save report locally now; function signature stays stable for future S3 migration."""
    if not file_storage or not file_storage.filename:
        return None

    original_name = secure_filename(file_storage.filename)
    if not original_name or '.' not in original_name:
        raise ValueError('Invalid file name.')

    ext = original_name.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_REPORT_EXTENSIONS:
        raise ValueError('Only PDF, JPG, JPEG, PNG files are allowed.')

    # Explicit size guard even if MAX_CONTENT_LENGTH is configured.
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_REPORT_FILE_SIZE:
        raise ValueError('File size exceeds 5MB limit.')

    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
    stored_name = f'{user_id}_{timestamp}_{original_name}'

    upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'reports')
    os.makedirs(upload_dir, exist_ok=True)

    absolute_path = os.path.join(upload_dir, stored_name)
    file_storage.save(absolute_path)

    # Store a path relative to /static for portability.
    relative_path = os.path.join('uploads', 'reports', stored_name).replace('\\', '/')
    return {
        'file_name': original_name,
        'file_path': relative_path
    }


def _compress_image_inplace(file_path):
    """Lightweight image compression (no-op if Pillow is unavailable or file is unsupported)."""
    if Image is None:
        return
    try:
        with Image.open(file_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail((1400, 1400))
            img.save(file_path, optimize=True, quality=82)
    except Exception:
        # Keep original file if optimization fails.
        return


# ---------------------------------------------------------------------------
# SLOT GENERATION HELPER
# ---------------------------------------------------------------------------

def _parse_hhmm(time_str):
    """Parse 'HH:MM' string → (hour:int, minute:int). Returns (9, 0) on error."""
    try:
        h, m = time_str.strip().split(':')
        return int(h), int(m)
    except Exception:
        return 9, 0


def _fmt_slot(h, m):
    """Format (hour, minute) → '9:00 AM' display string and '09:00' value string."""
    period = 'AM' if h < 12 else 'PM'
    display_h = h % 12 or 12
    return f'{display_h}:{m:02d} {period}', f'{h:02d}:{m:02d}'


def generate_available_slots(doctor_id, selected_date):
    """
    Generate available appointment slots for a doctor on a given date.

    Algorithm:
    1. Look for a DoctorAvailability row matching doctor + weekday.
    2. Fall back to Doctor.available_time string (e.g. '09:00-17:00') if not found.
    3. Generate time slots every `slot_duration` minutes between start and end.
    4. Remove slots already booked (status in pending/approved/confirmed).
    5. If selected_date == today, remove slots whose time has already passed.

    Returns:
        list of dicts: [{'value': '09:00', 'label': '9:00 AM'}, ...]
        Empty list if doctor not available that day.
    """
    WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekday_name = WEEKDAY_NAMES[selected_date.weekday()]

    # --- 1. Fetch DB availability row ---
    avail = DoctorAvailability.query.filter_by(
        doctor_id=doctor_id,
        day_of_week=weekday_name,
        is_active=True
    ).first()

    if avail:
        start_h, start_m = _parse_hhmm(avail.start_time)
        end_h, end_m = _parse_hhmm(avail.end_time)
        duration = avail.slot_duration or 30
    else:
        # --- 2. Fallback: parse Doctor.available_time string ---
        doctor = Doctor.query.get(doctor_id)
        if not doctor:
            return []

        # Check available_days (comma-separated partial names, e.g. "Mon,Tue,Wed")
        if doctor.available_days:
            short = weekday_name[:3]  # "Mon", "Tue" …
            days_str = doctor.available_days.lower()
            # If available_days is set and this day is NOT in it, return empty
            if short.lower() not in days_str and weekday_name.lower() not in days_str:
                return []

        # Parse available_time string like '09:00-17:00' or '9:00 AM - 5:00 PM'
        start_h, start_m = 9, 0
        end_h, end_m = 17, 0
        duration = 30

        if doctor.available_time and '-' in doctor.available_time:
            parts = [p.strip() for p in doctor.available_time.split('-', 1)]
            if len(parts) == 2:
                try:
                    # Handle both '09:00' and '9:00 AM' formats
                    def _parse_flexible(s):
                        s = s.strip()
                        is_pm = 'pm' in s.lower()
                        s = s.upper().replace('AM', '').replace('PM', '').strip()
                        h, m = _parse_hhmm(s)
                        if is_pm and h != 12:
                            h += 12
                        return h, m
                    start_h, start_m = _parse_flexible(parts[0])
                    end_h, end_m = _parse_flexible(parts[1])
                except Exception:
                    pass

    # --- 3. Generate slots ---
    slots = []
    cur_h, cur_m = start_h, start_m
    while (cur_h, cur_m) < (end_h, end_m):
        label, value = _fmt_slot(cur_h, cur_m)
        slots.append({'value': value, 'label': label})
        total_min = cur_h * 60 + cur_m + duration
        cur_h, cur_m = divmod(total_min, 60)

    if not slots:
        return []

    # --- 4. Remove already-booked slots ---
    booked = Appointment.query.filter(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == selected_date,
        Appointment.status.in_(['pending', 'approved', 'confirmed'])
    ).all()
    booked_values = set()
    for appt in booked:
        t = appt.appointment_time
        if t:
            # Normalise stored time to HH:MM 24-hour
            if 'AM' in t.upper() or 'PM' in t.upper():
                try:
                    dt = datetime.strptime(t.strip(), '%I:%M %p')
                    booked_values.add(dt.strftime('%H:%M'))
                except Exception:
                    booked_values.add(t)
            else:
                booked_values.add(t.strip())

    slots = [s for s in slots if s['value'] not in booked_values]

    # --- 5. Remove past slots if today ---
    if selected_date == date.today():
        now = datetime.utcnow()  # use local time if needed; UTC is safe here
        now_h, now_m = now.hour, now.minute
        slots = [s for s in slots
                 if (_parse_hhmm(s['value'])[0], _parse_hhmm(s['value'])[1]) > (now_h, now_m)]

    return slots


def get_recommended_doctors(patient_id, limit=3):
    """Recommend doctors using patient's history first, then globally most booked doctors."""
    patient_rows = db.session.query(
        Appointment.doctor_id,
        func.count(Appointment.id).label('booking_count')
    ).filter(
        Appointment.patient_id == patient_id,
        Appointment.status.in_(['pending', 'approved', 'confirmed', 'completed'])
    ).group_by(Appointment.doctor_id).order_by(
        func.count(Appointment.id).desc()
    ).limit(limit).all()

    recommended = []
    used_doctor_ids = set()

    for row in patient_rows:
        doctor = Doctor.query.get(row.doctor_id)
        if not doctor:
            continue
        used_doctor_ids.add(doctor.id)
        recommended.append({
            'id': doctor.id,
            'name': doctor.name,
            'specialization': doctor.specialization,
            'reason': 'Based on your previous visits',
            'booking_count': int(row.booking_count or 0)
        })

    remaining = max(limit - len(recommended), 0)
    if remaining > 0:
        global_rows = db.session.query(
            Appointment.doctor_id,
            func.count(Appointment.id).label('booking_count')
        ).filter(
            Appointment.status.in_(['pending', 'approved', 'confirmed', 'completed'])
        ).group_by(Appointment.doctor_id).order_by(
            func.count(Appointment.id).desc()
        ).limit(10).all()

        for row in global_rows:
            if row.doctor_id in used_doctor_ids:
                continue
            doctor = Doctor.query.get(row.doctor_id)
            if not doctor:
                continue
            recommended.append({
                'id': doctor.id,
                'name': doctor.name,
                'specialization': doctor.specialization,
                'reason': 'Popular with other patients',
                'booking_count': int(row.booking_count or 0)
            })
            used_doctor_ids.add(doctor.id)
            if len(recommended) >= limit:
                break

    return recommended[:limit]


def get_best_time_slots(limit=5):
    """Suggest commonly used appointment times while avoiding today's already busy slots."""
    today = date.today()
    busy_today = {
        row[0] for row in db.session.query(Appointment.appointment_time).filter(
            Appointment.appointment_date == today,
            Appointment.status.in_(['pending', 'approved', 'confirmed'])
        ).all()
        if row[0]
    }

    popular_rows = db.session.query(
        Appointment.appointment_time,
        func.count(Appointment.id).label('slot_count')
    ).filter(
        Appointment.status.in_(['pending', 'approved', 'confirmed', 'completed']),
        Appointment.appointment_time.isnot(None)
    ).group_by(Appointment.appointment_time).order_by(
        func.count(Appointment.id).desc()
    ).limit(20).all()

    suggestions = []
    for slot, slot_count in popular_rows:
        if slot in busy_today:
            continue
        suggestions.append({'time': slot, 'popularity': int(slot_count or 0)})
        if len(suggestions) >= limit:
            break

    if len(suggestions) < limit:
        fallback_slots = ['09:00 AM', '10:00 AM', '11:00 AM', '02:00 PM', '04:00 PM']
        existing = {s['time'] for s in suggestions}
        for slot in fallback_slots:
            if slot in busy_today or slot in existing:
                continue
            suggestions.append({'time': slot, 'popularity': 0})
            if len(suggestions) >= limit:
                break

    return suggestions[:limit]


def get_patient_activity_status(patient_id):
    """Return reminder text based on patient's booking recency."""
    last_appointment = Appointment.query.filter_by(patient_id=patient_id).order_by(
        Appointment.appointment_date.desc()
    ).first()

    if not last_appointment:
        return 'You have not booked any appointment yet. Consider scheduling your first health checkup.'

    if not last_appointment.appointment_date:
        return None

    days_since = (date.today() - last_appointment.appointment_date).days
    if days_since >= 90:
        return f'It has been {days_since} days since your last visit. A routine follow-up is recommended.'
    if days_since >= 45:
        return f'It has been {days_since} days since your last appointment. Consider booking a preventive checkup.'
    return None


app = Flask(__name__)
app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = MAX_REPORT_FILE_SIZE

# Trust one reverse proxy hop so URL generation and security attributes use HTTPS.
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

cache = Cache(config={'CACHE_TYPE': 'SimpleCache'}) if Cache else None
if cache:
    cache.init_app(app)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


@app.errorhandler(413)
def request_entity_too_large(_error):
    if request.path.startswith('/appointment/') and request.path.endswith('/prescription'):
        return jsonify({'success': False, 'message': 'File size exceeds 5MB limit.'}), 413
    flash('Uploaded file is too large. Maximum allowed size is 5MB.', 'danger')
    return redirect(url_for('user_dashboard'))


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Resource not found'}), 404
    return render_template('index.html'), 404


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f'Unhandled server error: {error}')
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Internal server error'}), 500
    flash('Something went wrong. Please try again.', 'danger')
    return redirect(url_for('index'))


@app.after_request
def add_static_cache_headers(response):
    if request.path.startswith('/static/'):
        response.headers.setdefault('Cache-Control', 'public, max-age=604800')
    elif request.path.startswith('/uploads/'):
        response.headers.setdefault('Cache-Control', 'public, max-age=86400')
    return response


@app.context_processor
def inject_notification_context():
    """Provide navbar notification badge + latest items for authenticated users."""
    if not current_user.is_authenticated:
        return {'nav_unread_count': 0, 'nav_notifications': []}

    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    latest = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(5).all()

    return {
        'nav_unread_count': unread_count,
        'nav_notifications': latest
    }

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Create tables
with app.app_context():
    db.create_all()

    # Ensure uploads directory exists
    uploads_dir = os.path.join(app.instance_path, 'uploads')
    os.makedirs(uploads_dir, exist_ok=True)
    

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            if user.user_type == 'deactivated':
                flash('Your account has been deactivated. Please contact support.', 'danger')
                return redirect(url_for('login'))

            login_user(user, remember='remember' in request.form)
            try:
                log_action(user, 'login', target_type='user', target_id=user.id)
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                app.logger.warning(f'Failed to write audit log for login user={user.id}: {exc}')

            next_page = request.args.get('next')
            
            if user.user_type == 'admin':
                return redirect(next_page or url_for('admin_dashboard'))
            elif user.user_type == 'doctor':
                return redirect(next_page or url_for('doctor_dashboard'))
            else:
                return redirect(next_page or url_for('user_dashboard'))
        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        phone = request.form.get('phone')
        # Fix: Get user_type from 'role' field in the form
        user_type = request.form.get('role') or request.form.get('user_type', 'patient')
        # Convert 'user' to 'patient' for consistency
        if user_type == 'user':
            user_type = 'patient'
        # Doctor-specific fields
        specialization = request.form.get('specialization')
        qualifications = request.form.get('qualifications')
        experience = request.form.get('experience')
        consultation_fee = request.form.get('consultation_fee')
        available_days = request.form.get('available_days')
        available_time = request.form.get('available_time')
        
        valid_roles = {'patient', 'doctor', 'admin'}
        if user_type not in valid_roles:
            user_type = 'patient'
        
        # Debug logging
        print(f"DEBUG SIGNUP: user_type = '{user_type}'")
        
        # Validation
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('signup'))
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return redirect(url_for('signup'))
        
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            phone=phone,
            user_type=user_type
        )
        
        # If doctor, create linked Doctor profile
        if user_type == 'doctor':
            print(f"DEBUG: Creating doctor profile for {username}")
            doctor = Doctor(
                name=username,
                specialization=specialization or 'General',
                qualifications=qualifications or '',
                experience=int(experience) if experience else 0,
                phone=phone,
                email=email,
                consultation_fee=float(consultation_fee) if consultation_fee else 0.0,
                available_days=available_days or '',
                available_time=available_time or '',
                is_available=True
            )
            db.session.add(doctor)
            db.session.flush()
            new_user.doctor_id = doctor.id
            print(f"DEBUG: Doctor created with ID {doctor.id}, linked to user")
        
        db.session.add(new_user)
        db.session.commit()
        
        success_msg = f"Registration successful as {user_type}! Please login."
        flash(success_msg, 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    user_for_log = current_user if current_user.is_authenticated else None
    try:
        log_action(user_for_log, 'logout', target_type='user', target_id=getattr(user_for_log, 'id', None))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.warning(f'Failed to write audit log for logout: {exc}')

    logout_user()
    return redirect(url_for('index'))

@app.route('/doctors')
def doctors():
    specialization = request.args.get('specialization')
    search = request.args.get('search')

    cache_key = f"doctors:{specialization or 'all'}:{search or ''}"
    if cache:
        cached_payload = cache.get(cache_key)
        if cached_payload:
            return render_template('doctors.html', **cached_payload)
    
    query = Doctor.query.filter_by(is_available=True)
    
    if specialization and specialization != 'all':
        query = query.filter_by(specialization=specialization)
    
    if search:
        query = query.filter(Doctor.name.ilike(f'%{search}%'))
    
    doctors_list = query.limit(100).all()
    specializations = db.session.query(Doctor.specialization).distinct().limit(100).all()

    doctor_ids = [doc.id for doc in doctors_list]
    rating_map = {}
    if doctor_ids:
        rating_rows = db.session.query(
            Feedback.doctor_id,
            func.avg(Feedback.rating).label('avg_rating'),
            func.count(Feedback.id).label('review_count')
        ).filter(Feedback.doctor_id.in_(doctor_ids)).group_by(Feedback.doctor_id).all()
        rating_map = {
            row.doctor_id: {
                'average_rating': round(float(row.avg_rating or 0), 1),
                'total_reviews': int(row.review_count or 0)
            }
            for row in rating_rows
        }

    doctors_with_ratings = [
        {
            'doctor': doc,
            'average_rating': rating_map.get(doc.id, {}).get('average_rating', 0),
            'total_reviews': rating_map.get(doc.id, {}).get('total_reviews', 0)
        }
        for doc in doctors_list
    ]

    payload = {
        'doctors_with_ratings': doctors_with_ratings,
        'specializations': [s[0] for s in specializations]
    }
    if cache:
        cache.set(cache_key, payload, timeout=300)

    return render_template('doctors.html', **payload)

@app.route('/book-appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    if current_user.user_type == 'admin':
        flash('Admins cannot book appointments', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    doctor = Doctor.query.get_or_404(doctor_id)
    
    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date', '').strip()
        appointment_time = request.form.get('appointment_time', '').strip()
        symptoms = request.form.get('symptoms', '').strip()

        # --- Validate date ---
        try:
            appt_date_obj = datetime.strptime(appointment_date, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            flash('Invalid date format. Please select a valid date.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

        if appt_date_obj < date.today():
            flash('Cannot book an appointment in the past.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

        # --- Validate time via slot engine ---
        available = generate_available_slots(doctor_id, appt_date_obj)
        valid_values = {s['value'] for s in available}
        # Also accept legacy 12-hour format stored in DB: normalise submitted time
        submitted_value = appointment_time
        if not submitted_value:
            flash('Please select a time slot.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

        if available and submitted_value not in valid_values:
            flash('Selected time slot is not available. Please choose from the list.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

        # --- Double-booking prevention (pending + approved + confirmed) ---
        existing_appointment = Appointment.query.filter(
            Appointment.doctor_id == doctor_id,
            Appointment.appointment_date == appt_date_obj,
            Appointment.appointment_time == submitted_value,
            Appointment.status.in_(['pending', 'approved', 'confirmed'])
        ).first()

        if existing_appointment:
            flash('This time slot is already booked. Please choose another.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

        # --- Create appointment (status always starts as 'pending') ---
        try:
            appointment = Appointment(
                patient_id=current_user.id,
                doctor_id=doctor_id,
                appointment_date=appt_date_obj,
                appointment_time=submitted_value,
                symptoms=symptoms,
                status='pending'
            )
            db.session.add(appointment)
            db.session.flush()

            log_action(current_user, 'appointment_created', target_type='appointment', target_id=appointment.id)

            appointment_day = appt_date_obj.strftime('%b %d, %Y')
            create_notification(
                current_user.id,
                'Appointment Booked',
                f'Your appointment request with Dr. {doctor.name} for {appointment_day} at {submitted_value} is pending approval.',
                notification_type='appointment',
                related_id=appointment.id
            )

            doctor_user = User.query.filter_by(user_type='doctor', doctor_id=doctor_id).first()
            if doctor_user:
                create_notification(
                    doctor_user.id,
                    'New Appointment Request',
                    f'{current_user.username} booked an appointment for {appointment_day} at {submitted_value}.',
                    notification_type='appointment',
                    related_id=appointment.id,
                    send_email=True
                )

            db.session.commit()
            flash('Appointment booked successfully! Awaiting doctor approval.', 'success')
            return redirect(url_for('user_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash('Failed to book appointment. Please try again.', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))

    # --- GET: pass today's slots to pre-populate if user picks today ---
    return render_template('appointments.html',
                           doctor=doctor,
                           min_date=date.today())

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.user_type == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.user_type == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    
    appointments = Appointment.query.options(
        joinedload(Appointment.doctor)
    ).filter_by(
        patient_id=current_user.id
    ).order_by(Appointment.appointment_date.desc()).all()

    # Fill presentation fields expected by the existing dashboard template.
    for appt in appointments:
        appt.doctor_name = f"Dr. {appt.doctor.name}" if appt.doctor else 'Doctor'
        appt.specialization = appt.doctor.specialization if appt.doctor else None

    completed_tasks = sum(1 for appt in appointments if appt.status in {'completed'})
    total_tasks = len(appointments)

    assigned_doctor = None
    for appt in appointments:
        if appt.doctor:
            assigned_doctor = appt.doctor
            break

    recommended_doctors = get_recommended_doctors(current_user.id, limit=3)
    suggested_time_slots = get_best_time_slots(limit=5)
    health_reminder = get_patient_activity_status(current_user.id)
    
    # Get feedback data for appointments
    appointment_ids = [appt.id for appt in appointments]
    feedback_rows = Feedback.query.filter(Feedback.appointment_id.in_(appointment_ids)).all() if appointment_ids else []
    feedback_dict = {row.appointment_id: row for row in feedback_rows}
    
    return render_template(
        'user_new.html',
        appointments=appointments,
        feedback_dict=feedback_dict,
        completed_tasks=completed_tasks,
        total_tasks=total_tasks,
        assigned_doctor=assigned_doctor,
        recommended_doctors=recommended_doctors,
        suggested_time_slots=suggested_time_slots,
        health_reminder=health_reminder
    )

@app.route('/submit-feedback/<int:appointment_id>', methods=['POST'])
@login_required
def submit_feedback(appointment_id):
    if current_user.user_type != 'patient':
        return jsonify({'success': False, 'message': 'Only patients can submit feedback'})
    
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Verify this is the patient's appointment
    if appointment.patient_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    # Check if appointment is completed
    if appointment.status != 'completed':
        return jsonify({'success': False, 'message': 'Can only provide feedback for completed appointments'})
    
    # Check if feedback already exists
    existing_feedback = Feedback.query.filter_by(appointment_id=appointment_id).first()
    if existing_feedback:
        return jsonify({'success': False, 'message': 'Feedback already submitted for this appointment'})
    
    try:
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment', '').strip()
        
        if rating < 1 or rating > 5:
            return jsonify({'success': False, 'message': 'Rating must be between 1 and 5 stars'})
        
        feedback = Feedback(
            appointment_id=appointment_id,
            patient_id=current_user.id,
            doctor_id=appointment.doctor_id,
            rating=rating,
            comment=comment
        )
        
        db.session.add(feedback)
        db.session.commit()
        
        flash('Thank you for your feedback!', 'success')
        return jsonify({'success': True, 'message': 'Feedback submitted successfully!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/doctor/dashboard')
@login_required
def doctor_dashboard():
    if current_user.user_type != 'doctor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get doctor's profile
    doctor = Doctor.query.get(current_user.doctor_id)
    
    # Get today's appointments
    today = date.today()
    today_appointments = Appointment.query.options(
        joinedload(Appointment.patient)
    ).filter_by(
        doctor_id=doctor.id,
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.options(
        joinedload(Appointment.patient)
    ).filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date > today,
        Appointment.status != 'cancelled'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(10).all()
    
    # Get all appointments for statistics
    all_appointments = Appointment.query.with_entities(Appointment.status).filter_by(doctor_id=doctor.id).all()
    total_appointments = len(all_appointments)
    pending_count = sum(1 for status, in all_appointments if status == 'pending')
    confirmed_count = sum(1 for status, in all_appointments if status == 'confirmed')
    completed_count = sum(1 for status, in all_appointments if status == 'completed')
    
    # Get feedback statistics
    all_feedback = Feedback.query.with_entities(Feedback.rating).filter_by(doctor_id=doctor.id).all()
    if all_feedback:
        average_rating = sum([f[0] for f in all_feedback]) / len(all_feedback)
        total_reviews = len(all_feedback)
    else:
        average_rating = 0
        total_reviews = 0
    
    return render_template('doctor.html',
                         doctor=doctor,
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_appointments=total_appointments,
                         pending_count=pending_count,
                         confirmed_count=confirmed_count,
                         completed_count=completed_count,
                         average_rating=average_rating,
                         total_reviews=total_reviews,
                         today=today)

@app.route('/admin/dashboard')
@app.route('/admin-dashboard')
@login_required
def admin_dashboard():
    if current_user.user_type != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))

    def _last_n_days(n):
        today = date.today()
        return [today - timedelta(days=offset) for offset in range(n - 1, -1, -1)]

    def _appointments_by_day_last_7_days():
        days = _last_n_days(7)
        rows = db.session.query(
            Appointment.appointment_date.label('appt_day'),
            func.count(Appointment.id).label('count')
        ).filter(
            Appointment.appointment_date >= days[0],
            Appointment.appointment_date <= days[-1]
        ).group_by(Appointment.appointment_date).all()

        counts = {row.appt_day: row.count for row in rows}
        return {
            'labels': [d.strftime('%a') for d in days],
            'values': [int(counts.get(d, 0)) for d in days]
        }

    def _status_breakdown():
        status_row = db.session.query(
            func.sum(case((Appointment.status == 'pending', 1), else_=0)).label('pending_count'),
            func.sum(case((Appointment.status.in_(['approved', 'confirmed']), 1), else_=0)).label('approved_count'),
            func.sum(case((Appointment.status == 'rejected', 1), else_=0)).label('rejected_count')
        ).first()

        return {
            'pending': int(status_row.pending_count or 0),
            'approved': int(status_row.approved_count or 0),
            'rejected': int(status_row.rejected_count or 0)
        }

    def _top_doctors(limit=5):
        rows = db.session.query(
            Doctor.name.label('doctor_name'),
            func.count(Appointment.id).label('appointment_count')
        ).outerjoin(
            Appointment, Appointment.doctor_id == Doctor.id
        ).group_by(
            Doctor.id, Doctor.name
        ).order_by(
            func.count(Appointment.id).desc(), Doctor.name.asc()
        ).limit(limit).all()

        return {
            'labels': [row.doctor_name for row in rows],
            'values': [int(row.appointment_count) for row in rows]
        }

    def _new_users_last_7_days():
        days = _last_n_days(7)
        start_dt = datetime.combine(days[0], datetime.min.time())
        end_dt = datetime.combine(days[-1], datetime.max.time())

        rows = db.session.query(
            func.date(User.created_at).label('created_day'),
            func.count(User.id).label('count')
        ).filter(
            User.created_at >= start_dt,
            User.created_at <= end_dt
        ).group_by(func.date(User.created_at)).all()

        counts = {}
        for row in rows:
            day_text = str(row.created_day)
            try:
                day_key = datetime.strptime(day_text, '%Y-%m-%d').date()
            except ValueError:
                continue
            counts[day_key] = row.count

        values = [int(counts.get(d, 0)) for d in days]
        return {
            'labels': [d.strftime('%a') for d in days],
            'values': values,
            'total': int(sum(values))
        }

    analytics_key = 'admin:analytics:v1'
    analytics_bundle = cache.get(analytics_key) if cache else None
    if not analytics_bundle:
        # Summary metrics
        total_patients = User.query.filter_by(user_type='patient').count()
        total_doctors = Doctor.query.count()
        total_appointments = Appointment.query.count()
        pending_appointments = Appointment.query.filter_by(status='pending').count()

        # Dashboard datasets
        appointments_trend = _appointments_by_day_last_7_days()
        status_breakdown = _status_breakdown()
        top_doctors = _top_doctors(limit=5)
        new_users_trend = _new_users_last_7_days()

        analytics_bundle = {
            'total_patients': total_patients,
            'total_doctors': total_doctors,
            'total_appointments': total_appointments,
            'pending_appointments': pending_appointments,
            'appointments_trend': appointments_trend,
            'status_breakdown': status_breakdown,
            'top_doctors': top_doctors,
            'new_users_trend': new_users_trend
        }
        if cache:
            cache.set(analytics_key, analytics_bundle, timeout=600)

    total_patients = analytics_bundle['total_patients']
    total_doctors = analytics_bundle['total_doctors']
    total_appointments = analytics_bundle['total_appointments']
    pending_appointments = analytics_bundle['pending_appointments']
    appointments_trend = analytics_bundle['appointments_trend']
    status_breakdown = analytics_bundle['status_breakdown']
    top_doctors = analytics_bundle['top_doctors']
    new_users_trend = analytics_bundle['new_users_trend']

    # Existing page data (kept for backward compatibility with current admin template)
    recent_appointments = Appointment.query.options(
        joinedload(Appointment.patient),
        joinedload(Appointment.doctor)
    ).order_by(
        Appointment.appointment_date.desc(), Appointment.appointment_time.desc()
    ).limit(10).all()

    users = User.query.order_by(User.created_at.desc()).all()
    normalized_users = []
    doctor_rows = Doctor.query.with_entities(
        Doctor.id,
        Doctor.specialization,
        Doctor.qualifications,
        Doctor.experience,
        Doctor.consultation_fee,
        Doctor.available_days,
        Doctor.available_time
    ).all()
    doctor_map = {
        row.id: {
            'specialization': row.specialization,
            'qualifications': row.qualifications,
            'experience': row.experience,
            'consultation_fee': row.consultation_fee,
            'available_days': row.available_days,
            'available_time': row.available_time,
        }
        for row in doctor_rows
    }
    for user in users:
        role = 'user' if user.user_type == 'patient' else user.user_type
        doctor_profile = doctor_map.get(user.doctor_id) if user.doctor_id else None
        normalized_users.append({
            'username': user.username,
            'email': user.email,
            'phone': user.phone,
            'role': role,
            'fullname': user.username,
            'age': None,
            'gender': None,
            'address': user.address,
            'blood_group': None,
            'medical_history': None,
            'emergency_contact': None,
            'specialization': doctor_profile['specialization'] if doctor_profile else '',
            'qualifications': doctor_profile['qualifications'] if doctor_profile else '',
            'experience': doctor_profile['experience'] if doctor_profile else '',
            'consultation_fee': doctor_profile['consultation_fee'] if doctor_profile else '',
            'available_days': doctor_profile['available_days'] if doctor_profile else '',
            'available_time': doctor_profile['available_time'] if doctor_profile else ''
        })

    # Audit log filters (admin-only) and limited recent result set
    role_filter = request.args.get('role', '').strip().lower()
    action_filter = request.args.get('action', '').strip()

    audit_query = AuditLog.query.order_by(AuditLog.timestamp.desc())
    if role_filter in {'admin', 'doctor', 'patient'}:
        audit_query = audit_query.filter(AuditLog.role == role_filter)
    if action_filter:
        audit_query = audit_query.filter(AuditLog.action == action_filter)

    recent_audit_logs = audit_query.limit(20).all()
    audit_actions = [
        row[0] for row in db.session.query(AuditLog.action)
        .distinct()
        .order_by(AuditLog.action.asc())
        .limit(100)
        .all()
    ]

    return render_template(
        'admin.html',
        total_patients=total_patients,
        total_doctors=total_doctors,
        total_appointments=total_appointments,
        pending_appointments=pending_appointments,
        recent_appointments=recent_appointments,
        users=normalized_users,
        audit_logs=recent_audit_logs,
        audit_role_filter=role_filter,
        audit_action_filter=action_filter,
        audit_action_options=audit_actions,
        analytics={
            'appointments_trend': appointments_trend,
            'status_breakdown': status_breakdown,
            'top_doctors': top_doctors,
            'new_users_trend': new_users_trend
        }
    )

@app.route('/admin/appointments')
@login_required
def manage_appointments():
    if current_user.user_type != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    appointments = Appointment.query.order_by(
        Appointment.appointment_date.desc()
    ).all()
    
    # Pass date context for template helpers (used in bookings.html)
    return render_template('bookings.html', appointments=appointments, today=date.today())

@app.route('/admin/update-appointment/<int:appointment_id>', methods=['POST'])
@login_required
def update_appointment(appointment_id):
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})

    appointment = Appointment.query.get_or_404(appointment_id)
    old_status = appointment.status
    new_status = request.form.get('status', '').strip().lower()

    if new_status not in VALID_STATUSES:
        return jsonify({'success': False, 'message': f'Invalid status: {new_status}'})

    ok, err = validate_transition(appointment, new_status, 'admin')
    if not ok:
        return jsonify({'success': False, 'message': err})

    try:
        appointment.status = new_status
        appointment.updated_at = datetime.utcnow()

        if new_status in {'approved', 'rejected'}:
            log_action(current_user, f'appointment_{new_status}', target_type='appointment', target_id=appointment.id)
        else:
            log_action(current_user, 'appointment_status_updated', target_type='appointment', target_id=appointment.id)

        if old_status != new_status:
            create_notification(
                appointment.patient_id,
                'Appointment Status Updated',
                f'Appointment #{appointment.id} status changed from {old_status.title()} to {new_status.title()}.',
                notification_type='appointment',
                related_id=appointment.id,
                send_email=True
            )

        db.session.commit()
        flash(f'Appointment status updated to {new_status.title()}.', 'success')
        return jsonify({'success': True, 'message': f'Status updated to {new_status}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'})

@app.route('/admin/add-doctor', methods=['POST'])
@login_required
def add_doctor():
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        name = request.form.get('name')
        
        # Validate required fields
        if not username or not email or not password or not name:
            return jsonify({'success': False, 'message': 'Username, email, password, and name are required'})
        
        # Check if username or email already exists
        if User.query.filter_by(username=username).first():
            return jsonify({'success': False, 'message': 'Username already exists'})
        
        if User.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'Email already registered'})
        
        # Create Doctor profile first
        doctor = Doctor(
            name=name,
            specialization=request.form.get('specialization'),
            qualifications=request.form.get('qualifications'),
            experience=int(request.form.get('experience', 0)),
            phone=request.form.get('phone'),
            email=email,
            consultation_fee=float(request.form.get('consultation_fee', 0)),
            available_days=request.form.get('available_days'),
            available_time=request.form.get('available_time'),
            is_available=True
        )
        
        db.session.add(doctor)
        db.session.flush()  # Get the doctor ID
        
        # Create User account linked to Doctor
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            phone=request.form.get('phone'),
            user_type='doctor',
            doctor_id=doctor.id
        )
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'Doctor {name} added successfully! Login credentials: {username}', 'success')
        return jsonify({'success': True, 'message': f'Doctor added successfully! Username: {username}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/update-doctor/<int:doctor_id>', methods=['POST'])
@login_required
def update_doctor(doctor_id):
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})

    doctor = Doctor.query.get_or_404(doctor_id)

    try:
        doctor.name = request.form.get('name', doctor.name)
        doctor.specialization = request.form.get('specialization', doctor.specialization)
        doctor.qualifications = request.form.get('qualifications', doctor.qualifications)
        doctor.experience = int(request.form.get('experience', doctor.experience or 0))
        doctor.phone = request.form.get('phone', doctor.phone)
        doctor.email = request.form.get('email', doctor.email)
        doctor.consultation_fee = float(request.form.get('consultation_fee', doctor.consultation_fee or 0))
        doctor.available_days = request.form.get('available_days', doctor.available_days)
        doctor.available_time = request.form.get('available_time', doctor.available_time)

        db.session.commit()
        return jsonify({'success': True, 'message': 'Doctor updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete-doctor/<int:doctor_id>', methods=['POST'])
@login_required
def delete_doctor(doctor_id):
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})

    doctor = Doctor.query.get_or_404(doctor_id)

    try:
        # Admin has full access to delete doctors regardless of appointments
        # Delete all appointments associated with this doctor
        existing_appointments = Appointment.query.filter_by(doctor_id=doctor_id).all()
        for appointment in existing_appointments:
            db.session.delete(appointment)

        # Remove linked doctor user accounts
        doctor_users = User.query.filter_by(doctor_id=doctor_id).all()
        for user in doctor_users:
            db.session.delete(user)

        # Delete the doctor
        db.session.delete(doctor)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Doctor and all associated appointments removed successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error deleting doctor: {str(e)}'})

@app.route('/api/available-slots/<int:doctor_id>')
def available_slots(doctor_id):
    """Return available time slots for a doctor on a given date.
    Used by the booking form AJAX call when the user picks a date.
    """
    date_str = request.args.get('date', '').strip()
    if not date_str:
        return jsonify({'error': 'Date required'}), 400

    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD.'}), 400

    if selected_date < date.today():
        return jsonify({'slots': [], 'message': 'Cannot book past dates.'})

    # Check doctor exists
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({'error': 'Doctor not found'}), 404

    slots = generate_available_slots(doctor_id, selected_date)
    return jsonify({
        'slots': slots,                          # list of {value, label}
        'available': len(slots) > 0,
        'doctor_id': doctor_id,
        'date': date_str
    })

# ---------------------------------------------------------------------------
# ADMIN — Doctor Availability Schedule CRUD
# ---------------------------------------------------------------------------

@app.route('/admin/doctor-availability/<int:doctor_id>', methods=['GET'])
@login_required
def admin_get_availability(doctor_id):
    """Return the current availability schedule for a doctor as JSON."""
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    rows = DoctorAvailability.query.filter_by(doctor_id=doctor_id).all()
    schedule = [
        {
            'id': r.id,
            'day_of_week': r.day_of_week,
            'start_time': r.start_time,
            'end_time': r.end_time,
            'slot_duration': r.slot_duration,
            'is_active': r.is_active
        }
        for r in rows
    ]
    return jsonify({'success': True, 'schedule': schedule, 'doctor_id': doctor_id})


@app.route('/admin/doctor-availability', methods=['POST'])
@login_required
def admin_set_availability():
    """Create or update a single day's availability for a doctor.

    POST body params:
        doctor_id, day_of_week, start_time (HH:MM 24h),
        end_time (HH:MM 24h), slot_duration (15/30/45/60), is_active (bool string)
    """
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    VALID_DAYS = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'}
    VALID_DURATIONS = {15, 30, 45, 60}

    try:
        doctor_id     = int(request.form.get('doctor_id', 0))
        day           = request.form.get('day_of_week', '').strip().title()
        start_time    = request.form.get('start_time', '').strip()
        end_time      = request.form.get('end_time', '').strip()
        slot_duration = int(request.form.get('slot_duration', 30))
        is_active     = request.form.get('is_active', 'true').lower() != 'false'

        if not doctor_id or not Doctor.query.get(doctor_id):
            return jsonify({'success': False, 'message': 'Invalid doctor_id'}), 400
        if day not in VALID_DAYS:
            return jsonify({'success': False, 'message': f'Invalid day. Use full name e.g. Monday.'}), 400
        if slot_duration not in VALID_DURATIONS:
            return jsonify({'success': False, 'message': 'slot_duration must be 15, 30, 45, or 60'}), 400

        for label, t in [('start_time', start_time), ('end_time', end_time)]:
            try:
                datetime.strptime(t, '%H:%M')
            except ValueError:
                return jsonify({'success': False, 'message': f'{label} must be HH:MM (24-hour)'}), 400

        sh, sm = _parse_hhmm(start_time)
        eh, em = _parse_hhmm(end_time)
        if (sh, sm) >= (eh, em):
            return jsonify({'success': False, 'message': 'start_time must be before end_time'}), 400

        existing = DoctorAvailability.query.filter_by(
            doctor_id=doctor_id, day_of_week=day
        ).first()
        if existing:
            existing.start_time    = start_time
            existing.end_time      = end_time
            existing.slot_duration = slot_duration
            existing.is_active     = is_active
        else:
            db.session.add(DoctorAvailability(
                doctor_id=doctor_id, day_of_week=day,
                start_time=start_time, end_time=end_time,
                slot_duration=slot_duration, is_active=is_active
            ))

        db.session.commit()
        return jsonify({'success': True, 'message': f'Availability for {day} saved.'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error: {str(e)}'}), 500


@app.route('/admin/doctor-availability/<int:doctor_id>/<int:avail_id>', methods=['DELETE'])
@login_required
def admin_delete_availability(doctor_id, avail_id):
    """Delete a single DoctorAvailability row."""
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403
    try:
        row = DoctorAvailability.query.filter_by(
            id=avail_id, doctor_id=doctor_id
        ).first_or_404()
        db.session.delete(row)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Availability row deleted.'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# DOCTOR — View Own Availability Schedule
# ---------------------------------------------------------------------------

@app.route('/doctor/my-availability', methods=['GET'])
@login_required
def doctor_my_availability():
    """Return this doctor's active schedule as JSON (for display on dashboard)."""
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    doctor = Doctor.query.get(current_user.doctor_id)
    if not doctor:
        return jsonify({'success': False, 'message': 'Doctor profile not found'}), 404

    rows = DoctorAvailability.query.filter_by(
        doctor_id=doctor.id, is_active=True
    ).all()
    schedule = [
        {
            'day_of_week':   r.day_of_week,
            'start_time':    r.start_time,
            'end_time':      r.end_time,
            'slot_duration': r.slot_duration
        }
        for r in rows
    ]
    return jsonify({'success': True, 'schedule': schedule, 'doctor_id': doctor.id})


# ===========================================================================
# MEDICAL RECORD / PRESCRIPTION ROUTES
# ===========================================================================


def _serialize_reports_for_appointment(appointment_id):
    reports = Report.query.filter_by(appointment_id=appointment_id).order_by(Report.uploaded_at.desc()).all()
    return [
        {
            'id': r.id,
            'file_name': r.file_name,
            'description': r.description or '',
            'uploaded_at': r.uploaded_at.strftime('%b %d, %Y %I:%M %p'),
            'view_url': url_for('get_report', report_id=r.id),
            'download_url': url_for('get_report', report_id=r.id, download=1)
        }
        for r in reports
    ]

@app.route('/appointment/<int:appointment_id>/prescription', methods=['POST'])
@login_required
def create_prescription(appointment_id):
    """Doctor creates a medical record for a COMPLETED appointment.
    Rules:
    - Caller must be a doctor.
    - Appointment must belong to this doctor.
    - Appointment status must be 'completed'.
    - No duplicate record allowed (unique constraint + pre-flight check).
    """
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Access denied — doctors only.'}), 403

    appointment = Appointment.query.get_or_404(appointment_id)

    # Verify ownership
    doctor = Doctor.query.get(current_user.doctor_id)
    if not doctor or appointment.doctor_id != doctor.id:
        return jsonify({'success': False, 'message': 'This appointment does not belong to you.'}), 403

    # Appointment must be completed
    if appointment.status != 'completed':
        return jsonify({
            'success': False,
            'message': f"Medical records can only be created for completed appointments (current: '{appointment.status}')."
        }), 400

    # Duplicate check
    existing = Prescription.query.filter_by(appointment_id=appointment_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'A medical record already exists for this appointment.'}), 409

    # Validate required fields
    diagnosis    = request.form.get('diagnosis', '').strip()
    prescription = request.form.get('prescription', '').strip()
    notes        = request.form.get('notes', '').strip() or None
    follow_up_str = request.form.get('follow_up_date', '').strip()
    report_description = request.form.get('report_description', '').strip() or None
    report_file = request.files.get('report_file')

    if not diagnosis:
        return jsonify({'success': False, 'message': 'Diagnosis is required.'}), 400
    if not prescription:
        return jsonify({'success': False, 'message': 'Prescription is required.'}), 400

    follow_up_date = None
    if follow_up_str:
        try:
            follow_up_date = datetime.strptime(follow_up_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid follow-up date format (YYYY-MM-DD).'}), 400

    try:
        saved_report = None
        if report_file and report_file.filename:
            saved_report = save_file(report_file, current_user.id)

        rec = Prescription(
            appointment_id = appointment_id,
            patient_id     = appointment.patient_id,
            doctor_user_id = current_user.id,
            diagnosis      = diagnosis,
            prescription   = prescription,
            notes          = notes,
            follow_up_date = follow_up_date,
        )
        db.session.add(rec)
        db.session.flush()

        log_action(current_user, 'medical_record_created', target_type='record', target_id=rec.id)

        if saved_report:
            db.session.add(Report(
                patient_id=appointment.patient_id,
                doctor_id=doctor.id,
                appointment_id=appointment.id,
                prescription_id=rec.id,
                file_name=saved_report['file_name'],
                file_path=saved_report['file_path'],
                description=report_description
            ))

        create_notification(
            appointment.patient_id,
            'Medical Record Available',
            f'A new medical record was added for appointment #{appointment.id}.',
            notification_type='medical',
            related_id=appointment.id,
            send_email=True
        )

        db.session.commit()
        payload = rec.to_dict()
        payload['reports'] = _serialize_reports_for_appointment(appointment_id)
        return jsonify({'success': True, 'message': 'Medical record created successfully.', 'record': payload})
    except ValueError as exc:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(exc)}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error creating prescription for appt {appointment_id}: {e}')
        return jsonify({'success': False, 'message': 'Failed to save record. Please try again.'}), 500


@app.route('/appointment/<int:appointment_id>/prescription', methods=['GET'])
@login_required
def get_prescription(appointment_id):
    """Return the medical record for an appointment as JSON.
    Access:
    - Doctor: only their own appointments.
    - Patient: only their own appointments.
    - Admin: any appointment.
    """
    appointment = Appointment.query.get_or_404(appointment_id)

    # Role-based access
    if current_user.user_type == 'doctor':
        doctor = Doctor.query.get(current_user.doctor_id)
        if not doctor or appointment.doctor_id != doctor.id:
            return jsonify({'success': False, 'message': 'Access denied.'}), 403
        can_edit = appointment.status == 'completed'
    elif current_user.user_type == 'patient':
        if appointment.patient_id != current_user.id:
            return jsonify({'success': False, 'message': 'Access denied.'}), 403
        can_edit = False
    elif current_user.user_type == 'admin':
        can_edit = False
    else:
        return jsonify({'success': False, 'message': 'Access denied.'}), 403

    rec = Prescription.query.filter_by(appointment_id=appointment_id).first()
    payload = rec.to_dict() if rec else None
    if payload is not None:
        payload['reports'] = _serialize_reports_for_appointment(appointment_id)

    return jsonify({
        'success':    True,
        'record':     payload,
        'can_edit':   can_edit and rec is not None,
        'can_create': can_edit and rec is None,
    })


@app.route('/report/<int:report_id>')
@login_required
def get_report(report_id):
    """Securely stream report file (inline view or attachment download) to authorized users only."""
    report = Report.query.get_or_404(report_id)

    is_admin = current_user.user_type == 'admin'
    is_patient_owner = current_user.user_type == 'patient' and report.patient_id == current_user.id
    is_assigned_doctor = current_user.user_type == 'doctor' and current_user.doctor_id == report.doctor_id

    if not (is_admin or is_patient_owner or is_assigned_doctor):
        flash('Access denied.', 'danger')
        return redirect(url_for('user_dashboard'))

    safe_stored_name = os.path.basename(report.file_path or '')
    file_abs_path = os.path.join(app.root_path, 'static', 'uploads', 'reports', safe_stored_name)
    if not os.path.exists(file_abs_path):
        flash('Requested file does not exist.', 'warning')
        return redirect(url_for('user_dashboard'))

    guessed_type = mimetypes.guess_type(report.file_name)[0] or 'application/octet-stream'
    as_download = request.args.get('download', '0') == '1'

    return send_file(
        file_abs_path,
        mimetype=guessed_type,
        as_attachment=as_download,
        download_name=report.file_name
    )


@app.route('/appointment/<int:appointment_id>/prescription', methods=['PATCH'])
@login_required
def update_prescription(appointment_id):
    """Doctor updates an existing medical record (their own appointments only)."""
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Access denied — doctors only.'}), 403

    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.get(current_user.doctor_id)
    if not doctor or appointment.doctor_id != doctor.id:
        return jsonify({'success': False, 'message': 'This appointment does not belong to you.'}), 403

    rec = Prescription.query.filter_by(
        appointment_id=appointment_id,
        doctor_user_id=current_user.id
    ).first()
    if not rec:
        return jsonify({'success': False, 'message': 'No record found to update.'}), 404

    data = request.get_json(silent=True) or {}
    # Also accept form data
    if not data:
        data = request.form.to_dict()

    diagnosis    = data.get('diagnosis', '').strip()
    prescription = data.get('prescription', '').strip()
    notes        = data.get('notes', '').strip() or None
    follow_up_str = data.get('follow_up_date', '').strip()

    if diagnosis:
        rec.diagnosis = diagnosis
    if prescription:
        rec.prescription = prescription
    rec.notes = notes

    if follow_up_str:
        try:
            rec.follow_up_date = datetime.strptime(follow_up_str, '%Y-%m-%d').date()
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid follow-up date format.'}), 400
    elif 'follow_up_date' in data and follow_up_str == '':
        rec.follow_up_date = None

    try:
        db.session.commit()
        return jsonify({'success': True, 'message': 'Medical record updated.', 'record': rec.to_dict()})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Error updating prescription {rec.id}: {e}')
        return jsonify({'success': False, 'message': 'Failed to update record.'}), 500


@app.route('/appointment/<int:appointment_id>/prescription/pdf', methods=['GET'])
@login_required
def download_prescription_pdf(appointment_id):
    """Generate and stream a PDF summary of the medical record.
    Access: patient (own appointment) or admin.
    """
    if current_user.user_type not in ('patient', 'admin'):
        flash('Only patients and admins can download medical records.', 'warning')
        return redirect(url_for('user_dashboard'))

    appointment = Appointment.query.get_or_404(appointment_id)

    # Patient can only download their own
    if current_user.user_type == 'patient' and appointment.patient_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('user_dashboard'))

    rec = Prescription.query.filter_by(appointment_id=appointment_id).first()
    if not rec:
        flash('No medical record found for this appointment.', 'warning')
        return redirect(url_for('user_dashboard'))

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4,
                                rightMargin=2*cm, leftMargin=2*cm,
                                topMargin=2*cm, bottomMargin=2*cm)
        styles = getSampleStyleSheet()
        story  = []

        header_style = ParagraphStyle('Header', parent=styles['Title'],
                                      fontSize=18, textColor=colors.HexColor('#1E3A5F'), spaceAfter=4)
        sub_style    = ParagraphStyle('Sub', parent=styles['Normal'],
                                      fontSize=10, textColor=colors.grey)
        label_style  = ParagraphStyle('Label', parent=styles['Normal'],
                                      fontSize=10, textColor=colors.HexColor('#1E3A5F'),
                                      fontName='Helvetica-Bold', spaceBefore=10)
        value_style  = ParagraphStyle('Value', parent=styles['Normal'],
                                      fontSize=11, leading=15)

        # Header
        story.append(Paragraph('Care 4 U Hospital', header_style))
        story.append(Paragraph('Medical Record / Prescription', sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#1E3A5F'), spaceAfter=10))

        # Appointment info table
        patient_user = User.query.get(appointment.patient_id)
        doctor_user  = User.query.get(rec.doctor_user_id)
        doctor_obj   = appointment.doctor

        info = [
            ['Appointment ID', f'#{appointment.id}',
             'Date', appointment.appointment_date.strftime('%B %d, %Y')],
            ['Patient', patient_user.username if patient_user else '—',
             'Time', appointment.appointment_time],
            ['Doctor', f'Dr. {doctor_obj.name}' if doctor_obj else '—',
             'Specialization', doctor_obj.specialization if doctor_obj else '—'],
            ['Record Created', rec.created_at.strftime('%b %d, %Y %I:%M %p'), '', ''],
        ]
        t = Table(info, colWidths=[3.5*cm, 6*cm, 3.5*cm, 5*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#EEF2FF')),
            ('BACKGROUND', (2,0), (2,-2), colors.HexColor('#EEF2FF')),
            ('FONTNAME',   (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE',   (0,0), (-1,-1), 9),
            ('GRID',       (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('VALIGN',     (0,0), (-1,-1), 'MIDDLE'),
            ('PADDING',    (0,0), (-1,-1), 6),
        ]))
        story.append(t)
        story.append(Spacer(1, 12))

        # Clinical sections
        for label, content in [
            ('Diagnosis',     rec.diagnosis),
            ('Prescription',  rec.prescription),
            ('Notes',         rec.notes or 'None'),
        ]:
            story.append(Paragraph(label, label_style))
            story.append(Paragraph(content.replace('\n', '<br/>'), value_style))

        if rec.follow_up_date:
            story.append(Paragraph('Follow-up Date', label_style))
            story.append(Paragraph(rec.follow_up_date.strftime('%B %d, %Y'), value_style))

        story.append(Spacer(1, 20))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
        story.append(Paragraph(
            f'Generated on {datetime.utcnow().strftime("%B %d, %Y")} — Care 4 U Hospital',
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8,
                           textColor=colors.grey, alignment=TA_CENTER, spaceBefore=6)
        ))

        doc.build(story)
        buffer.seek(0)
        filename = f'medical_record_appointment_{appointment_id}.pdf'
        return Response(
            buffer.read(),
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )

    except ImportError:
        flash('PDF generation is not available (reportlab not installed).', 'warning')
        return redirect(url_for('user_dashboard'))
    except Exception as e:
        app.logger.error(f'PDF generation error for appt {appointment_id}: {e}')
        flash('Failed to generate PDF. Please try again.', 'danger')
        return redirect(url_for('user_dashboard'))


@app.route('/user/upload-document', methods=['POST'])


@login_required
def upload_document():
    if current_user.user_type != 'patient':
        return jsonify({'success': False, 'message': 'Access denied'})

    file = request.files.get('document')
    description = request.form.get('description', '')

    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'No file provided'})

    filename = secure_filename(file.filename)
    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
    dest_dir = os.path.join(app.instance_path, 'uploads', str(current_user.id))
    os.makedirs(dest_dir, exist_ok=True)

    try:
        file_path = os.path.join(dest_dir, safe_name)
        file.save(file_path)
        
        # Get file size and type
        file_size = os.path.getsize(file_path)
        file_type = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'unknown'
        
        # Create medical record entry in database
        medical_record = MedicalRecord(
            patient_id=current_user.id,
            filename=safe_name,
            original_filename=filename,
            description=description,
            file_type=file_type,
            file_size=file_size
        )
        db.session.add(medical_record)
        db.session.flush()
        log_action(current_user, 'file_uploaded', target_type='record', target_id=medical_record.id)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Document uploaded', 'description': description})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/upload-profile-picture', methods=['POST'])
@login_required
def upload_profile_picture():
    """Upload profile picture for user (patient/doctor/admin)"""
    
    # File validation
    if 'profile_picture' not in request.files:
        return jsonify({'success': False, 'message': 'No file provided'})
    
    file = request.files['profile_picture']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    # Allowed image extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    
    # Validate file extension
    if '.' not in file.filename or file.filename.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS:
        return jsonify({'success': False, 'message': 'Only image files are allowed (png, jpg, jpeg, gif, webp)'})
    
    try:
        filename = secure_filename(file.filename)
        safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_profile_{filename}"
        
        # Create directory for profile pictures
        profile_pic_dir = os.path.join(app.instance_path, 'uploads', 'profile_pictures')
        os.makedirs(profile_pic_dir, exist_ok=True)
        
        # Save the file
        file_path = os.path.join(profile_pic_dir, safe_name)
        file.save(file_path)
        _compress_image_inplace(file_path)
        
        # Store the relative path in database
        relative_path = f'profile_pictures/{safe_name}'
        
        # Update user's profile picture
        if current_user.user_type == 'doctor':
            # Update doctor's profile image
            doctor = Doctor.query.get(current_user.doctor_id)
            if doctor:
                doctor.profile_image = relative_path
                log_action(current_user, 'profile_updated', target_type='user', target_id=current_user.id)
                db.session.commit()
                return jsonify({'success': True, 'message': 'Profile picture updated successfully'})
            else:
                return jsonify({'success': False, 'message': 'Doctor profile not found'})
        else:
            # Update user's profile picture (patient or admin)
            current_user.profile_picture = relative_path
            log_action(current_user, 'profile_updated', target_type='user', target_id=current_user.id)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Profile picture updated successfully'})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error uploading file: {str(e)}'})

@app.route('/uploads/profile_pictures/<path:filename>')
def serve_profile_picture(filename):
    """Serve profile pictures from the instance uploads folder"""
    uploads_dir = os.path.join(app.instance_path, 'uploads')
    try:
        return send_from_directory(uploads_dir, f'profile_pictures/{filename}')
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404

@app.route('/cancel-appointment/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)

    # Authorisation: only the owning patient or admin can cancel
    if appointment.patient_id != current_user.id and current_user.user_type != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('user_dashboard'))

    # Enforce transition rules
    role = current_user.user_type
    ok, err = validate_transition(appointment, 'cancelled', role)
    if not ok:
        flash(err, 'danger')
        if role == 'admin':
            return redirect(url_for('manage_appointments'))
        return redirect(url_for('user_dashboard'))

    try:
        appointment.status = 'cancelled'
        appointment.updated_at = datetime.utcnow()

        doctor_user = User.query.filter_by(user_type='doctor', doctor_id=appointment.doctor_id).first()
        if doctor_user:
            create_notification(
                doctor_user.id,
                'Appointment Cancelled',
                f'Appointment #{appointment.id} was cancelled by {current_user.username}.',
                notification_type='appointment',
                related_id=appointment.id,
                send_email=True
            )

        if current_user.user_type == 'admin':
            create_notification(
                appointment.patient_id,
                'Appointment Cancelled by Admin',
                f'Your appointment #{appointment.id} has been cancelled by an administrator.',
                notification_type='appointment',
                related_id=appointment.id,
                send_email=True
            )

        db.session.commit()
        flash('Appointment cancelled successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to cancel appointment. Please try again.', 'danger')

    if current_user.user_type == 'admin':
        return redirect(url_for('manage_appointments'))
    return redirect(url_for('user_dashboard'))

@app.route('/doctor/update-appointment/<int:appointment_id>', methods=['POST'])
@login_required
def doctor_update_appointment(appointment_id):
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Access denied'})

    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.get(current_user.doctor_id)

    if not doctor or appointment.doctor_id != doctor.id:
        return jsonify({'success': False, 'message': 'Access denied'})

    new_status = request.form.get('status', '').strip().lower()
    notes = request.form.get('notes', '').strip()

    if new_status not in VALID_STATUSES:
        return jsonify({'success': False, 'message': f'Invalid status: {new_status}'})

    ok, err = validate_transition(appointment, new_status, 'doctor')
    if not ok:
        return jsonify({'success': False, 'message': err})

    try:
        old_status = appointment.status
        appointment.status = new_status
        appointment.updated_at = datetime.utcnow()
        if notes:
            appointment.notes = notes

        if new_status in {'approved', 'rejected'}:
            log_action(current_user, f'appointment_{new_status}', target_type='appointment', target_id=appointment.id)
        else:
            log_action(current_user, 'appointment_status_updated', target_type='appointment', target_id=appointment.id)

        if old_status != new_status:
            create_notification(
                appointment.patient_id,
                'Appointment Status Updated',
                f'Dr. {doctor.name} changed appointment #{appointment.id} from {old_status.title()} to {new_status.title()}.',
                notification_type='appointment',
                related_id=appointment.id,
                send_email=True
            )

        db.session.commit()
        return jsonify({
            'success': True,
            'message': f'Appointment {new_status.title()} successfully.'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error: {str(e)}'})

@app.route('/doctor/patients')
@login_required
def doctor_patients():
    if current_user.user_type != 'doctor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    doctor = Doctor.query.get(current_user.doctor_id)
    
    # Get all unique patients who have appointments with this doctor
    patient_ids = db.session.query(Appointment.patient_id).filter_by(
        doctor_id=doctor.id
    ).distinct().all()
    
    patient_ids = [pid[0] for pid in patient_ids]
    patients = User.query.filter(User.id.in_(patient_ids)).all()
    
    # Get appointment counts for each patient
    patient_data = []
    for patient in patients:
        appointments = Appointment.query.filter_by(
            patient_id=patient.id,
            doctor_id=doctor.id
        ).all()
        
        patient_data.append({
            'patient': patient,
            'total_appointments': len(appointments),
            'last_appointment': max([a.appointment_date for a in appointments]) if appointments else None,
            'medical_records_count': MedicalRecord.query.filter_by(patient_id=patient.id).count()
        })
    
    return render_template('doctor_patients.html', 
                         doctor=doctor,
                         patient_data=patient_data)

@app.route('/doctor/patient/<int:patient_id>/records')
@login_required
def doctor_view_patient_records(patient_id):
    if current_user.user_type != 'doctor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    doctor = Doctor.query.get(current_user.doctor_id)
    patient = User.query.get_or_404(patient_id)
    
    # Verify that this doctor has treated this patient
    appointment_exists = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).first()
    
    if not appointment_exists:
        flash('You can only view records of your patients', 'danger')
        return redirect(url_for('doctor_patients'))
    
    # Get patient's medical records
    medical_records = MedicalRecord.query.filter_by(
        patient_id=patient_id
    ).order_by(MedicalRecord.upload_date.desc()).all()
    
    # Get patient's appointments with this doctor
    appointments = Appointment.query.filter_by(
        patient_id=patient_id,
        doctor_id=doctor.id
    ).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template('patient_records.html',
                         doctor=doctor,
                         patient=patient,
                         medical_records=medical_records,
                         appointments=appointments)

@app.route('/doctor/download-record/<int:record_id>')
@login_required
def doctor_download_record(record_id):
    if current_user.user_type != 'doctor':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    doctor = Doctor.query.get(current_user.doctor_id)
    medical_record = MedicalRecord.query.get_or_404(record_id)
    
    # Verify that this doctor has treated this patient
    appointment_exists = Appointment.query.filter_by(
        patient_id=medical_record.patient_id,
        doctor_id=doctor.id
    ).first()
    
    if not appointment_exists:
        flash('You can only access records of your patients', 'danger')
        return redirect(url_for('doctor_patients'))
    
    # Construct file path
    upload_dir = os.path.join(app.instance_path, 'uploads', str(medical_record.patient_id))
    
    try:
        return send_from_directory(
            upload_dir, 
            medical_record.filename,
            as_attachment=True,
            download_name=medical_record.original_filename
        )
    except FileNotFoundError:
        flash('File not found', 'danger')
        return redirect(url_for('doctor_view_patient_records', patient_id=medical_record.patient_id))


@app.route('/doctor/update-schedule', methods=['POST'])
@login_required
def doctor_update_schedule():
    """Update doctor availability (schedule, hours, consultation fee)"""
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        doctor = Doctor.query.get(current_user.doctor_id)
        
        # Get form data
        available_days = request.form.get('available_days', '').strip()
        available_time = request.form.get('available_time', '').strip()
        consultation_fee = request.form.get('consultation_fee', '').strip()
        
        # Validate required fields
        if not available_days or not available_time or not consultation_fee:
            return jsonify({'success': False, 'message': 'All schedule fields are required'}), 400
        
        # Validate time format (HH:MM-HH:MM)
        if '-' not in available_time:
            return jsonify({'success': False, 'message': 'Time format should be HH:MM-HH:MM'}), 400
        
        # Validate consultation fee is a number
        try:
            fee = float(consultation_fee)
            if fee < 0:
                return jsonify({'success': False, 'message': 'Consultation fee must be positive'}), 400
        except ValueError:
            return jsonify({'success': False, 'message': 'Invalid consultation fee'}), 400
        
        # Update doctor record
        doctor.available_days = available_days
        doctor.available_time = available_time
        doctor.consultation_fee = fee
        log_action(current_user, 'profile_updated', target_type='user', target_id=current_user.id)
        
        db.session.commit()
        
        app.logger.info(f'Doctor {doctor.name} (ID: {doctor.id}) updated schedule: days={available_days}, time={available_time}, fee={fee}')
        
        return jsonify({
            'success': True,
            'message': 'Schedule updated successfully'
        })
    
    except Exception as exc:
        db.session.rollback()
        app.logger.error(f'Exception updating doctor schedule: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'An error occurred'}), 500


@app.route('/admin/deactivate-user/<int:user_id>', methods=['POST'])
@login_required
def deactivate_user(user_id):
    """Soft-deactivate a non-admin account and notify the user."""
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    user = User.query.get_or_404(user_id)
    if user.user_type == 'admin':
        return jsonify({'success': False, 'message': 'Admin accounts cannot be deactivated'}), 400

    if user.user_type == 'deactivated':
        log_action(current_user, 'user_deactivation_skipped', target_type='user', target_id=user.id)
        db.session.commit()
        return jsonify({'success': True, 'message': 'User is already deactivated'})

    try:
        user.user_type = 'deactivated'
        log_action(current_user, 'user_deactivated', target_type='user', target_id=user.id)
        create_notification(
            user.id,
            'Account Deactivated',
            'Your account has been deactivated by an administrator. Please contact support for help.',
            notification_type='security',
            send_email=True
        )
        db.session.commit()
        return jsonify({'success': True, 'message': 'User account deactivated successfully'})
    except Exception as exc:
        db.session.rollback()
        app.logger.error(f'Failed to deactivate user {user_id}: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to deactivate user'}), 500


@app.route('/admin/activate-user/<int:user_id>', methods=['POST'])
@login_required
def activate_user(user_id):
    """Reactivate a deactivated user (default role patient unless explicit valid role provided)."""
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'}), 403

    user = User.query.get_or_404(user_id)
    restore_role = request.form.get('role', 'patient').strip().lower()
    if restore_role not in {'patient', 'doctor'}:
        restore_role = 'patient'

    if restore_role == 'doctor' and not user.doctor_id:
        restore_role = 'patient'

    try:
        user.user_type = restore_role
        log_action(current_user, 'user_activated', target_type='user', target_id=user.id)
        db.session.commit()
        return jsonify({'success': True, 'message': f'User account activated as {restore_role}.'})
    except Exception as exc:
        db.session.rollback()
        app.logger.error(f'Failed to activate user {user_id}: {exc}', exc_info=True)
        return jsonify({'success': False, 'message': 'Failed to activate user'}), 500


@app.route('/notifications')
@login_required
def notifications_page():
    page = request.args.get('page', 1, type=int)
    per_page = 10

    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page, error_out=False)

    return render_template('notifications.html', notifications=notifications)


@app.route('/notifications/read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)

    if notification.user_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('notifications_page'))

    try:
        notification.is_read = True
        db.session.commit()
        flash('Notification marked as read.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to mark notification as read.', 'danger')

    return redirect(url_for('notifications_page'))


@app.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    try:
        Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
            {'is_read': True}, synchronize_session=False
        )
        db.session.commit()
        flash('All notifications marked as read.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to update notifications.', 'danger')

    return redirect(url_for('notifications_page'))

# AI Health Assistant Chatbot Endpoint
@app.route('/user/chat-assistant', methods=['POST'])
@login_required
def chat_assistant():
    """AI-powered health symptom analyzer and doctor recommendation engine"""
    if current_user.user_type != 'patient':
        return jsonify({'success': False, 'message': 'This feature is for patients only'})
    
    data = request.get_json()
    symptoms = data.get('symptoms', '').lower().strip()
    
    if not symptoms:
        return jsonify({'success': False, 'message': 'Please describe your symptoms'})
    
    # Analyze symptoms using AI-based logic
    analysis = analyze_symptoms(symptoms)
    
    return jsonify({
        'success': True,
        'response': analysis['response'],
        'is_emergency': analysis['is_emergency'],
        'specializations': analysis['specializations'],
        'severity_score': analysis['severity_score']
    })

def analyze_symptoms(symptoms_text):
    """
    AI-based symptom analysis engine
    Detects emergency conditions, suggests specializations, and calculates severity
    """
    symptoms_text_lower = symptoms_text.lower()
    
    # Emergency keyword mapping with weights
    emergency_indicators = {
        'chest pain': 3,
        'heart attack': 5,
        'stroke': 5,
        'seizure': 4,
        'difficulty breathing': 4,
        'shortness of breath': 4,
        'severe bleeding': 5,
        'unconscious': 5,
        'severe allergic': 4,
        'anaphylaxis': 5,
        'poisoning': 5,
        'overdose': 5,
        'severe trauma': 5,
        'severe burns': 5,
        'loss of consciousness': 5,
        'severe head injury': 4,
        'drowning': 5,
        'choking': 4,
        'unable to breathe': 5,
        'severe abdominal pain': 3,
        'rupture': 4,
        'serious injury': 3,
        'bleeding heavily': 4,
        'gunshot': 5,
        'stab wound': 4,
    }
    
    # Specialization mapping with keyword associations
    specialization_map = {
        'Cardiology': {
            'keywords': ['chest pain', 'heart', 'palpitation', 'arrhythmia', 'hypertension', 'blood pressure', 'cardiac', 'angina', 'irregular heartbeat', 'shortness of breath'],
            'base_score': 0
        },
        'Neurology': {
            'keywords': ['headache', 'migraine', 'dizziness', 'stroke', 'seizure', 'tremor', 'nerve', 'neuropathy', 'numbness', 'paralysis', 'vertigo', 'brain'],
            'base_score': 0
        },
        'Orthopedics': {
            'keywords': ['fracture', 'bone', 'joint', 'arthritis', 'back pain', 'knee pain', 'shoulder pain', 'ankle', 'sprain', 'ligament'],
            'base_score': 0
        },
        'Gastroenterology': {
            'keywords': ['stomach', 'abdominal', 'nausea', 'vomiting', 'diarrhea', 'constipation', 'acid reflux', 'heartburn', 'liver', 'digestive', 'intestinal'],
            'base_score': 0
        },
        'Pulmonology': {
            'keywords': ['cough', 'asthma', 'lung', 'bronchitis', 'pneumonia', 'respiratory', 'breathing', 'wheezing', 'shortness of breath', 'tuberculosis'],
            'base_score': 0
        },
        'Dermatology': {
            'keywords': ['rash', 'skin', 'acne', 'eczema', 'psoriasis', 'mole', 'wart', 'itching', 'fungal', 'allergy'],
            'base_score': 0
        },
        'Ophthalmology': {
            'keywords': ['eye', 'vision', 'blind', 'blurred', 'eye pain', 'glaucoma', 'cataract', 'contact lens', 'glasses'],
            'base_score': 0
        },
        'ENT (Otolaryngology)': {
            'keywords': ['ear', 'nose', 'throat', 'hearing', 'tinnitus', 'sinus', 'sinusitis', 'sore throat', 'hoarse', 'vertigo'],
            'base_score': 0
        },
        'Pediatrics': {
            'keywords': ['baby', 'child', 'infant', 'kid', 'vaccination', 'fever', 'crying', 'development', 'growth'],
            'base_score': 0
        },
        'Psychiatry': {
            'keywords': ['depression', 'anxiety', 'stress', 'panic', 'mental', 'psychological', 'emotional', 'insomnia', 'sleep', 'mood'],
            'base_score': 0
        }
    }
    
    # Check emergency conditions with AI-based reasoning
    emergency_score = 0
    emergency_reasons = []
    
    for emergency_keyword, weight in emergency_indicators.items():
        if emergency_keyword in symptoms_text_lower:
            emergency_score += weight
            emergency_reasons.append(emergency_keyword)
    
    # AI emergency detection logic (not just keywords)
    # Check for multiple critical indicators
    is_emergency = emergency_score >= 4
    
    # Additional AI logic: context analysis
    critical_phrases = ['severe', 'sudden', 'critical', 'emergency', 'urgent', 'immediate']
    has_critical_modifier = any(phrase in symptoms_text_lower for phrase in critical_phrases)
    
    if has_critical_modifier and emergency_score >= 2:
        is_emergency = True
    
    # Calculate severity score (0-100)
    severity_score = min(emergency_score * 15, 100)
    if symptoms_text_lower.count(' ') > 10:  # More detailed symptoms
        severity_score = min(severity_score + 10, 100)
    
    # Match specializations based on symptom keywords
    matching_specializations = []
    
    for specialty, info in specialization_map.items():
        keyword_matches = 0
        for keyword in info['keywords']:
            if keyword in symptoms_text_lower:
                keyword_matches += 1
        
        if keyword_matches > 0:
            score = keyword_matches
            matching_specializations.append({
                'name': specialty,
                'score': score,
                'keywords_matched': keyword_matches
            })
    
    # Sort by match score (highest first)
    matching_specializations.sort(key=lambda x: x['score'], reverse=True)
    
    # Take top 2-3 specializations
    top_specializations = matching_specializations[:3]
    
    # If no specializations matched, suggest based on general health
    if not top_specializations:
        top_specializations = [
            {'name': 'General Practice', 'score': 1, 'keywords_matched': 0}
        ]
    
    # Format specializations with reasoning
    formatted_specializations = []
    for spec in top_specializations:
        reason_parts = []
        
        if spec['name'] != 'General Practice':
            keywords_found = []
            for keyword in specialization_map[spec['name']]['keywords']:
                if keyword in symptoms_text_lower:
                    keywords_found.append(keyword)
            
            if keywords_found:
                reason = f"Based on your mention of {', '.join(keywords_found[:2])}"
                if len(keywords_found) > 2:
                    reason += f" and other {spec['name'].lower()} symptoms"
            else:
                reason = f"Recommended for overall assessment"
        else:
            reason = "For general health evaluation and preliminary diagnosis"
        
        formatted_specializations.append({
            'name': spec['name'],
            'reason': reason
        })
    
    # Generate AI response message
    response_message = generate_assistant_response(symptoms_text, is_emergency, formatted_specializations, severity_score)
    
    return {
        'response': response_message,
        'is_emergency': is_emergency,
        'specializations': formatted_specializations,
        'severity_score': severity_score
    }

def generate_assistant_response(symptoms, is_emergency, specializations, severity):
    """Generate a helpful AI response message"""
    
    if is_emergency:
        response = (
            "🚨 <strong>URGENT: Please Seek Immediate Medical Attention</strong><br><br>"
            "Based on your description, this appears to be a medical emergency. "
            "Please call emergency services (911 in the US) or visit the nearest emergency room immediately. "
            "Do not wait for an appointment.<br><br>"
            f"Your symptoms indicate potential {specializations[0]['name'] if specializations else 'medical'} concerns."
        )
    else:
        response = f"<strong>Thank you for sharing your symptoms.</strong><br><br>"
        
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
            response += f"<strong>Recommended specialists:</strong> "
            spec_names = [s['name'] for s in specializations[:2]]
            response += ", ".join(spec_names) + ".<br><br>"
        
        response += (
            "<em>Note: This is an AI-powered preliminary assessment only and does not replace "
            "professional medical advice. Always consult with a qualified healthcare provider.</em>"
        )
    
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)
