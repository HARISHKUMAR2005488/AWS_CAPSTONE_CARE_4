from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import json

from config import Config
from database import db, User, Doctor, Appointment, TimeSlot

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
    
    # Add sample admin if none exists
    if not User.query.filter_by(user_type='admin').first():
        admin = User(
            username='admin',
            email='admin@care4u.com',
            password=generate_password_hash('admin123', method='pbkdf2:sha256'),
            user_type='admin'
        )
        db.session.add(admin)
        db.session.commit()
    
    # Add sample doctors if none exists
    if not Doctor.query.first():
        doctors = [
            Doctor(
                name='Dr. Sarah Johnson',
                specialization='Cardiology',
                qualifications='MD, FACC',
                experience=15,
                phone='+1-555-0101',
                email='sarah.j@care4u.com',
                consultation_fee=150.00,
                available_days='Mon,Tue,Wed,Thu',
                available_time='9:00 AM - 4:00 PM'
            ),
            Doctor(
                name='Dr. Michael Chen',
                specialization='Neurology',
                qualifications='MD, PhD',
                experience=12,
                phone='+1-555-0102',
                email='michael.c@care4u.com',
                consultation_fee=180.00,
                available_days='Tue,Wed,Thu,Fri',
                available_time='10:00 AM - 6:00 PM'
            ),
            Doctor(
                name='Dr. Emily Davis',
                specialization='Pediatrics',
                qualifications='MD, FAAP',
                experience=8,
                phone='+1-555-0103',
                email='emily.d@care4u.com',
                consultation_fee=120.00,
                available_days='Mon,Tue,Thu,Fri',
                available_time='8:00 AM - 3:00 PM'
            )
        ]
        db.session.add_all(doctors)
        db.session.commit()
    
    # Create doctor login accounts if they don't exist
    doctors = Doctor.query.all()
    for doctor in doctors:
        if not User.query.filter_by(doctor_id=doctor.id).first():
            doctor_user = User(
                username=doctor.name.lower().replace(' ', '_').replace('.', ''),
                email=doctor.email,
                password=generate_password_hash('doctor123', method='pbkdf2:sha256'),
                user_type='doctor',
                doctor_id=doctor.id,
                phone=doctor.phone
            )
            db.session.add(doctor_user)
    db.session.commit()

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
        
        # Create new user
        new_user = User(
            username=username,
            email=email,
            password=generate_password_hash(password, method='pbkdf2:sha256'),
            phone=phone,
            user_type='patient'
        )
        
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
    
    return render_template('admin.html',
                         total_patients=total_patients,
                         total_doctors=total_doctors,
                         total_appointments=total_appointments,
                         pending_appointments=pending_appointments,
                         recent_appointments=recent_appointments)

@app.route('/admin/appointments')
@login_required
def manage_appointments():
    if current_user.user_type != 'admin':
        flash('Access denied', 'danger')
        return redirect(url_for('index'))
    
    appointments = Appointment.query.order_by(
        Appointment.appointment_date.desc()
    ).all()
    
    return render_template('bookings.html', appointments=appointments)

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)