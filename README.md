# Care_4_U Hospitals

**A Modern Telemedicine & Hospital Management Platform**

![Status](https://img.shields.io/badge/status-active-brightgreen)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Flask](https://img.shields.io/badge/flask-2.3.3-lightblue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running the Application](#running-the-application)
- [Demo Credentials](#demo-credentials)
- [API Endpoints](#api-endpoints)
- [Screenshots](#screenshots)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)

---

## 🏥 Overview

**Care_4_U Hospitals** is a comprehensive, full-stack telemedicine and hospital management platform designed to streamline healthcare operations. The application provides role-based access for patients, doctors, and administrators, enabling seamless appointment scheduling, medical record management, and healthcare provider coordination.

Built with modern web technologies and a focus on user experience, Care_4_U offers an intuitive interface for healthcare delivery in the digital age, featuring responsive design, professional UI/UX, and scalable architecture.

**Key Capabilities:**
- Real-time appointment booking and management
- Secure patient medical records system
- Doctor availability scheduling
- Admin dashboard with comprehensive analytics
- Professional healthcare-themed design
- Mobile-responsive interface

---

## ✨ Features

### 👨‍⚕️ **Patient Portal**
- ✅ User registration and secure authentication
- ✅ Browse available doctors by specialty and ratings
- ✅ Book, reschedule, and cancel appointments
- ✅ View appointment history and upcoming bookings
- ✅ Access personal medical records and documents
- ✅ Update profile information and health data
- ✅ View doctor details, qualifications, and experience
- ✅ Receive appointment confirmations and reminders

### 👩‍⚕️ **Doctor Dashboard**
- ✅ Manage availability and time slots
- ✅ View daily and upcoming appointment schedule
- ✅ Access patient medical history and previous records
- ✅ View patient symptoms and medical information
- ✅ Add notes and observations for appointments
- ✅ Manage consultation fees and specialization
- ✅ Track appointment statistics and patient counts
- ✅ Professional schedule overview with color-coded status

### 🔐 **Admin Panel**
- ✅ Comprehensive dashboard with system analytics
- ✅ Manage doctor profiles, credentials, and availability
- ✅ Monitor all appointments across the system
- ✅ Approve/reject appointment requests
- ✅ Manage patient accounts and access
- ✅ View system statistics (total patients, doctors, appointments)
- ✅ Generate reports and analytics
- ✅ System configuration and settings management

### 🎨 **UI/UX Enhancements**
- ✅ Modern healthcare-themed design system
- ✅ Fully responsive layout (mobile, tablet, desktop)
- ✅ Professional gradient buttons and cards
- ✅ Status badges with color coding
- ✅ Form validation with clear feedback
- ✅ Empty state messaging
- ✅ Progress indicators for multi-step processes
- ✅ Smooth animations and transitions
- ✅ Accessibility-focused design

---

## 🛠 Tech Stack

### **Backend**
- **Framework**: Flask 2.3.3
- **Language**: Python 3.9+
- **Database**: SQLite with Flask-SQLAlchemy ORM
- **Authentication**: Flask-Login with session management
- **Validation**: WTForms for form handling

### **Frontend**
- **Markup**: HTML5
- **Styling**: CSS3 with modern CSS Grid, Flexbox, and CSS Variables
- **Interactivity**: Vanilla JavaScript (ES6+)
- **Icons**: Font Awesome 6
- **Responsive Design**: Mobile-first approach

### **Development Tools**
- **Runtime**: Python 3.9+
- **Package Manager**: pip
- **Virtual Environment**: venv
- **Version Control**: Git

### **Architecture Highlights**
- Model-View-Controller (MVC) pattern
- RESTful routing principles
- Session-based authentication
- Jinja2 templating engine
- CSS custom properties (variables) for theming
- Responsive breakpoints: 480px, 768px, 1024px

---

## 📁 Project Structure

```
AWS_CAPSTONE_CARE_4/
├── app.py                      # Main Flask application & routes
├── config.py                   # Configuration settings
├── database.py                 # Database initialization & models
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
│
├── templates/                  # Jinja2 HTML templates
│   ├── base.html              # Base layout template
│   ├── index.html             # Homepage
│   ├── about.html             # About page
│   ├── login.html             # Login page
│   ├── signup.html            # Registration page
│   ├── doctors.html           # Doctors directory
│   ├── appointments.html      # Appointment booking
│   ├── user.html              # Patient dashboard
│   ├── doctor.html            # Doctor dashboard
│   ├── doctor_patients.html   # Doctor's patient list
│   ├── patient_records.html   # Doctor's patient records view
│   ├── admin.html             # Admin dashboard
│   └── bookings.html          # Admin bookings management
│
├── static/                     # Static assets
│   ├── css/
│   │   └── style.css          # Main stylesheet (5900+ lines)
│   └── js/
│       └── script.js          # Client-side functionality
│
├── instance/                   # Instance-specific files
│   ├── uploads/               # File upload directories
│   │   ├── 3/                # Doctor profile pictures
│   │   ├── 5/                # Patient files
│   │   └── profile_pictures/  # User avatars
│   └── care4u.db             # SQLite database
│
├── services/                   # Business logic layer
│   └── [service modules]      # Utility functions
│
├── .venv/                      # Python virtual environment
├── setup.ps1                   # Setup script
└── run.ps1                     # Run script

```

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.9 or higher**
- **pip** (Python package manager)
- **PowerShell** (for Windows setup/run scripts)
- **Modern web browser** (Chrome, Firefox, Safari, or Edge)
- **4GB RAM** minimum
- **200MB disk space**

### **Verify Installation**
```powershell
python --version
pip --version
```

---

## 🚀 Installation & Setup

### **Option 1: Automated Setup (Recommended - Windows)**

1. Clone or download the project:
```powershell
cd path/to/AWS_CAPSTONE_CARE_4
```

2. Run the setup script:
```powershell
.\setup.ps1
```

This will:
- Create a Python virtual environment
- Install all dependencies from `requirements.txt`
- Initialize the database
- Create necessary directories

### **Option 2: Manual Setup (All Platforms)**

1. **Create virtual environment:**
```bash
python -m venv .venv
```

2. **Activate virtual environment:**

**Windows (PowerShell):**
```powershell
.\.venv\Scripts\Activate.ps1
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Initialize database:**
```python
python
>>> from database import init_db
>>> init_db()
>>> exit()
```

---

## ▶️ Running the Application

### **Windows (PowerShell)**

**Using run script (Recommended):**
```powershell
.\run.ps1
```

**Manual execution:**
```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

### **macOS/Linux**

```bash
source .venv/bin/activate
python app.py
```

### **Access the Application**

Open your browser and navigate to:
```
http://127.0.0.1:5000
```

The application will be running on **port 5000** by default.

---

## 🔑 Demo Credentials

### **Admin Account**
- **Email**: `admin@care4u.com`
- **Password**: `admin123`
- **Access**: Full system management, analytics, user management

### **Doctor Account**
- **Email**: `sarah.j@care4u.com`
- **Password**: `doctor123`
- **Specialty**: Cardiology
- **Access**: Appointment management, patient records, availability

### **Patient Account**
- **Email**: `patient@care4u.com`
- **Password**: `patient123`
- **Access**: Book appointments, view medical history, manage profile

**Note**: You can also create new accounts through the signup page.

---

## 🔗 API Endpoints

### **Authentication Routes**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/login` | User login |
| GET/POST | `/signup` | User registration |
| GET | `/logout` | User logout |

### **Patient Routes**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/user` | Patient dashboard |
| GET | `/doctors` | Browse doctors |
| GET/POST | `/appointments/<doctor_id>` | Book appointment |
| GET | `/bookings` | View patient appointments |

### **Doctor Routes**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/doctor` | Doctor dashboard |
| GET | `/doctor_patients` | View patient list |
| GET | `/patient_records/<patient_id>` | View patient details |

### **Admin Routes**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin` | Admin dashboard |
| GET | `/bookings` | Manage appointments |
| GET/POST | `/manage_doctors` | Manage doctor profiles |

### **Public Routes**
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Homepage |
| GET | `/about` | About page |

---

## 📸 Screenshots

### **Patient Portal**
- Login & Registration
  
  ![Placeholder: Patient Login Screen]

- Doctor Directory
  
  ![Placeholder: Doctor Listing Page]

- Appointment Booking
  
  ![Placeholder: Booking Form with Progress]

- Patient Dashboard
  
  ![Placeholder: Patient Dashboard Overview]

### **Doctor Dashboard**
- Appointment Schedule
  
  ![Placeholder: Doctor Appointments View]

- Patient Records
  
  ![Placeholder: Patient Medical Records]

### **Admin Dashboard**
- System Analytics
  
  ![Placeholder: Admin Dashboard Statistics]

- Appointment Management
  
  ![Placeholder: Bookings Management Table]

### **Design System**
- Modern Healthcare Color Scheme
  
  ![Placeholder: Color Palette (Medical Blue, Green, Accents)]

- Responsive Design Examples
  
  ![Placeholder: Mobile, Tablet, Desktop Views]

---

## 🚀 Future Enhancements

### **Short-term (Next Release)**
- [ ] Email notifications for appointment reminders
- [ ] Appointment rescheduling functionality
- [ ] Doctor ratings and review system
- [ ] Payment integration (Stripe/PayPal)
- [ ] Prescription management system
- [ ] Video consultation capability
- [ ] SMS notifications

### **Medium-term (Q2-Q3 2026)**
- [ ] AI-powered appointment scheduling
- [ ] Medical chatbot for basic consultations
- [ ] Insurance verification and claims processing
- [ ] Multi-language support
- [ ] Dark mode theme
- [ ] Advanced search and filtering
- [ ] Appointment calendar export (iCal)

### **Long-term (Q4 2026 & Beyond)**
- [ ] Mobile native applications (iOS/Android)
- [ ] Telemedicine platform with video conferencing
- [ ] Electronic health records (EHR) system
- [ ] Hospital bed management
- [ ] Pharmacy integration
- [ ] Billing and invoicing system
- [ ] Advanced analytics and reporting
- [ ] Machine learning for appointment no-show prediction
- [ ] Integration with wearable devices
- [ ] Cloud deployment (AWS, Azure, GCP)

### **Technical Improvements**
- [ ] Unit and integration testing (pytest)
- [ ] API documentation (Swagger/OpenAPI)
- [ ] Docker containerization
- [ ] CI/CD pipeline setup
- [ ] Performance optimization and caching
- [ ] Security audits and penetration testing
- [ ] Database migration to PostgreSQL
- [ ] Microservices architecture transition

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### **Code Guidelines**
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Test your changes before submitting
- Update documentation as needed

---

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## 👨‍💻 Author

**Care_4_U Hospitals Development Team**

---

## 📞 Support & Contact

For questions, bug reports, or feature requests:

- **Email**: support@care4u.com
- **Issues**: GitHub Issues page
- **Documentation**: See README.md and inline code comments

---

## 🔐 Security Notes

- All user passwords are hashed using werkzeug security
- Sessions are protected with secure cookies
- Database queries use parameterized statements to prevent SQL injection
- Input validation on all forms
- CORS protection for API endpoints

---

## 📊 Project Statistics

- **Total Lines of CSS**: 6000+
- **Total Lines of HTML**: 2000+
- **Total Lines of Python**: 500+
- **Number of Templates**: 12
- **Database Models**: 5 (User, Doctor, Appointment, PatientRecord, etc.)
- **API Endpoints**: 15+

---

## 🎯 Project Goals

✅ Provide accessible healthcare scheduling  
✅ Streamline hospital operations  
✅ Enhance patient-doctor communication  
✅ Demonstrate full-stack web development capabilities  
✅ Build a scalable and maintainable codebase  
✅ Create professional, modern user interfaces  

---

**Last Updated**: January 2026  
**Version**: 1.0.0  
**Status**: Active Development
```
hospitalcare/
├── app.py              # Main application file
├── config.py           # Configuration settings
├── database.py         # Database models
├── requirements.txt    # Python dependencies
├── run.ps1            # Application startup script
├── setup.ps1          # Setup script
├── instance/          # Database files
├── static/
│   ├── css/           # Stylesheets
│   └── js/            # JavaScript files
└── templates/         # HTML templates
```

## User Roles

### Patient
- Book appointments with doctors
- View appointment history
- Manage profile

### Doctor
- View today's appointments
- Manage upcoming appointments
- Confirm/cancel appointments
- Add appointment notes
- Mark appointments as completed

### Admin
- Manage all appointments
- Add new doctors
- View system statistics
- Manage users



## AWS Deployment Guide

This application can be deployed to AWS using EC2, Elastic Beanstalk, or ECS. Below is a comprehensive guide for AWS deployment.

### Prerequisites

- AWS Account with appropriate permissions
- AWS CLI installed and configured
- Basic understanding of AWS services (EC2, DynamoDB, SNS, IAM)

### Architecture Options

#### Option 1: AWS EC2 with DynamoDB (Recommended)

This deployment uses:
- **EC2** instance for hosting the Flask application
- **DynamoDB** tables for data storage (Users, Doctors, Appointments)
- **SNS** for appointment notifications
- **IAM** roles for secure access

#### Option 2: AWS Elastic Beanstalk

Simplified deployment with automatic scaling and load balancing.

### Step-by-Step Deployment

#### 1. Set Up DynamoDB Tables

Create the following DynamoDB tables in AWS Console or using AWS CLI:

**Users Table:**
```bash
aws dynamodb create-table \
    --table-name Users \
    --attribute-definitions \
        AttributeName=username,AttributeType=S \
    --key-schema AttributeName=username,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

**Doctors Table:**
```bash
aws dynamodb create-table \
    --table-name Doctors \
    --attribute-definitions \
        AttributeName=username,AttributeType=S \
    --key-schema AttributeName=username,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

**Appointments Table:**
```bash
aws dynamodb create-table \
    --table-name Appointments \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=username,AttributeType=S \
        AttributeName=date,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "[{\"IndexName\":\"username-index\",\"KeySchema\":[{\"AttributeName\":\"username\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}},{\"IndexName\":\"date-index\",\"KeySchema\":[{\"AttributeName\":\"date\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

**MedicalRecords Table (for storing patient medical documents):**
```bash
aws dynamodb create-table \
    --table-name MedicalRecords \
    --attribute-definitions \
        AttributeName=id,AttributeType=S \
        AttributeName=username,AttributeType=S \
    --key-schema AttributeName=id,KeyType=HASH \
    --global-secondary-indexes \
        "[{\"IndexName\":\"username-index\",\"KeySchema\":[{\"AttributeName\":\"username\",\"KeyType\":\"HASH\"}],\"Projection\":{\"ProjectionType\":\"ALL\"}}]" \
    --billing-mode PAY_PER_REQUEST \
    --region us-east-1
```

> **Note on Medical File Storage**: Medical reports are stored as base64-encoded strings in DynamoDB. Due to DynamoDB's 400KB item size limit, the application enforces a 1MB maximum file size. For production use with larger files, consider using Amazon S3 instead.

#### 2. Create SNS Topic for Notifications

```bash
aws sns create-topic --name AppointmentNotifications --region us-east-1
```

Subscribe your email to receive notifications:
```bash
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:AppointmentNotifications \
    --protocol email \
    --notification-endpoint your-email@example.com
```

#### 3. Create IAM Role for EC2

Create an IAM role with the following policies:
- **AmazonDynamoDBFullAccess** (or custom policy with read/write permissions)
- **AmazonSNSFullAccess** (or custom policy for publishing)

```bash
# Create trust policy file (trust-policy.json)
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}

# Create the role
aws iam create-role \
    --role-name HospitalCareEC2Role \
    --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy \
    --role-name HospitalCareEC2Role \
    --policy-arn arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess

aws iam attach-role-policy \
    --role-name HospitalCareEC2Role \
    --policy-arn arn:aws:iam::aws:policy/AmazonSNSFullAccess

# Create instance profile
aws iam create-instance-profile \
    --instance-profile-name HospitalCareEC2Profile

aws iam add-role-to-instance-profile \
    --instance-profile-name HospitalCareEC2Profile \
    --role-name HospitalCareEC2Role
```

#### 4. Launch EC2 Instance

1. **Choose AMI**: Amazon Linux 2023 or Ubuntu Server
2. **Instance Type**: t2.micro (free tier) or t2.small
3. **IAM Role**: Attach the `HospitalCareEC2Profile` created above
4. **Security Group**: Allow inbound traffic on ports 22 (SSH) and 80 (HTTP) or 5000
5. **Storage**: 8-20 GB is sufficient

#### 5. Connect to EC2 and Set Up Application

```bash
# SSH into your EC2 instance
ssh -i your-key.pem ec2-user@your-ec2-public-ip

# Update system packages
sudo yum update -y  # For Amazon Linux
# or
sudo apt update && sudo apt upgrade -y  # For Ubuntu

# Install Python and Git
sudo yum install python3 python3-pip git -y  # Amazon Linux
# or
sudo apt install python3 python3-pip python3-venv git -y  # Ubuntu

# Clone your repository
git clone https://github.com/yourusername/hospital-care.git
cd hospital-care

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install boto3 gunicorn
```

#### 6. Configure Environment Variables

Create a `.env` file or export environment variables:

```bash
export FLASK_SECRET_KEY="your-secure-random-secret-key"
export AWS_REGION="us-east-1"
export USERS_TABLE="Users"
export DOCTORS_TABLE="Doctors"
export APPOINTMENTS_TABLE="Appointments"
export MEDICAL_RECORDS_TABLE="MedicalRecords"
export SNS_TOPIC_ARN="arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:AppointmentNotifications"
```

Or create a `.env` file and load it in your application.

#### 7. Run the Application

**Development Mode:**
```bash
python app_aws.py
```

**Production Mode with Gunicorn:**
```bash
gunicorn -w 4 -b 0.0.0.0:80 app_aws:app
```

For running as a background service, create a systemd service file:

```bash
sudo nano /etc/systemd/system/hospitalcare.service
```

Add the following content:
```ini
[Unit]
Description=Hospital Care Flask Application
After=network.target

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/hospital-care
Environment="PATH=/home/ec2-user/hospital-care/.venv/bin"
Environment="FLASK_SECRET_KEY=your-secret-key"
Environment="AWS_REGION=us-east-1"
Environment="MEDICAL_RECORDS_TABLE=MedicalRecords"
Environment="SNS_TOPIC_ARN=arn:aws:sns:us-east-1:ACCOUNT_ID:AppointmentNotifications"
ExecStart=/home/ec2-user/hospital-care/.venv/bin/gunicorn -w 4 -b 0.0.0.0:80 app_aws:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable hospitalcare
sudo systemctl start hospitalcare
sudo systemctl status hospitalcare
```

#### 8. Access Your Application

Visit your EC2 instance's public IP address: `http://your-ec2-public-ip`

### Elastic Beanstalk Deployment

For a more managed approach:

1. **Install EB CLI:**
```bash
pip install awsebcli
```

2. **Initialize Elastic Beanstalk:**
```bash
eb init -p python-3.11 hospital-care --region us-east-1
```

3. **Create environment:**
```bash
eb create hospital-care-env
```

4. **Set environment variables:**
```bash
eb setenv FLASK_SECRET_KEY="your-key" AWS_REGION="us-east-1" MEDICAL_RECORDS_TABLE="MedicalRecords" SNS_TOPIC_ARN="your-topic-arn"
```

5. **Deploy:**
```bash
eb deploy
```

6. **Open application:**
```bash
eb open
```

### Security Best Practices

1. **Never hardcode credentials** - Use IAM roles and environment variables
2. **Use HTTPS** - Set up SSL certificate with AWS Certificate Manager and Application Load Balancer
3. **Enable DynamoDB encryption** at rest
4. **Use VPC** - Deploy EC2 in private subnet with NAT Gateway
5. **Configure Security Groups** - Restrict access to necessary ports only
6. **Enable CloudWatch Logs** - Monitor application logs
7. **Regular backups** - Enable DynamoDB point-in-time recovery
8. **Update dependencies** - Keep Python packages up to date

### Monitoring and Logging

Enable CloudWatch for monitoring:
```bash
# Install CloudWatch agent on EC2
sudo yum install amazon-cloudwatch-agent -y

# Configure logging in your Flask app
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
```

### Cost Optimization

- Use **t2.micro** or **t3.micro** instances (free tier eligible)
- Set **PAY_PER_REQUEST** billing mode for DynamoDB (good for low traffic)
- Use **Auto Scaling** for production workloads
- Set up **CloudWatch alarms** for cost monitoring

### Troubleshooting AWS Deployment

**DynamoDB Access Denied:**
- Verify IAM role is attached to EC2 instance
- Check IAM policies include DynamoDB permissions

**SNS Notifications Not Received:**
- Confirm email subscription to SNS topic
- Check SNS_TOPIC_ARN environment variable is set correctly

**Application Not Accessible:**
- Verify Security Group allows inbound traffic on port 80/5000
- Check if application is running: `sudo systemctl status hospitalcare`

**Connection Timeout:**
- Ensure EC2 instance has public IP
- Verify route table and internet gateway configuration

**Medical File Upload Fails:**
- Ensure MedicalRecords table is created in DynamoDB
- Check file size is under 1MB (DynamoDB limitation)
- Verify allowed file types: PDF, JPG, JPEG, PNG, DOC, DOCX
- Check MEDICAL_RECORDS_TABLE environment variable is set

### Medical Records Storage in DynamoDB

**How It Works:**
- Files are converted to **base64-encoded strings** and stored in DynamoDB
- Maximum file size: **1MB** (enforced by application)
- DynamoDB item size limit: **400KB** per item
- Supported file types: PDF, JPG, JPEG, PNG, DOC, DOCX

**Limitations:**
- Not suitable for large files (X-rays, CT scans, large PDFs)
- Higher storage costs compared to S3
- Slower retrieval for large files
- Base64 encoding increases storage size by ~33%

**For Production:**
For larger medical files or high-volume storage, consider migrating to **Amazon S3** with DynamoDB storing only metadata and S3 file references.

## Troubleshooting

### ImportError: cannot import name 'url_decode'

This is a compatibility issue. Run the setup script again:
```powershell
.\setup.ps1
```

### Port 5000 already in use

Change the port in app.py:
```python
app.run(debug=True, port=5001)  # Use different port
```

### Database errors

Delete the database and restart:
```powershell
Remove-Item instance\hospital.db
python app.py
```

## Development

To add new features:
1. Activate virtual environment: `.\.venv\Scripts\Activate.ps1`
2. Make your changes
3. Test the application
4. Update requirements.txt if new packages are added

## License

This project is for educational purposes.

