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
