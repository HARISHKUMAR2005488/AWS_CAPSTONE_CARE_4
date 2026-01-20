# Hospital Care Application Startup Script
# This script ensures the virtual environment is activated before running the app

Write-Host "Starting Hospital Care Application..." -ForegroundColor Green
Write-Host "Activating virtual environment..." -ForegroundColor Yellow

# Activate virtual environment
& "$PSScriptRoot\.venv\Scripts\Activate.ps1"

Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host "Starting Flask application..." -ForegroundColor Yellow
Write-Host ""
Write-Host "Application will be available at: http://127.0.0.1:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Demo Credentials:" -ForegroundColor Magenta
Write-Host "  Admin:  admin@care4u.com / admin123" -ForegroundColor White
Write-Host "  Doctor: sarah.j@care4u.com / doctor123" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray
Write-Host ""

# Run the application
python app.py
