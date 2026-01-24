# Hospital Care Application

A comprehensive hospital management system built with Flask.

## Features

- **Patient Portal**: Book appointments, view medical history
- **Doctor Dashboard**: Manage appointments, view patient information
- **Admin Panel**: Manage doctors, appointments, and system settings

## Quick Start

### First Time Setup

1. Run the setup script to create virtual environment and install dependencies:
```powershell
.\setup.ps1
```

### Running the Application

Use the run script:
```powershell
.\run.ps1
```

Or manually:
```powershell
.\.venv\Scripts\Activate.ps1
python app.py
```

The application will be available at: http://127.0.0.1:5000

## Demo Credentials

- **Admin**: admin@care4u.com / admin123
- **Doctor**: sarah.j@care4u.com / doctor123
- **Patient**: Create your own account

## Technology Stack

- **Backend**: Flask 2.3.3
- **Database**: SQLite with Flask-SQLAlchemy
- **Authentication**: Flask-Login
- **Frontend**: HTML, CSS, JavaScript
- **Icons**: Font Awesome

## Project Structure

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

