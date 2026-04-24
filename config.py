import os
from datetime import timedelta


def _ssl_enabled():
    """Check whether the app will run with SSL (cert files present and not disabled)."""
    if os.environ.get('FLASK_SSL', '1') == '0':
        return False
    cert = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssl', 'cert.pem')
    key = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ssl', 'key.pem')
    return os.path.exists(cert) and os.path.exists(key)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///hospital.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    DEBUG = os.environ.get('FLASK_DEBUG', '0') == '1'
    PREFERRED_URL_SCHEME = os.environ.get('PREFERRED_URL_SCHEME', 'https')
    # Secure cookies only when SSL is actually active
    SESSION_COOKIE_SECURE = (
        os.environ.get('SESSION_COOKIE_SECURE', '').lower() in ('1', 'true')
        if os.environ.get('SESSION_COOKIE_SECURE')
        else _ssl_enabled()
    )
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    CACHE_TYPE = 'SimpleCache'
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', '300'))