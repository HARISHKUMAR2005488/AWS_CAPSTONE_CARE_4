from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date
import json
import os

from config import Config
from database import db, User, Doctor, Appointment, TimeSlot, MedicalRecord

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

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
            login_user(user, remember='remember' in request.form)
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
        user_type = request.form.get('user_type', 'patient')
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
            doctor = Doctor(
                name=username,
                specialization=specialization or 'General',
                qualifications=qualifications or '',
                experience=int(experience) if experience else 0,
                phone=phone,
                email=email,
                consultation_fee=float(consultation_fee) if consultation_fee else 0.0,
                available_days=available_days or '',
                available_time=available_time or ''
            )
            db.session.add(doctor)
            db.session.flush()
            new_user.doctor_id = doctor.id
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('signup.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/doctors')
def doctors():
    specialization = request.args.get('specialization')
    search = request.args.get('search')
    
    query = Doctor.query.filter_by(is_available=True)
    
    if specialization and specialization != 'all':
        query = query.filter_by(specialization=specialization)
    
    if search:
        query = query.filter(Doctor.name.ilike(f'%{search}%'))
    
    doctors_list = query.all()
    specializations = db.session.query(Doctor.specialization).distinct().all()
    
    return render_template('doctors.html', 
                         doctors=doctors_list, 
                         specializations=[s[0] for s in specializations])

