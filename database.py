from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    date_of_birth = db.Column(db.Date)
    user_type = db.Column(db.String(20), default='patient')  # 'patient', 'doctor', or 'admin'
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=True)  # Link to doctor if user_type is 'doctor'
    profile_picture = db.Column(db.String(200))  # Path to user's profile picture
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.username}>'

class Doctor(db.Model):
    __tablename__ = 'doctors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(100), nullable=False)
    qualifications = db.Column(db.Text)
    experience = db.Column(db.Integer)
    phone = db.Column(db.String(20))
    email = db.Column(db.String(120))
    consultation_fee = db.Column(db.Float, default=0.0)
    available_days = db.Column(db.String(100))  # e.g., "Mon,Wed,Fri"
    available_time = db.Column(db.String(100))  # e.g., "9:00 AM - 5:00 PM"
    profile_image = db.Column(db.String(200))
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True)
    
    def __repr__(self):
        return f'<Doctor {self.name}>'

class Appointment(db.Model):
    __tablename__ = 'appointments'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False, index=True)
    appointment_date = db.Column(db.Date, nullable=False)
    appointment_time = db.Column(db.String(50), nullable=False)
    symptoms = db.Column(db.Text)
    # Allowed values: pending, approved, rejected, completed, cancelled
    # Legacy value 'confirmed' treated as 'approved' in all display/logic layers
    status = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes = db.Column(db.Text)

    def __repr__(self):
        return f'<Appointment {self.id}>'

class TimeSlot(db.Model):
    __tablename__ = 'time_slots'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    is_available = db.Column(db.Boolean, default=True)
    
    def __repr__(self):
        return f'<TimeSlot {self.day_of_week} {self.start_time}-{self.end_time}>'


class DoctorAvailability(db.Model):
    """Structured availability schedule used by the slot engine.
    One row per (doctor, day_of_week). Admin creates/edits these rows.
    """
    __tablename__ = 'doctor_availability'
    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    # Full weekday name, e.g. "Monday", "Tuesday" …
    day_of_week = db.Column(db.String(20), nullable=False)
    # Stored as "HH:MM" 24-hour strings for sqlite compatibility
    start_time = db.Column(db.String(5), nullable=False, default='09:00')
    end_time = db.Column(db.String(5), nullable=False, default='17:00')
    # Minutes per slot (15 / 30 / 45 / 60)
    slot_duration = db.Column(db.Integer, nullable=False, default=30)
    is_active = db.Column(db.Boolean, default=True)

    doctor = db.relationship('Doctor', backref=db.backref('availability_schedule', lazy=True))

    def __repr__(self):
        return f'<DoctorAvailability doc={self.doctor_id} {self.day_of_week} {self.start_time}-{self.end_time}>'



class MedicalRecord(db.Model):
    __tablename__ = 'medical_records'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationship to patient
    patient = db.relationship('User', backref=db.backref('medical_records', lazy=True))
    
    def __repr__(self):
        return f'<MedicalRecord {self.original_filename}>'

class Feedback(db.Model):
    __tablename__ = 'feedback'
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False, unique=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    appointment = db.relationship('Appointment', backref=db.backref('feedback', uselist=False, lazy=True))
    patient = db.relationship('User', backref=db.backref('feedback_given', lazy=True))
    doctor = db.relationship('Doctor', backref=db.backref('feedback_received', lazy=True))
    
    def __repr__(self):
        return f'<Feedback {self.id} - Rating: {self.rating}>'


class Prescription(db.Model):
    """Medical record / prescription created by a doctor for a completed appointment.
    One record per appointment (appointment_id is unique).
    doctor_id references users.id (the doctor's login user), NOT doctors.id.
    """
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    # One-to-one with Appointment
    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey('appointments.id'),
        nullable=False,
        unique=True
    )
    # Patient user id (for fast patient-scoped queries)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # Doctor user id (the User who created this, not Doctor.id)
    doctor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    # Clinical content
    diagnosis     = db.Column(db.Text, nullable=False)
    prescription  = db.Column(db.Text, nullable=False)
    notes         = db.Column(db.Text, nullable=True)
    follow_up_date = db.Column(db.Date, nullable=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    appointment  = db.relationship(
        'Appointment',
        backref=db.backref('prescription', uselist=False, lazy=True)
    )
    patient = db.relationship(
        'User',
        foreign_keys=[patient_id],
        backref=db.backref('prescriptions_received', lazy=True)
    )
    doctor_user = db.relationship(
        'User',
        foreign_keys=[doctor_user_id],
        backref=db.backref('prescriptions_written', lazy=True)
    )

    def to_dict(self):
        return {
            'id':             self.id,
            'appointment_id': self.appointment_id,
            'diagnosis':      self.diagnosis,
            'prescription':   self.prescription,
            'notes':          self.notes or '',
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'created_at':     self.created_at.strftime('%b %d, %Y %I:%M %p'),
        }

    def __repr__(self):
        return f'<Prescription appt={self.appointment_id}>'


class Report(db.Model):
    __tablename__ = 'reports'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('doctors.id'), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.Text, nullable=True)

    # Compatibility links to existing appointment/prescription flows.
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True, index=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=True, index=True)

    patient = db.relationship('User', foreign_keys=[patient_id], backref=db.backref('reports', lazy=True))
    doctor = db.relationship('Doctor', foreign_keys=[doctor_id], backref=db.backref('reports', lazy=True))
    appointment = db.relationship('Appointment', backref=db.backref('reports', lazy=True))
    prescription = db.relationship('Prescription', backref=db.backref('reports', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'patient_id': self.patient_id,
            'doctor_id': self.doctor_id,
            'file_name': self.file_name,
            'file_path': self.file_path,
            'uploaded_at': self.uploaded_at.strftime('%b %d, %Y %I:%M %p'),
            'description': self.description or ''
        }

    def __repr__(self):
        return f'<Report {self.id} patient={self.patient_id}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(120), nullable=False)
    target_type = db.Column(db.String(30), nullable=True)
    target_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)
    role = db.Column(db.String(20), nullable=False, index=True)

    def __repr__(self):
        return f'<AuditLog user={self.user_id} action={self.action}>'


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info', nullable=False)
    related_id = db.Column(db.Integer, nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<Notification {self.id} user={self.user_id}>'