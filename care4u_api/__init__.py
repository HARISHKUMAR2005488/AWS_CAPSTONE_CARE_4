"""CARE_4_U production API package."""

import time
import uuid

from flask import Flask, g, request

from care4u_api.auth.routes import auth_bp
from care4u_api.appointments.routes import appointments_bp
from care4u_api.chatbot.routes import chatbot_bp
from care4u_api.notifications.routes import notifications_bp
from care4u_api.config import ApiConfig
from care4u_api.utils.logging_utils import configure_structured_logging
from care4u_api.utils.openapi import register_openapi_routes
from care4u_api.utils.responses import error_response


def create_app() -> Flask:
    """Application factory for stateless REST API deployment."""
    app = Flask(__name__)
    app.config.from_object(ApiConfig)

    configure_structured_logging(app)

    @app.before_request
    def start_request_timer():
        g.request_id = str(uuid.uuid4())
        g.request_started_at = time.perf_counter()

    @app.after_request
    def log_request(response):
        started = getattr(g, 'request_started_at', None)
        latency_ms = int((time.perf_counter() - started) * 1000) if started else -1
        app.logger.info(
            'request_processed',
            extra={
                'request_id': getattr(g, 'request_id', ''),
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code,
                'latency_ms': latency_ms,
                'remote_addr': request.remote_addr,
            },
        )
        response.headers['X-Request-Id'] = getattr(g, 'request_id', '')
        return response

    app.register_blueprint(auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(appointments_bp, url_prefix='/api/v1/appointments')
    app.register_blueprint(notifications_bp, url_prefix='/api/v1/notifications')
    app.register_blueprint(chatbot_bp, url_prefix='/api/v1/chatbot')

    register_openapi_routes(app)

    @app.errorhandler(404)
    def handle_404(_error):
        return error_response('Resource not found', status_code=404)

    @app.errorhandler(405)
    def handle_405(_error):
        return error_response('Method not allowed', status_code=405)

    @app.errorhandler(500)
    def handle_500(_error):
        return error_response('Internal server error', status_code=500)

    return app