@app.route('/book-appointment/<int:doctor_id>', methods=['GET', 'POST'])
@login_required
def book_appointment(doctor_id):
    if current_user.user_type == 'admin':
        flash('Admins cannot book appointments', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    doctor = Doctor.query.get_or_404(doctor_id)
    
    if request.method == 'POST':
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        symptoms = request.form.get('symptoms')
        
        # Check if slot is available
        existing_appointment = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
            appointment_time=appointment_time,
            status='confirmed'
        ).first()
        
        if existing_appointment:
            flash('This time slot is already booked', 'danger')
            return redirect(url_for('book_appointment', doctor_id=doctor_id))
        
        # Create appointment
        appointment = Appointment(
            patient_id=current_user.id,
            doctor_id=doctor_id,
            appointment_date=datetime.strptime(appointment_date, '%Y-%m-%d').date(),
            appointment_time=appointment_time,
            symptoms=symptoms,
            status='pending'
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        flash('Appointment booked successfully! Waiting for confirmation.', 'success')
        return redirect(url_for('user_dashboard'))
    
    # Generate available time slots (simplified version)
    available_slots = [
        '9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM',
        '11:00 AM', '11:30 AM', '2:00 PM', '2:30 PM',
        '3:00 PM', '3:30 PM', '4:00 PM'
    ]
    
    return render_template('appointments.html', 
                         doctor=doctor, 
                         available_slots=available_slots,
                         min_date=date.today())

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.user_type == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.user_type == 'doctor':
        return redirect(url_for('doctor_dashboard'))
    
    appointments = Appointment.query.filter_by(
        patient_id=current_user.id
    ).order_by(Appointment.appointment_date.desc()).all()
    
    return render_template('user.html', appointments=appointments)

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
    today_appointments = Appointment.query.filter_by(
        doctor_id=doctor.id,
        appointment_date=today
    ).order_by(Appointment.appointment_time).all()
    
    # Get upcoming appointments
    upcoming_appointments = Appointment.query.filter(
        Appointment.doctor_id == doctor.id,
        Appointment.appointment_date > today,
        Appointment.status != 'cancelled'
    ).order_by(Appointment.appointment_date, Appointment.appointment_time).limit(10).all()
    
    # Get all appointments for statistics
    all_appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    total_appointments = len(all_appointments)
    pending_count = len([a for a in all_appointments if a.status == 'pending'])
    confirmed_count = len([a for a in all_appointments if a.status == 'confirmed'])
    completed_count = len([a for a in all_appointments if a.status == 'completed'])
    
    return render_template('doctor.html',
                         doctor=doctor,
                         today_appointments=today_appointments,
                         upcoming_appointments=upcoming_appointments,
                         total_appointments=total_appointments,
                         pending_count=pending_count,
                         confirmed_count=confirmed_count,
                         completed_count=completed_count,
                         today=today)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.user_type != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    # Get statistics
    total_patients = User.query.filter_by(user_type='patient').count()
    total_doctors = Doctor.query.count()
    total_appointments = Appointment.query.count()
    pending_appointments = Appointment.query.filter_by(status='pending').count()
    
    # Get recent appointments
    recent_appointments = Appointment.query.order_by(
        Appointment.created_at.desc()
    ).limit(10).all()
    doctors = Doctor.query.order_by(Doctor.created_at.desc()).all()
    
    return render_template('admin.html',
                         total_patients=total_patients,
                         total_doctors=total_doctors,
                         total_appointments=total_appointments,
                         pending_appointments=pending_appointments,
                         recent_appointments=recent_appointments,
                         doctors=doctors)

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
    new_status = request.form.get('status')
    
    if new_status in ['confirmed', 'cancelled', 'completed']:
        appointment.status = new_status
        db.session.commit()
        flash(f'Appointment {new_status} successfully', 'success')
        return jsonify({'success': True})
    
    return jsonify({'success': False, 'message': 'Invalid status'})

@app.route('/admin/add-doctor', methods=['POST'])
@login_required
def add_doctor():
    if current_user.user_type != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    try:
        doctor = Doctor(
            name=request.form.get('name'),
            specialization=request.form.get('specialization'),
            qualifications=request.form.get('qualifications'),
            experience=int(request.form.get('experience', 0)),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            consultation_fee=float(request.form.get('consultation_fee', 0)),
            available_days=request.form.get('available_days'),
            available_time=request.form.get('available_time')
        )
        
        db.session.add(doctor)
        db.session.commit()
        
        flash('Doctor added successfully', 'success')
        return jsonify({'success': True})
    except Exception as e:
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
    date_str = request.args.get('date')
    
    if not date_str:
        return jsonify({'error': 'Date required'}), 400
    
    try:
        selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Get doctor's working days and hours
        doctor = Doctor.query.get_or_404(doctor_id)
        
        # Get already booked slots
        booked_slots = Appointment.query.filter_by(
            doctor_id=doctor_id,
            appointment_date=selected_date,
            status='confirmed'
        ).all()
        
        booked_times = [app.appointment_time for app in booked_slots]
        
        # Generate available slots based on doctor's schedule
        available_slots = [
            '9:00 AM', '9:30 AM', '10:00 AM', '10:30 AM',
            '11:00 AM', '11:30 AM', '2:00 PM', '2:30 PM',
            '3:00 PM', '3:30 PM', '4:00 PM'
        ]
        
        # Filter out booked slots
        available_slots = [slot for slot in available_slots if slot not in booked_times]
        
        return jsonify({'available_slots': available_slots})
    except ValueError:
        return jsonify({'error': 'Invalid date format'}), 400

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
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Document uploaded', 'description': description})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/cancel-appointment/<int:appointment_id>')
@login_required
def cancel_appointment(appointment_id):
    appointment = Appointment.query.get_or_404(appointment_id)
    
    # Check if user owns the appointment or is admin
    if appointment.patient_id != current_user.id and current_user.user_type != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('user_dashboard'))
    
    appointment.status = 'cancelled'
    db.session.commit()
    
    flash('Appointment cancelled successfully', 'success')
    
    if current_user.user_type == 'admin':
        return redirect(url_for('manage_appointments'))
    else:
        return redirect(url_for('user_dashboard'))

@app.route('/doctor/update-appointment/<int:appointment_id>', methods=['POST'])
@login_required
def doctor_update_appointment(appointment_id):
    if current_user.user_type != 'doctor':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    appointment = Appointment.query.get_or_404(appointment_id)
    doctor = Doctor.query.get(current_user.doctor_id)
    
    # Ensure this appointment belongs to this doctor
    if appointment.doctor_id != doctor.id:
        return jsonify({'success': False, 'message': 'Access denied'})
    
    new_status = request.form.get('status')
    notes = request.form.get('notes', '')
    
    if new_status in ['confirmed', 'cancelled', 'completed']:
        appointment.status = new_status
        if notes:
            appointment.notes = notes
        db.session.commit()
        return jsonify({'success': True, 'message': f'Appointment {new_status} successfully'})
    
    return jsonify({'success': False, 'message': 'Invalid status'})

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